from __future__ import annotations

import shlex
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Mapping


BackendType = Literal["linux-native", "windows-wsl", "macos-lima", "ssh-linux"]


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
class ExecutionResult:
    backend_type: BackendType
    argv: tuple[str, ...]
    display_command: str
    cwd: Path | str | None
    returncode: int
    stdout: str
    stderr: str
    ok: bool

    def to_payload(self) -> dict[str, Any]:
        return {
            "backend_type": self.backend_type,
            "argv": list(self.argv),
            "display": self.display_command,
            "cwd": None if self.cwd is None else str(self.cwd),
            "returncode": self.returncode,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "ok": self.ok,
        }


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
        completed = subprocess.run(
            list(rendered.argv),
            cwd=self._local_cwd(rendered.cwd),
            env=dict(rendered.env) if rendered.env else None,
            input=rendered.stdin_text,
            text=True,
            capture_output=True,
            check=False,
            timeout=plan.timeout if plan.timeout > 0 else None,
        )
        return ExecutionResult(
            backend_type=rendered.backend_type,
            argv=rendered.argv,
            display_command=rendered.display_command,
            cwd=rendered.cwd,
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            ok=completed.returncode == 0,
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
