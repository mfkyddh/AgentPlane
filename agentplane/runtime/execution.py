from __future__ import annotations

import os
import queue
import shlex
import shutil
import subprocess
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal, Mapping

BackendType = Literal["linux-native", "windows-wsl", "macos-lima", "ssh-linux"]
ErrorCategory = Literal["backend_unavailable", "network", "auth", "command", "timeout", "unknown"]
EscalationLevel = Literal["none", "human", "auto"]


def shell_join(argv: tuple[str, ...] | list[str]) -> str:
    return " ".join(shlex.quote(part) for part in argv)


def env_prefixed_command(argv: tuple[str, ...], env: Mapping[str, str]) -> str:
    prefix = " ".join(f"{key}={shlex.quote(value)}" for key, value in env.items())
    command = shell_join(argv)
    if not prefix:
        return command
    return f"{prefix} {command}"


def require_local_executable(executable: str) -> None:
    if "/" in executable or "\\" in executable:
        candidate = Path(executable)
        if candidate.exists():
            return
    if shutil.which(executable) is None:
        raise ValueError(f"missing required executable for backend runner: {executable}")


@dataclass(frozen=True)
class ExecutionPlan:
    backend_type: BackendType
    cwd_ref: str
    argv: tuple[str, ...]
    env_refs: tuple[str, ...]
    input_refs: tuple[str, ...]
    expected_outputs: tuple[str, ...]
    capabilities: tuple[str, ...]
    timeout: int

    def to_payload(self) -> dict[str, Any]:
        return {
            "backend_type": self.backend_type,
            "cwd_ref": self.cwd_ref,
            "argv": list(self.argv),
            "env_refs": list(self.env_refs),
            "input_refs": list(self.input_refs),
            "expected_outputs": list(self.expected_outputs),
            "capabilities": list(self.capabilities),
            "timeout": self.timeout,
        }


@dataclass(frozen=True)
class StreamChunk:
    stream: Literal["stdout", "stderr"]
    text: str


@dataclass(frozen=True)
class ExecutionBindings:
    cwd_values: Mapping[str, Path | str | None] = field(default_factory=dict)
    env_values: Mapping[str, Mapping[str, str]] = field(default_factory=dict)
    input_values: Mapping[str, str] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def resolve_cwd(self, ref: str) -> Path | str | None:
        if ref in self.cwd_values:
            return self.cwd_values[ref]
        if not ref:
            return None
        return ref

    def resolve_env(self, refs: tuple[str, ...]) -> dict[str, str]:
        merged: dict[str, str] = {}
        for ref in refs:
            values = self.env_values.get(ref)
            if values is None:
                raise ValueError(f"missing env binding for execution ref: {ref}")
            merged.update(values)
        return merged

    def resolve_input(self, refs: tuple[str, ...]) -> str | None:
        if not refs:
            return None
        chunks: list[str] = []
        for ref in refs:
            value = self.input_values.get(ref)
            if value is None:
                raise ValueError(f"missing input binding for execution ref: {ref}")
            chunks.append(value)
        return "".join(chunks)


@dataclass(frozen=True)
class PlannedExecutionStep:
    key: str
    plan: ExecutionPlan
    bindings: ExecutionBindings = field(default_factory=ExecutionBindings)


@dataclass(frozen=True)
class RenderedExecution:
    backend_type: BackendType
    argv: tuple[str, ...]
    display_command: str
    cwd: Path | str | None
    env: Mapping[str, str]
    stdin_text: str | None
    expected_outputs: tuple[str, ...]
    capabilities: tuple[str, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "backend_type": self.backend_type,
            "argv": list(self.argv),
            "display_command": self.display_command,
            "cwd": None if self.cwd is None else str(self.cwd),
            "env": dict(self.env),
            "expects_stdin": self.stdin_text is not None,
            "expected_outputs": list(self.expected_outputs),
            "capabilities": list(self.capabilities),
        }
        if self.metadata:
            payload["metadata"] = dict(self.metadata)
        return payload


