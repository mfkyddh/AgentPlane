from __future__ import annotations

import shlex
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Mapping

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
class CommandSpec:
    """Unified command specification, replaces ExecutionPlan + ExecutionBindings."""

    backend_type: BackendType
    argv: tuple[str, ...]
    cwd: Path | str | None = None
    env: Mapping[str, str] = field(default_factory=dict)
    stdin_text: str | None = None
    timeout: int = 120
    expected_outputs: tuple[str, ...] = ()
    capabilities: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "backend_type": self.backend_type,
            "argv": list(self.argv),
            "cwd": None if self.cwd is None else str(self.cwd),
            "env": dict(self.env),
            "expects_stdin": self.stdin_text is not None,
            "expected_outputs": list(self.expected_outputs),
            "capabilities": list(self.capabilities),
            "timeout": self.timeout,
        }
        if self.metadata:
            serializable: dict[str, Any] = {}
            for key, value in self.metadata.items():
                if isinstance(value, (str, int, float, bool, type(None))):
                    serializable[key] = value
                elif isinstance(value, Path):
                    serializable[key] = str(value)
            if serializable:
                payload["metadata"] = serializable
        return payload


@dataclass(frozen=True)
class CommandStep:
    """A named execution step with a CommandSpec."""

    key: str
    spec: CommandSpec


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
    hint: str | None = None
    diagnostic: dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "category": self.category,
            "message": self.message,
            "retryable": self.retryable,
            "escalation": self.escalation,
        }
        if self.hint:
            payload["hint"] = self.hint
        if self.diagnostic:
            payload["diagnostic"] = dict(self.diagnostic)
        return payload


def _classify_error(returncode: int, stderr: str) -> ExecutionError:
    stderr_lower = stderr.lower()
    if "permission denied" in stderr_lower or "authentication" in stderr_lower:
        return ExecutionError(
            category="auth",
            message=f"Authentication or permission failure (exit {returncode}): {stderr.strip()}",
            retryable=False,
            escalation="human",
            hint="检查 SSH 密钥或 API 凭证是否正确配置",
            diagnostic={"returncode": returncode, "stderr_tail": stderr.strip()[-500:]},
        )
    if any(
        token in stderr_lower
        for token in ("connection refused", "no route to host", "network is unreachable", "could not resolve hostname")
    ):
        return ExecutionError(
            category="network",
            message=f"Network failure (exit {returncode}): {stderr.strip()}",
            retryable=True,
            escalation="auto",
            hint="检查目标主机是否可达、SSH 端口是否开放",
            diagnostic={"returncode": returncode, "stderr_tail": stderr.strip()[-500:]},
        )
    if any(token in stderr_lower for token in ("connection timed out", "timed out", "timeout")):
        return ExecutionError(
            category="timeout",
            message=f"Operation timed out (exit {returncode}): {stderr.strip()}",
            retryable=True,
            escalation="auto",
            hint="操作超时，可能是网络延迟或命令执行时间过长",
            diagnostic={"returncode": returncode, "stderr_tail": stderr.strip()[-500:]},
        )
    if any(token in stderr_lower for token in ("could not resolve hostname", "ssh: connect to host", "no route to host")):
        return ExecutionError(
            category="backend_unavailable",
            message=f"SSH connection failed (exit {returncode}): {stderr.strip()}",
            retryable=True,
            escalation="auto",
            hint="检查 SSH 配置和目标主机状态",
            diagnostic={"returncode": returncode, "stderr_tail": stderr.strip()[-500:]},
        )
    if any(token in stderr_lower for token in ("command not found", "no such file or directory", "not found")):
        return ExecutionError(
            category="command",
            message=f"Command not found or invalid (exit {returncode}): {stderr.strip()}",
            retryable=False,
            escalation="none",
            hint="检查命令路径和依赖是否已安装",
            diagnostic={"returncode": returncode, "stderr_tail": stderr.strip()[-500:]},
        )
    return ExecutionError(
        category="command",
        message=f"Command failed with exit code {returncode}: {stderr.strip()}",
        retryable=returncode == 1,
        escalation="none",
        hint="查看 stderr 输出定位具体错误",
        diagnostic={"returncode": returncode, "stderr_tail": stderr.strip()[-500:]},
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
