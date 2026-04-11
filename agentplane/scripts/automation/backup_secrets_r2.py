from __future__ import annotations

import hashlib
import hmac
import json
import os
import shutil
import subprocess
import tarfile
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from agentplane.runtime.workspace import resolve_workspace_from_repo
from agentplane.scripts.onepanel.client import load_config as load_onepanel_config
from agentplane.scripts.onepanel.client import send_signed_request


WORKSPACE = resolve_workspace_from_repo(Path(__file__).resolve().parents[3])
REPO_ROOT = WORKSPACE.control_root
DEFAULT_ENV_FILE = Path("secrets/services/secrets-backup.r2.wsl.env")
DEFAULT_TASK_ENV_FILE = Path("secrets/services/onepanel-api.wsl.env")
DEFAULT_SOURCE_DIR = WORKSPACE.private_root
DEFAULT_STATE_FILE = Path("/data/agentplane/secrets-backup/state.json")
DEFAULT_TMP_DIR = Path("/tmp/agentplane-secrets-backup")
DEFAULT_BUCKET = "AgentPlane_Backups"
DEFAULT_PREFIX = "backups/agentplane/secrets-main"
DEFAULT_KEEP_COUNT = 5
TASK_NAME = "wsl-agentplane-secrets-backup"
TASK_SPEC = "0 */5 * * *"
TASK_COMMAND = (
    f"cd {REPO_ROOT} && "
    "uv run python -m agentplane.cli host automation apply wsl --name wsl-agentplane-secrets-backup --operation run --execute"
)


@dataclass(frozen=True)
class BackupConfig:
    source_dir: Path
    state_file: Path
    tmp_dir: Path
    bucket: str
    endpoint: str
    prefix: str
    access_key_id: str
    secret_access_key: str
    password: str
    keep_count: int


def load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def load_config(env_file: Path) -> BackupConfig:
    env = load_env_file(env_file)
    return BackupConfig(
        source_dir=Path(env.get("SECRETS_BACKUP_SOURCE_DIR", str(DEFAULT_SOURCE_DIR))),
        state_file=Path(env.get("SECRETS_BACKUP_STATE_FILE", str(DEFAULT_STATE_FILE))),
        tmp_dir=Path(env.get("SECRETS_BACKUP_TMP_DIR", str(DEFAULT_TMP_DIR))),
        bucket=env.get("SECRETS_BACKUP_BUCKET", DEFAULT_BUCKET),
        endpoint=env["SECRETS_BACKUP_ENDPOINT"].rstrip("/"),
        prefix=env.get("SECRETS_BACKUP_PREFIX", DEFAULT_PREFIX).strip("/"),
        access_key_id=env["SECRETS_BACKUP_ACCESS_KEY_ID"],
        secret_access_key=env["SECRETS_BACKUP_SECRET_ACCESS_KEY"],
        password=env["SECRETS_BACKUP_PASSWORD"],
        keep_count=max(1, int(env.get("SECRETS_BACKUP_KEEP_COUNT", str(DEFAULT_KEEP_COUNT)))),
    )


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _stamp_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _read_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_state(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _sorted_files(source_dir: Path) -> list[Path]:
    return sorted(path for path in source_dir.rglob("*") if path.is_file())


def _hash_scan(source_dir: Path, files: list[Path]) -> str:
    digest = hashlib.sha256()
    for file_path in files:
        stat = file_path.stat()
        relative = file_path.relative_to(source_dir).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(stat.st_size).encode("ascii"))
        digest.update(b"\0")
        digest.update(str(stat.st_mtime_ns).encode("ascii"))
        digest.update(b"\0")
        digest.update(str(stat.st_mode).encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()


def _hash_content(source_dir: Path, files: list[Path]) -> str:
    digest = hashlib.sha256()
    for file_path in files:
        stat = file_path.stat()
        relative = file_path.relative_to(source_dir).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(stat.st_mode).encode("ascii"))
        digest.update(b"\0")
        with file_path.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
        digest.update(b"\0")
    return digest.hexdigest()