@dataclass(frozen=True)
class ExecutionError:
    category: ErrorCategory
    message: str
    retryable: bool
    escalation: EscalationLevel

    def to_payload(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "message": self.message,
            "retryable": self.retryable,
            "escalation": self.escalation,
        }


def _classify_error(returncode: int, stderr: str) -> ExecutionError:
    stderr_lower = stderr.lower()
    if "permission denied" in stderr_lower or "authentication" in stderr_lower:
        return ExecutionError(
            category="auth",
            message=f"Authentication or permission failure (exit {returncode}): {stderr.strip()}",
            retryable=False,
            escalation="human",
        )
    if any(token in stderr_lower for token in ("connection refused", "no route to host", "network is unreachable", "could not resolve hostname")):
        return ExecutionError(
            category="network",
            message=f"Network failure (exit {returncode}): {stderr.strip()}",
            retryable=True,
            escalation="auto",
        )
    if any(token in stderr_lower for token in ("command not found", "no such file or directory", "not found")):
        return ExecutionError(
            category="command",
            message=f"Command not found or invalid (exit {returncode}): {stderr.strip()}",
            retryable=False,
            escalation="none",
        )
    return ExecutionError(
        category="command",
        message=f"Command failed with exit code {returncode}: {stderr.strip()}",
        retryable=returncode == 1,  # exit 1 often signals soft/config errors
        escalation="none",
    )


@dataclass(frozen=True)
class ExecutionResult:
    backend_type: BackendType
    argv: tuple[str, ...]
    display_command: str
    cwd: Path | str | None
    returncode: int
    stdout: str
    stderr: str
    ok: bool
    error: ExecutionError | None = None

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "backend_type": self.backend_type,
            "argv": list(self.argv),
            "display": self.display_command,
            "cwd": None if self.cwd is None else str(self.cwd),
            "returncode": self.returncode,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "ok": self.ok,
        }
        if self.error is not None:
            payload["error"] = self.error.to_payload()
        return payload


class BackendRunner:
    def __init__(self, backends: Mapping[BackendType, Any]) -> None:
        self._backends = dict(backends)

    def render(self, plan: ExecutionPlan, *, bindings: ExecutionBindings | None = None) -> RenderedExecution:
        effective_bindings = bindings or ExecutionBindings()
        try:
            backend = self._backends[plan.backend_type]
        except KeyError as exc:
            raise ValueError(f"unsupported backend type: {plan.backend_type}") from exc
        return backend.render(plan, effective_bindings)

    def execute(self, plan: ExecutionPlan, *, bindings: ExecutionBindings | None = None) -> ExecutionResult:
        rendered = self.render(plan, bindings=bindings)
        binary_stdin = rendered.backend_type in {"ssh-linux", "windows-wsl"} and os.name == "nt" and rendered.stdin_text is not None
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
                    timeout=plan.timeout if plan.timeout > 0 else None,
                )
                stdout = completed.stdout.decode("utf-8", errors="replace") if isinstance(completed.stdout, bytes) else completed.stdout
                stderr = completed.stderr.decode("utf-8", errors="replace") if isinstance(completed.stderr, bytes) else completed.stderr
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
                    timeout=plan.timeout if plan.timeout > 0 else None,
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
                    message=f"Command timed out after {plan.timeout}s: {rendered.display_command}",
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

    def execute_stream(
        self,
        plan: ExecutionPlan,
        *,
        bindings: ExecutionBindings | None = None,
        on_chunk: Callable[[StreamChunk], None] | None = None,
    ) -> ExecutionResult:
        rendered = self.render(plan, bindings=bindings)
        binary_stdin = rendered.backend_type in {"ssh-linux", "windows-wsl"} and os.name == "nt" and rendered.stdin_text is not None

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
