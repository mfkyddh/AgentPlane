from __future__ import annotations

import os
import queue
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable, Mapping

from agentplane.runtime.execution_models import (
    BackendType,
    CommandSpec,
    ExecutionBindings,
    ExecutionError,
    ExecutionPlan,
    ExecutionResult,
    RenderedExecution,
    StreamChunk,
    _classify_error,
)


class BackendRunner:
    def __init__(self, backends: Mapping[BackendType, Any]) -> None:
        self._backends = dict(backends)

    def render_spec(self, spec: CommandSpec) -> RenderedExecution:
        try:
            backend = self._backends[spec.backend_type]
        except KeyError as exc:
            raise ValueError(f"unsupported backend type: {spec.backend_type}") from exc
        return backend.render_spec(spec)

    def execute_spec(self, spec: CommandSpec) -> ExecutionResult:
        rendered = self.render_spec(spec)
        return self._run_rendered(rendered, timeout=spec.timeout)

    def execute_spec_stream(
        self,
        spec: CommandSpec,
        *,
        on_chunk: Callable[[StreamChunk], None] | None = None,
    ) -> ExecutionResult:
        rendered = self.render_spec(spec)
        return self._run_rendered_stream(rendered, timeout=spec.timeout, on_chunk=on_chunk)

    def render(self, plan: ExecutionPlan, *, bindings: ExecutionBindings | None = None) -> RenderedExecution:
        effective_bindings = bindings or ExecutionBindings()
        try:
            backend = self._backends[plan.backend_type]
        except KeyError as exc:
            raise ValueError(f"unsupported backend type: {plan.backend_type}") from exc
        return backend.render(plan, effective_bindings)

    def execute(self, plan: ExecutionPlan, *, bindings: ExecutionBindings | None = None) -> ExecutionResult:
        rendered = self.render(plan, bindings=bindings)
        return self._run_rendered(rendered, timeout=plan.timeout)

    def execute_batch(
        self,
        plan: ExecutionPlan,
        *,
        bindings_list: list[ExecutionBindings],
        on_each: Callable[[ExecutionResult], None] | None = None,
    ) -> list[ExecutionResult]:
        results: list[ExecutionResult] = []
        for bindings in bindings_list:
            result = self.execute(plan, bindings=bindings)
            results.append(result)
            if on_each is not None:
                on_each(result)
        return results

    def execute_stream(
        self,
        plan: ExecutionPlan,
        *,
        bindings: ExecutionBindings | None = None,
        on_chunk: Callable[[StreamChunk], None] | None = None,
    ) -> ExecutionResult:
        rendered = self.render(plan, bindings=bindings)
        return self._run_rendered_stream(rendered, timeout=plan.timeout, on_chunk=on_chunk)

    def _run_rendered(self, rendered: RenderedExecution, *, timeout: int) -> ExecutionResult:
        binary_stdin = (
            rendered.backend_type in {"ssh-linux", "windows-wsl"}
            and os.name == "nt"
            and rendered.stdin_text is not None
        )
        try:
            if binary_stdin:
                completed = subprocess.run(
                    list(rendered.argv),
                    cwd=self._local_cwd(rendered.cwd),
                    env=dict(rendered.env) if rendered.env else None,
                    input=rendered.stdin_text.encode("utf-8"),
                    text=False,
                    capture_output=True,
                    check=False,
                    timeout=timeout if timeout > 0 else None,
                )
                stdout = (
                    completed.stdout.decode("utf-8", errors="replace")
                    if isinstance(completed.stdout, bytes)
                    else completed.stdout
                )
                stderr = (
                    completed.stderr.decode("utf-8", errors="replace")
                    if isinstance(completed.stderr, bytes)
                    else completed.stderr
                )
            else:
                completed = subprocess.run(
                    list(rendered.argv),
                    cwd=self._local_cwd(rendered.cwd),
                    env=dict(rendered.env) if rendered.env else None,
                    input=rendered.stdin_text,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    capture_output=True,
                    check=False,
                    timeout=timeout if timeout > 0 else None,
                )
                stdout = completed.stdout
                stderr = completed.stderr
        except subprocess.TimeoutExpired as exc:
            return ExecutionResult(
                backend_type=rendered.backend_type,
                argv=rendered.argv,
                display_command=rendered.display_command,
                cwd=rendered.cwd,
                returncode=-1,
                stdout="",
                stderr=str(exc),
                ok=False,
                error=ExecutionError(
                    category="timeout",
                    message=f"Command timed out after {timeout}s: {rendered.display_command}",
                    retryable=True,
                    escalation="auto",
                ),
            )
        except FileNotFoundError as exc:
            return ExecutionResult(
                backend_type=rendered.backend_type,
                argv=rendered.argv,
                display_command=rendered.display_command,
                cwd=rendered.cwd,
                returncode=-1,
                stdout="",
                stderr=str(exc),
                ok=False,
                error=ExecutionError(
                    category="backend_unavailable",
                    message=f"Backend executable not found: {exc}",
                    retryable=False,
                    escalation="human",
                ),
            )
        except OSError as exc:
            return ExecutionResult(
                backend_type=rendered.backend_type,
                argv=rendered.argv,
                display_command=rendered.display_command,
                cwd=rendered.cwd,
                returncode=-1,
                stdout="",
                stderr=str(exc),
                ok=False,
                error=ExecutionError(
                    category="unknown",
                    message=str(exc),
                    retryable=False,
                    escalation="human",
                ),
            )

        if completed.returncode != 0:
            error = _classify_error(completed.returncode, stderr)
            return ExecutionResult(
                backend_type=rendered.backend_type,
                argv=rendered.argv,
                display_command=rendered.display_command,
                cwd=rendered.cwd,
                returncode=completed.returncode,
                stdout=stdout,
                stderr=stderr,
                ok=False,
                error=error,
            )

        return ExecutionResult(
            backend_type=rendered.backend_type,
            argv=rendered.argv,
            display_command=rendered.display_command,
            cwd=rendered.cwd,
            returncode=completed.returncode,
            stdout=stdout,
            stderr=stderr,
            ok=True,
        )

    def _run_rendered_stream(
        self,
        rendered: RenderedExecution,
        *,
        timeout: int,
        on_chunk: Callable[[StreamChunk], None] | None = None,
    ) -> ExecutionResult:
        binary_stdin = (
            rendered.backend_type in {"ssh-linux", "windows-wsl"}
            and os.name == "nt"
            and rendered.stdin_text is not None
        )

        def _reader(pipe: Any, q: queue.Queue[str], name: str) -> None:
            try:
                for line in iter(pipe.readline, b"" if binary_stdin else ""):
                    if not line:
                        break
                    if not isinstance(line, (bytes, str)):
                        break
                    text = line.decode("utf-8", errors="replace") if isinstance(line, bytes) else line
                    q.put(text)
                    if on_chunk is not None:
                        on_chunk(StreamChunk(stream=name, text=text))  # type: ignore[arg-type]
            finally:
                pipe.close()

        try:
            if binary_stdin:
                proc = subprocess.Popen(
                    list(rendered.argv),
                    cwd=self._local_cwd(rendered.cwd),
                    env=dict(rendered.env) if rendered.env else None,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                if rendered.stdin_text is not None:
                    proc.stdin.write(rendered.stdin_text.encode("utf-8"))
                proc.stdin.close()
            else:
                proc = subprocess.Popen(
                    list(rendered.argv),
                    cwd=self._local_cwd(rendered.cwd),
                    env=dict(rendered.env) if rendered.env else None,
                    stdin=subprocess.PIPE if rendered.stdin_text is not None else None,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
                if rendered.stdin_text is not None and proc.stdin is not None:
                    proc.stdin.write(rendered.stdin_text)
                    proc.stdin.close()

            stdout_q: queue.Queue[str] = queue.Queue()
            stderr_q: queue.Queue[str] = queue.Queue()
            t_out = threading.Thread(target=_reader, args=(proc.stdout, stdout_q, "stdout"))
            t_err = threading.Thread(target=_reader, args=(proc.stderr, stderr_q, "stderr"))
            t_out.start()
            t_err.start()

            t_out.join()
            t_err.join()
            returncode = proc.wait()

            stdout_lines: list[str] = []
            while not stdout_q.empty():
                stdout_lines.append(stdout_q.get_nowait())
            stderr_lines: list[str] = []
            while not stderr_q.empty():
                stderr_lines.append(stderr_q.get_nowait())

            stdout = "".join(stdout_lines)
            stderr = "".join(stderr_lines)
        except FileNotFoundError as exc:
            return ExecutionResult(
                backend_type=rendered.backend_type,
                argv=rendered.argv,
                display_command=rendered.display_command,
                cwd=rendered.cwd,
                returncode=-1,
                stdout="",
                stderr=str(exc),
                ok=False,
                error=ExecutionError(
                    category="backend_unavailable",
                    message=f"Backend executable not found: {exc}",
                    retryable=False,
                    escalation="human",
                ),
            )
        except OSError as exc:
            return ExecutionResult(
                backend_type=rendered.backend_type,
                argv=rendered.argv,
                display_command=rendered.display_command,
                cwd=rendered.cwd,
                returncode=-1,
                stdout="",
                stderr=str(exc),
                ok=False,
                error=ExecutionError(
                    category="unknown",
                    message=str(exc),
                    retryable=False,
                    escalation="human",
                ),
            )

        if returncode != 0:
            error = _classify_error(returncode, stderr)
            return ExecutionResult(
                backend_type=rendered.backend_type,
                argv=rendered.argv,
                display_command=rendered.display_command,
                cwd=rendered.cwd,
                returncode=returncode,
                stdout=stdout,
                stderr=stderr,
                ok=False,
                error=error,
            )

        return ExecutionResult(
            backend_type=rendered.backend_type,
            argv=rendered.argv,
            display_command=rendered.display_command,
            cwd=rendered.cwd,
            returncode=returncode,
            stdout=stdout,
            stderr=stderr,
            ok=True,
        )

    @staticmethod
    def _local_cwd(value: Path | str | None) -> str | None:
        if value is None:
            return None
        if isinstance(value, Path):
            return str(value)
        rendered = str(value)
        if rendered.startswith("/"):
            return rendered
        if len(rendered) >= 2 and rendered[0].isalpha() and rendered[1] == ":":
            return rendered
        return rendered


class CommandRunner:
    def run(
        self,
        argv: list[str] | tuple[str, ...],
        *,
        cwd: Path | str | None = None,
        env: Mapping[str, str] | None = None,
        timeout: int | None = None,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            list(argv),
            cwd=self._local_cwd(cwd),
            env=dict(env) if env else None,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
            timeout=timeout,
        )

    @staticmethod
    def _local_cwd(value: Path | str | None) -> str | None:
        if value is None:
            return None
        return str(value)


class ConcurrentExecutor:
    """Execute multiple CommandSpecs in parallel via ThreadPoolExecutor."""

    def __init__(self, runner: BackendRunner, max_workers: int = 4) -> None:
        self._runner = runner
        self._max_workers = max_workers
        self._executor: ThreadPoolExecutor | None = None

    def _get_executor(self) -> ThreadPoolExecutor:
        if self._executor is None:
            self._executor = ThreadPoolExecutor(max_workers=self._max_workers)
        return self._executor

    def execute(self, spec: CommandSpec) -> ExecutionResult:
        return self._runner.execute_spec(spec)

    def execute_parallel(self, specs: list[CommandSpec]) -> list[ExecutionResult]:
        executor = self._get_executor()
        futures = [executor.submit(self.execute, spec) for spec in specs]
        return [f.result() for f in futures]

    def shutdown(self, wait: bool = True) -> None:
        if self._executor is not None:
            self._executor.shutdown(wait=wait)
            self._executor = None

    def __enter__(self) -> ConcurrentExecutor:
        return self

    def __exit__(self, *exc: object) -> None:
        self.shutdown()