def _make_archive(source_dir: Path, tar_path: Path) -> None:
    tar_path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tar_path, "w:gz") as archive:
        archive.add(source_dir, arcname=source_dir.name)


def encrypt_file_with_openssl(input_path: Path, output_path: Path, password: str) -> None:
    env = os.environ.copy()
    env["AGENTPLANE_SECRETS_BACKUP_PASSWORD"] = password
    result = subprocess.run(
        [
            "openssl",
            "enc",
            "-aes-256-cbc",
            "-pbkdf2",
            "-salt",
            "-in",
            str(input_path),
            "-out",
            str(output_path),
            "-pass",
            "env:AGENTPLANE_SECRETS_BACKUP_PASSWORD",
        ],
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "openssl encryption failed")


class R2Client:
    def __init__(self, endpoint: str, access_key_id: str, secret_access_key: str) -> None:
        parsed = urllib.parse.urlparse(endpoint)
        self.endpoint = endpoint.rstrip("/")
        self.host = parsed.netloc
        self.scheme = parsed.scheme
        self.region = "auto"
        self.service = "s3"
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key

    def _sign(self, timestamp: str, date_scope: str, canonical_request: str) -> str:
        credential_scope = f"{date_scope}/{self.region}/{self.service}/aws4_request"
        string_to_sign = "\n".join(
            [
                "AWS4-HMAC-SHA256",
                timestamp,
                credential_scope,
                hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
            ]
        )

        def _hmac(key: bytes, value: str) -> bytes:
            return hmac.new(key, value.encode("utf-8"), hashlib.sha256).digest()

        k_date = _hmac(("AWS4" + self.secret_access_key).encode("utf-8"), date_scope)
        k_region = _hmac(k_date, self.region)
        k_service = _hmac(k_region, self.service)
        k_signing = _hmac(k_service, "aws4_request")
        signature = hmac.new(k_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
        return (
            "AWS4-HMAC-SHA256 "
            f"Credential={self.access_key_id}/{credential_scope}, "
            "SignedHeaders=host;x-amz-content-sha256;x-amz-date, "
            f"Signature={signature}"
        )

    def _request(
        self,
        *,
        method: str,
        bucket: str,
        key: str = "",
        query: dict[str, str] | None = None,
        body: bytes = b"",
        content_type: str | None = None,
    ) -> bytes:
        timestamp = _utc_now().strftime("%Y%m%dT%H%M%SZ")
        date_scope = timestamp[:8]
        canonical_uri = "/" + "/".join(
            urllib.parse.quote(part, safe="") for part in ([bucket] + [item for item in key.split("/") if item])
        )
        query_items = sorted((query or {}).items())
        canonical_query = urllib.parse.urlencode(query_items, quote_via=urllib.parse.quote, safe="")
        payload_hash = hashlib.sha256(body).hexdigest()
        canonical_headers = f"host:{self.host}\n" f"x-amz-content-sha256:{payload_hash}\n" f"x-amz-date:{timestamp}\n"
        canonical_request = "\n".join(
            [
                method.upper(),
                canonical_uri,
                canonical_query,
                canonical_headers,
                "host;x-amz-content-sha256;x-amz-date",
                payload_hash,
            ]
        )
        headers = {
            "Host": self.host,
            "x-amz-content-sha256": payload_hash,
            "x-amz-date": timestamp,
            "Authorization": self._sign(timestamp, date_scope, canonical_request),
        }
        if content_type:
            headers["Content-Type"] = content_type
        url = f"{self.endpoint}{canonical_uri}"
        if canonical_query:
            url = f"{url}?{canonical_query}"
        request = urllib.request.Request(url, data=body if body else None, method=method.upper(), headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read()
        except urllib.error.HTTPError as exc:  # pragma: no cover - exercised in live verification
            body_text = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"R2 {method.upper()} failed: {exc.code} {body_text}") from exc

    def put_object(self, *, bucket: str, key: str, file_path: Path) -> dict[str, str]:
        body = file_path.read_bytes()
        self._request(method="PUT", bucket=bucket, key=key, body=body, content_type="application/octet-stream")
        return {"bucket": bucket, "key": key}

    def list_objects(self, *, bucket: str, prefix: str) -> list[dict[str, object]]:
        body = self._request(method="GET", bucket=bucket, query={"list-type": "2", "prefix": prefix})
        root = ET.fromstring(body.decode("utf-8"))
        items: list[dict[str, object]] = []
        for entry in root.findall(".//{*}Contents"):
            key = entry.findtext("{*}Key", "")
            size_text = entry.findtext("{*}Size", "0")
            items.append({"key": key, "size": int(size_text)})
        return items

    def delete_object(self, *, bucket: str, key: str) -> None:
        self._request(method="DELETE", bucket=bucket, key=key)


def _cleanup_tmp_dir(tmp_dir: Path) -> None:
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _object_key(prefix: str, now: datetime, content_fingerprint: str) -> str:
    return f"{prefix}/agentplane-secrets-{_stamp_utc(now)}-{content_fingerprint[:12]}.tar.gz.enc"


def _prune_old_backups(client: Any, bucket: str, prefix: str, keep_count: int) -> list[str]:
    objects = client.list_objects(bucket=bucket, prefix=prefix)
    keys = sorted((str(item["key"]) for item in objects if str(item["key"]).endswith(".tar.gz.enc")), reverse=True)
    deleted: list[str] = []
    for key in keys[keep_count:]:
        client.delete_object(bucket=bucket, key=key)
        deleted.append(key)
    return deleted


def run_backup(
    config: BackupConfig,
    *,
    client: Any | None = None,
    now: datetime | None = None,
    encrypt_file: Callable[[Path, Path, str], None] = encrypt_file_with_openssl,
) -> dict[str, Any]:
    timestamp = now or _utc_now()
    payload: dict[str, Any] = {
        "status": "failed_runtime",
        "source_dir": str(config.source_dir),
        "state_file": str(config.state_file),
        "tmp_dir": str(config.tmp_dir),
        "bucket": config.bucket,
        "prefix": config.prefix,
        "object_key": None,
        "last_uploaded_key": None,
        "deleted_old_backups": 0,
    }

    if not config.source_dir.is_dir():
        payload["status"] = "failed_precheck"
        payload["reason"] = f"source directory does not exist: {config.source_dir}"
        return payload

    client = client or R2Client(config.endpoint, config.access_key_id, config.secret_access_key)
    _cleanup_tmp_dir(config.tmp_dir)
    config.tmp_dir.mkdir(parents=True, exist_ok=True)
    tar_path = config.tmp_dir / "secrets.tar.gz"
    encrypted_path = config.tmp_dir / "secrets.tar.gz.enc"

    try:
        files = _sorted_files(config.source_dir)
        scan_fingerprint = _hash_scan(config.source_dir, files)
        state = _read_state(config.state_file)
        payload["scan_fingerprint"] = scan_fingerprint
        payload["last_uploaded_key"] = state.get("last_uploaded_key")
        if state.get("scan_fingerprint") == scan_fingerprint:
            payload["status"] = "ok_no_changes"
            payload["content_fingerprint"] = state.get("content_fingerprint")
            return payload

        content_fingerprint = _hash_content(config.source_dir, files)
        payload["content_fingerprint"] = content_fingerprint
        if state.get("content_fingerprint") == content_fingerprint:
            state["scan_fingerprint"] = scan_fingerprint
            _write_state(config.state_file, state)
            payload["status"] = "ok_no_changes"
            return payload

        _make_archive(config.source_dir, tar_path)
        encrypt_file(tar_path, encrypted_path, config.password)
        object_key = _object_key(config.prefix, timestamp, content_fingerprint)
        client.put_object(bucket=config.bucket, key=object_key, file_path=encrypted_path)
        deleted = _prune_old_backups(client, config.bucket, config.prefix, config.keep_count)
        state = {
            "scan_fingerprint": scan_fingerprint,
            "content_fingerprint": content_fingerprint,
            "last_uploaded_key": object_key,
            "last_uploaded_at": _iso_utc(timestamp),
        }
        _write_state(config.state_file, state)
        payload.update(
            {
                "status": "ok_uploaded",
                "object_key": object_key,
                "last_uploaded_key": object_key,
                "deleted_old_backups": len(deleted),
                "deleted_keys": deleted,
            }
        )
        return payload
    except Exception as exc:
        payload["reason"] = str(exc)
        return payload
    finally:
        _cleanup_tmp_dir(config.tmp_dir)


def _default_group_id(search_payload: dict[str, Any]) -> int:
    items = search_payload.get("body", {}).get("data", {}).get("items") or []
    if items:
        return int(items[0].get("groupID") or 0)
    return 0


def _search_cronjobs(env_file: Path, info: str) -> dict[str, Any]:
    config = load_onepanel_config(env_file)
    return send_signed_request(
        config,
        "POST",
        "/api/v2/cronjobs/search",
        body_bytes=json.dumps(
            {"page": 1, "pageSize": 50, "info": info, "groupIDs": [], "orderBy": "createdAt", "order": "descending"}
        ).encode("utf-8"),
    )


def ensure_onepanel_task(*, env_file: Path, trigger_now: bool = False) -> dict[str, Any]:
    current = _search_cronjobs(env_file, TASK_NAME)
    if current.get("status") != 200:
        raise RuntimeError(f"failed to search cronjobs: {current}")
    config = load_onepanel_config(env_file)
    items = current.get("body", {}).get("data", {}).get("items") or []
    existing = next((item for item in items if item.get("name") == TASK_NAME), None)
    group_id = int(existing.get("groupID", 0)) if existing else _default_group_id(_search_cronjobs(env_file, ""))
    payload = {
        "name": TASK_NAME,
        "type": "shell",
        "groupID": group_id,
        "specCustom": True,
        "spec": TASK_SPEC,
        "executor": "bash",
        "scriptMode": "input",
        "script": TASK_COMMAND,
        "command": "",
        "containerName": "",
        "user": "root",
        "scriptID": 0,
        "appID": "",
        "website": "",
        "exclusionRules": "",
        "dbType": "",
        "dbName": "",
        "url": "",
        "isDir": False,
        "sourceDir": "",
        "snapshotRule": {"withImage": False, "ignoreAppIDs": []},
        "sourceAccountIDs": "",
        "downloadAccountID": 0,
        "retainCopies": int(existing.get("retainCopies", 7)) if existing else 7,
        "retryTimes": int(existing.get("retryTimes", 3)) if existing else 3,
        "timeout": int(existing.get("timeout", 3600)) if existing else 3600,
        "ignoreErr": bool(existing.get("ignoreErr", False)) if existing else False,
        "secret": str(existing.get("secret", "")) if existing else "",
        "args": str(existing.get("args", "")) if existing else "",
        "alertCount": int(existing.get("alertCount", 0)) if existing else 0,
        "alertTitle": "",
        "alertMethod": "",
    }
    operation = "create"
    path = "/api/v2/cronjobs"
    if existing:
        payload["id"] = int(existing["id"])
        operation = "update"
        path = "/api/v2/cronjobs/update"
    response = send_signed_request(config, "POST", path, body_bytes=json.dumps(payload).encode("utf-8"))
    if response.get("status") != 200 or response.get("body", {}).get("code") != 200:
        raise RuntimeError(f"failed to {operation} cronjob: {response}")
    result: dict[str, Any] = {"operation": operation, "task_name": TASK_NAME, "spec": TASK_SPEC, "command": TASK_COMMAND}
    if trigger_now:
        refreshed = _search_cronjobs(env_file, TASK_NAME)
        refreshed_items = refreshed.get("body", {}).get("data", {}).get("items") or []
        task = next((item for item in refreshed_items if item.get("name") == TASK_NAME), None)
        if not task:
            raise RuntimeError("cronjob missing after create/update")
        handle = send_signed_request(
            config,
            "POST",
            "/api/v2/cronjobs/handle",
            body_bytes=json.dumps({"id": int(task["id"])}).encode("utf-8"),
        )
        if handle.get("status") != 200 or handle.get("body", {}).get("code") != 200:
            raise RuntimeError(f"failed to trigger cronjob: {handle}")
        result["triggered"] = True
        result["task_id"] = int(task["id"])
    return result

