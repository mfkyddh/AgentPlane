#!/usr/bin/env python3
"""Shared target executor for repository-owned 1Panel operations."""

from __future__ import annotations

import hashlib
import json
import ssl
import time as _time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from agentplane.runtime.platform import default_linux_backend

from .env_targets import TargetConfig, run_command


class TargetExecutor:
    def __init__(self, target: TargetConfig) -> None:
        self.target = target
        self._remote_client: Any = None

    def api_request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        *,
        query: dict[str, Any] | None = None,
    ) -> Any:
        if self.target.mode == "local":
            return self._local_api_request(method, path, body, query=query)
        return self._remote_api_request(method, path, body, query=query)

    def _local_api_request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        *,
        query: dict[str, Any] | None = None,
    ) -> Any:
        from .client import send_signed_request

        config = self.target.api_config
        body_bytes = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
        response = send_signed_request(config, method, path, body_bytes=body_bytes, query=query)
        payload = response["body"]
        if not isinstance(payload, dict) or payload.get("code") != 200:
            raise RuntimeError(json.dumps(response, ensure_ascii=False))
        return payload["data"]

    def _get_remote_client(self) -> Any:
        if self._remote_client is None:
            from agentplane.ssh import RemoteAPIClient

            ssh_target = self.target.build_ssh_target()
            pool = ssh_target.connection_pool
            if pool is None:
                from agentplane.ssh import SSHConnectionPool

                pool = SSHConnectionPool(ssh_target.config_path)
            self._remote_client = RemoteAPIClient(
                pool, ssh_target.alias, remote_port=self.target.remote_port
            )
        return self._remote_client

    def _remote_api_request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        *,
        query: dict[str, Any] | None = None,
    ) -> Any:
        config = self.target.api_config
        client = self._get_remote_client()
        local_port = client.local_port

        request_url = f"http://127.0.0.1:{local_port}{path}"
        if query:
            encoded = urllib.parse.urlencode(
                {k: str(v) for k, v in query.items() if v is not None and v != ""}
            )
            sep = "&" if urllib.parse.urlparse(request_url).query else "?"
            request_url = f"{request_url}{sep}{encoded}"

        timestamp = str(int(_time.time()))
        token = hashlib.md5(f"1panel{config.api_key}{timestamp}".encode("utf-8")).hexdigest()
        base_uri = urllib.parse.urlparse(config.base_url)
        origin = f"{base_uri.scheme}://{base_uri.netloc}"

        body_json = json.dumps(body, ensure_ascii=False) if body is not None else None
        body_bytes = body_json.encode("utf-8") if body_json else None

        headers = {
            "Accept": "application/json, text/plain, text/event-stream",
            "Content-Type": "application/json",
            "1Panel-Token": token,
            "1Panel-Timestamp": timestamp,
            "Host": base_uri.netloc,
        }
        if config.security_entrance:
            headers["Origin"] = origin
            headers["Referer"] = f"{origin}/{config.security_entrance}/"

        ctx = ssl._create_unverified_context() if config.skip_tls_verify else None
        req = urllib.request.Request(request_url, data=body_bytes, method=method.upper(), headers=headers)
        try:
            resp = urllib.request.urlopen(req, timeout=config.timeout_seconds, context=ctx)
            response = json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            response = json.loads(exc.read().decode(errors="replace"))
        body_payload = response.get("body", response)
        if not isinstance(body_payload, dict) or body_payload.get("code") != 200:
            raise RuntimeError(json.dumps(response, ensure_ascii=False))
        return body_payload["data"]

    def shell(self, command: str) -> str:
        if self.target.mode == "local":
            backend = self.target.linux_backend or default_linux_backend()
            result = run_command(backend.shell_argv(command))
        else:
            result = run_command(self.target.build_ssh_target().local_ssh_args_for_shell(command))
        if result.returncode != 0:
            raise RuntimeError(result.stdout.strip() or result.stderr.strip() or f"Shell command failed: {command}")
        return result.stdout.strip()
