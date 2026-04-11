#!/usr/bin/env python3
"""Shared target executor for repository-owned 1Panel operations."""

from __future__ import annotations

import json
import subprocess
from typing import Any

from agentplane.runtime.platform import default_linux_backend

from .env_targets import TargetConfig, build_api_request_command


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, text=True, capture_output=True, check=False)


class TargetExecutor:
    def __init__(self, target: TargetConfig) -> None:
        self.target = target

    def api_request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        *,
        query: dict[str, Any] | None = None,
    ) -> Any:
        command = build_api_request_command(self.target, method, path, body=body, query=query)

        if self.target.mode == "local":
            result = run_command(command)
        else:
            result = run_command(self.target.build_ssh_target().ssh_args_for_argv(command))

        if result.returncode != 0:
            raise RuntimeError(result.stdout.strip() or result.stderr.strip() or f"API command failed: {method} {path}")

        payload = json.loads(result.stdout)
        body_payload = payload["body"]
        if not isinstance(body_payload, dict) or body_payload.get("code") != 200:
            raise RuntimeError(json.dumps(payload, ensure_ascii=False))
        return body_payload["data"]

    def shell(self, command: str) -> str:
        if self.target.mode == "local":
            backend = self.target.linux_backend or default_linux_backend()
            result = run_command(backend.shell_argv(command))
        else:
            result = run_command(self.target.build_ssh_target().ssh_args_for_shell(command))
        if result.returncode != 0:
            raise RuntimeError(result.stdout.strip() or result.stderr.strip() or f"Shell command failed: {command}")
        return result.stdout.strip()
