from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


def load_shell_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class CloudflareError(RuntimeError):
    pass


class CloudflareClient:
    def __init__(self, token: str) -> None:
        self.token = token

    def request(
        self,
        method: str,
        path: str,
        *,
        query: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"https://api.cloudflare.com/client/v4{path}"
        if query:
            url = f"{url}?{urllib.parse.urlencode(query)}"
        body_bytes = None
        headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
        if body is not None:
            body_bytes = json.dumps(body, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(url, data=body_bytes, method=method.upper(), headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise CloudflareError(f"Cloudflare API {method} {path} failed: {exc.code} {error_body}") from exc
        if not payload.get("success"):
            raise CloudflareError(f"Cloudflare API {method} {path} failed: {json.dumps(payload, ensure_ascii=False)}")
        return payload

    def verify_account_token(self, account_id: str) -> dict[str, Any]:
        payload = self.request("GET", f"/accounts/{account_id}/tokens/verify")
        result = payload.get("result")
        if not isinstance(result, dict):
            raise CloudflareError(f"Cloudflare token verify returned unexpected payload for account {account_id}")
        return result

    def get_zone_id(self, zone_name: str) -> str:
        payload = self.request("GET", "/zones", query={"name": zone_name})
        result = payload.get("result", [])
        if not result:
            raise CloudflareError(f"Cloudflare zone not found: {zone_name}")
        return str(result[0]["id"])

    def find_dns_record(self, *, zone_name: str, record_name: str, record_type: str) -> dict[str, Any] | None:
        zone_id = self.get_zone_id(zone_name)
        payload = self.request(
            "GET",
            f"/zones/{zone_id}/dns_records",
            query={"type": record_type, "name": record_name},
        )
        result = payload.get("result", [])
        if not result:
            return None
        first = result[0]
        return first if isinstance(first, dict) else None

    def ensure_dns_record(
        self,
        *,
        zone_name: str,
        record_name: str,
        record_type: str,
        content: str,
        proxied: bool,
    ) -> dict[str, Any]:
        zone_id = self.get_zone_id(zone_name)
        existing_payload = self.request(
            "GET",
            f"/zones/{zone_id}/dns_records",
            query={"type": record_type, "name": record_name},
        )
        existing = existing_payload.get("result", [])
        body = {"type": record_type, "name": record_name, "content": content, "proxied": proxied}
        if not existing:
            created = self.request("POST", f"/zones/{zone_id}/dns_records", body=body)["result"]
            return {"changed": True, "record": created, "action": "created"}

        record = existing[0]
        if record.get("content") == content and bool(record.get("proxied")) == proxied:
            return {"changed": False, "record": record, "action": "unchanged"}

        updated = self.request("PUT", f"/zones/{zone_id}/dns_records/{record['id']}", body=body)["result"]
        return {"changed": True, "record": updated, "action": "updated"}
