#!/usr/bin/env python3
"""Shared target executor for repository-owned 1Panel operations."""

from __future__ import annotations

import base64
import hashlib
import json
import time as _time
import urllib.parse
from typing import Any

from agentplane.runtime.platform import default_linux_backend

from .env_targets import TargetConfig, run_command


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

    def _remote_api_request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        *,
        query: dict[str, Any] | None = None,
    ) -> Any:
        config = self.target.api_config
        body_json = json.dumps(body, ensure_ascii=False) if body is not None else None
        body_bytes = body_json.encode("utf-8") if body_json else None

        request_url = urllib.parse.urljoin(f"{config.connect_base_url}/", path.lstrip("/"))
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

        headers = {
            "Accept": "application/json, text/plain, text/event-stream",
            "Content-Type": "application/json",
            "1Panel-Token": token,
            "1Panel-Timestamp": timestamp,
            "Content-Length": str(len(body_bytes or b"")),
            "Host": base_uri.netloc,
        }
        if config.security_entrance:
            headers["Origin"] = origin
            headers["Referer"] = f"{origin}/{config.security_entrance}/"

        payload_data = {
            "url": request_url,
            "method": method.upper(),
            "headers": headers,
            "body_json": body_json,
            "timeout": config.timeout_seconds,
            "skip_tls": config.skip_tls_verify and request_url.startswith("https://"),
        }

        script_content = (
            "import json,sys,urllib.request,urllib.error,ssl\n"
            "d=json.loads(sys.argv[1])\n"
            "ctx=ssl._create_unverified_context() if d['skip_tls'] else None\n"
            "bd=d['body_json'].encode() if d['body_json'] else None\n"
            "req=urllib.request.Request(d['url'],data=bd,method=d['method'],headers=d['headers'])\n"
            "try:\n"
            "    r=urllib.request.urlopen(req,timeout=d['timeout'],context=ctx)\n"
            "    print(json.dumps({'status':r.status,'body':json.loads(r.read().decode())}))\n"
            "except urllib.error.HTTPError as e:\n"
            "    print(json.dumps({'status':e.code,'body':json.loads(e.read().decode(errors='replace'))}))\n"
        )
        script_b64 = base64.b64encode(script_content.encode("utf-8")).decode("ascii")
        inline_script = f"import base64;exec(base64.b64decode('{script_b64}').decode())"
        payload_json = json.dumps(payload_data, ensure_ascii=False)
        ssh_target = self.target.build_ssh_target()
        result = run_command(
            ssh_target.local_ssh_args_for_argv(["python3", "-c", inline_script, payload_json])
        )
        if result.returncode != 0:
            raise RuntimeError(
                result.stdout.strip() or result.stderr.strip() or f"API command failed: {method} {path}"
            )
        response = json.loads(result.stdout)
        body_payload = response["body"]
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
