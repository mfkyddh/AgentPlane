# Prod2 Clash Relay Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 `prod2-main` 落地一套正式受管的 `Trojan + TLS` relay 服务，并生成可在 Windows `Clash Nyanpasu` 中以 `Local Profile` 方式导入的 `prod2` 专用配置，同时保留现有 `Remote Profile` 不变。

**Architecture:** 远端 relay 作为 `inventory/servers/prod2-main/inventory.json` 中的动态 `compose` service，service key 使用 `relay-trojan`，以便直接复用现有 `service plan/apply reconcile -> infra/compose/<service-key>` 路径规则。Cloudflare DNS 保持灰云，由一个小型可复用 helper 管理 `relay.zzzai.fun -> 38.12.32.94` 记录；Windows 侧通过一个 YAML renderer 基于当前 `Remote Profile` 生成完整的 `prod2` 本地 profile，再用 Nyanpasu 官方支持的 `Local Profile` 导入路径接管。

**Tech Stack:** Python 3.12、`PyYAML`、现有 `ops.cli service` / `ops.adapters.service` / `ops.domain.service`、Docker Compose、Cloudflare v4 API、PowerShell、Clash Nyanpasu Local Profile

---

## File Map

- Create: `infra/compose/relay-trojan/docker-compose.prod2.yml`
- Create: `infra/compose/relay-trojan/config.template.json`
- Create: `infra/compose/relay-trojan/README.md`
- Create: `templates/services/relay-trojan.prod2.env.example`
- Create: `ops/scripts/cloudflare/client.py`
- Create: `ops/scripts/relay_trojan/ensure_dns_record.py`
- Create: `ops/scripts/relay_trojan/render_clash_profile.py`
- Create: `tests/test_relay_trojan_compose_layout.py`
- Create: `tests/test_relay_trojan_dns_cli.py`
- Create: `tests/test_relay_trojan_profile_renderer.py`
- Create: `docs/runbooks/prod2-main-relay-trojan.md`
- Modify: `ops/scripts/onepanel/public_ingress.py`
- Modify: `ops/adapters/service/docker_runtime.py`
- Modify: `tests/test_service_cli.py`
- Modify: `tests/test_docs_no_legacy_terms.py`
- Modify: `inventory/servers/prod2-main/inventory.json`
- Modify: `inventory/servers/prod2-main/README.md`
- Modify: `docs/architecture/control-plane.md`
- Modify: `README.md`

## Local-Only Files

以下文件必须在本地创建，但不得提交：

- Local only: `secrets/hosts/prod2-main/relay-trojan/service.env`
- Local only: `secrets/hosts/prod2-main/relay-trojan/config.json`
- Local only: `secrets/services/relay-trojan.prod2.env`
- Local only: `/mnt/c/Users/Administrator/AppData/Roaming/Clash Nyanpasu/config/profiles/prod2-relay-local.yaml`

### Task 1: 冻结 `relay-trojan` 服务合同与 host binding 校验

**Files:**
- Modify: `tests/test_service_cli.py`
- Modify: `ops/adapters/service/docker_runtime.py`

- [ ] **Step 1: 写失败测试，声明 `relay-trojan` 是 `prod2-main` 的动态 compose service**

在 `tests/test_service_cli.py` 的 `write_inventory()` 夹具里新增：

```python
"relay-trojan": {
    "control_plane": "compose",
    "container_name": "relay-trojan-prod",
    "image": "ghcr.io/xtls/xray-core:25.3.6",
    "host_binding": "0.0.0.0:24443",
    "runtime_root": "/data/relay-trojan",
    "public_endpoint": {
        "domain": "relay.zzzai.fun",
        "port": 24443,
        "protocol": "trojan",
        "transport": "tcp+tls",
        "cloudflare_proxy": False,
    },
},
```

并新增断言：

```python
result = run_cli("service", "get", "--target", "prod0-main", "--name", "relay-trojan", "--repo-root", str(root))
payload = json.loads(result.stdout)
service = payload["payload"]["service"]
declared = service["declared"]
assert service["name"] == "relay-trojan"
assert declared["host_binding"] == "0.0.0.0:24443"
assert declared["public_endpoint"]["domain"] == "relay.zzzai.fun"
```

- [ ] **Step 2: 写失败测试，要求 `service verify` 比对 `host_binding`**

把 `write_fake_service_ssh()` 里的 fake `docker inspect relay-trojan-prod` 输出扩成：

```bash
if [[ "$cmd" == *"docker inspect relay-trojan-prod --format"* ]]; then
  cat <<JSON
{"Name":"relay-trojan-prod","Config":{"Image":"ghcr.io/xtls/xray-core:25.3.6"},"State":{"Status":"running","Running":true},"HostConfig":{"NetworkMode":"bridge"},"NetworkSettings":{"Ports":{"24443/tcp":[{"HostIp":"0.0.0.0","HostPort":"24443"}]}}}
JSON
  exit 0
fi
```

新增断言：

```python
result = run_cli("service", "verify", "--target", "prod0-main", "--name", "relay-trojan", "--repo-root", str(root))
payload = json.loads(result.stdout)
checks = payload["payload"]["checks"]
assert checks["running"]["ok"] is True
assert checks["image"]["ok"] is True
assert checks["host_binding"]["ok"] is True
```

- [ ] **Step 3: 运行 focused tests，确认先红**

Run:

```bash
cd /root/work/OP_Linux/.worktrees/prod2-clash-relay-plan
uv run python -m pytest tests/test_service_cli.py -q
```

Expected:
- FAIL，因为 `docker_runtime.verify_container_service()` 还不会校验 `host_binding`

- [ ] **Step 4: 实现最小 `host_binding` 校验逻辑**

在 `ops/adapters/service/docker_runtime.py` 的 `verify_container_service()` 中加入：

```python
expected_host_binding = declared.get("host_binding") if isinstance(declared, dict) else None
if isinstance(expected_host_binding, str):
    ports = live.get("NetworkSettings", {}).get("Ports", {}) if isinstance(live, dict) else {}
    actual_bindings: list[str] = []
    for container_port, bindings in ports.items():
        if not isinstance(bindings, list):
            continue
        for binding in bindings:
            if not isinstance(binding, dict):
                continue
            host_ip = str(binding.get("HostIp", "")).strip()
            host_port = str(binding.get("HostPort", "")).strip()
            actual_bindings.append(f"{host_ip}:{host_port}")
    checks["host_binding"] = {
        "ok": expected_host_binding in actual_bindings,
        "actual": actual_bindings,
        "expected": expected_host_binding,
    }
```

- [ ] **Step 5: 重新运行 tests，确认转绿**

Run:

```bash
uv run python -m pytest tests/test_service_cli.py -q
```

Expected:
- PASS，且 `relay-trojan` 能被 `service get/verify` 识别为动态 compose service

- [ ] **Step 6: 提交本任务**

```bash
git add tests/test_service_cli.py ops/adapters/service/docker_runtime.py
git commit -m "feat: verify dynamic service host bindings"
```

### Task 2: 落地 relay compose 资产与模板

**Files:**
- Create: `tests/test_relay_trojan_compose_layout.py`
- Create: `infra/compose/relay-trojan/docker-compose.prod2.yml`
- Create: `infra/compose/relay-trojan/config.template.json`
- Create: `infra/compose/relay-trojan/README.md`
- Create: `templates/services/relay-trojan.prod2.env.example`

- [ ] **Step 1: 写失败测试，冻结 compose 目录与 env 模板**

创建 `tests/test_relay_trojan_compose_layout.py`：

```python
import unittest
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_compose(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


class RelayTrojanComposeLayoutTests(unittest.TestCase):
    def test_prod2_compose_matches_expected_layout(self) -> None:
        compose = load_compose(REPO_ROOT / "infra" / "compose" / "relay-trojan" / "docker-compose.prod2.yml")
        service = compose["services"]["relay-trojan"]

        self.assertEqual("relay-trojan-prod", service["container_name"])
        self.assertEqual(["../../../secrets/services/relay-trojan.prod2.env"], service["env_file"])
        self.assertIn("0.0.0.0:24443:24443", service["ports"])
        self.assertIn("/data/relay-trojan:/data/relay-trojan", service["volumes"])
        self.assertEqual(["zqf_network"], service["networks"])

    def test_prod2_env_template_matches_contract(self) -> None:
        env_template = (REPO_ROOT / "templates" / "services" / "relay-trojan.prod2.env.example").read_text(encoding="utf-8")
        self.assertIn("RELAY_TROJAN_PUBLIC_DOMAIN=relay.zzzai.fun", env_template)
        self.assertIn("RELAY_TROJAN_PUBLIC_PORT=24443", env_template)
        self.assertIn("RELAY_TROJAN_CONTAINER_NAME=relay-trojan-prod", env_template)
        self.assertIn("RELAY_TROJAN_CERT_FULLCHAIN=/data/relay-trojan/certs/fullchain.pem", env_template)
```

- [ ] **Step 2: 运行 focused tests，确认先红**

Run:

```bash
cd /root/work/OP_Linux/.worktrees/prod2-clash-relay-plan
uv run python -m pytest tests/test_relay_trojan_compose_layout.py -q
```

Expected:
- FAIL，因为 `relay-trojan` compose 目录和模板尚不存在

- [ ] **Step 3: 创建 `docker-compose.prod2.yml`**

写入 `infra/compose/relay-trojan/docker-compose.prod2.yml`：

```yaml
services:
  relay-trojan:
    image: ${RELAY_TROJAN_IMAGE_REF}
    container_name: ${RELAY_TROJAN_CONTAINER_NAME}
    restart: unless-stopped

    env_file:
      - ../../../secrets/services/relay-trojan.prod2.env

    command:
      - run
      - -config
      - /data/relay-trojan/config/config.json

    ports:
      - "0.0.0.0:24443:24443"

    volumes:
      - /data/relay-trojan:/data/relay-trojan

    networks:
      - zqf_network

networks:
  zqf_network:
    external: true
```

- [ ] **Step 4: 创建 config template 与 env example**

写入 `infra/compose/relay-trojan/config.template.json`：

```json
{
  "log": {
    "loglevel": "warning"
  },
  "inbounds": [
    {
      "tag": "relay-trojan",
      "listen": "0.0.0.0",
      "port": 24443,
      "protocol": "trojan",
      "settings": {
        "clients": [
          {
            "password": "__RELAY_TROJAN_PASSWORD__"
          }
        ]
      },
      "streamSettings": {
        "network": "tcp",
        "security": "tls",
        "tlsSettings": {
          "certificates": [
            {
              "certificateFile": "/data/relay-trojan/certs/fullchain.pem",
              "keyFile": "/data/relay-trojan/certs/privkey.pem"
            }
          ]
        }
      }
    }
  ],
  "outbounds": [
    {
      "tag": "direct",
      "protocol": "freedom"
    }
  ]
}
```

写入 `templates/services/relay-trojan.prod2.env.example`：

```dotenv
RELAY_TROJAN_IMAGE_REF=ghcr.io/xtls/xray-core:25.3.6
RELAY_TROJAN_CONTAINER_NAME=relay-trojan-prod
RELAY_TROJAN_PUBLIC_DOMAIN=relay.zzzai.fun
RELAY_TROJAN_PUBLIC_PORT=24443
RELAY_TROJAN_CERT_FULLCHAIN=/data/relay-trojan/certs/fullchain.pem
RELAY_TROJAN_CERT_KEY=/data/relay-trojan/certs/privkey.pem
RELAY_TROJAN_PASSWORD=replace-with-32-byte-random-string
```

- [ ] **Step 5: 创建 README**

写入 `infra/compose/relay-trojan/README.md`：

```md
# relay-trojan

- 这是 `prod2-main` 上供 Windows Clash 使用的正式 relay compose 资产。
- 生产模板：`docker-compose.prod2.yml`
- 正式 service key：`relay-trojan`
- 正式容器名：`relay-trojan-prod`
- 正式公网入口：`relay.zzzai.fun:24443`
- 正式协议：`Trojan + TLS`
- 真正的运行时 secret 仅存在于 `secrets/` 本地与远端 `/opt/op_linux/secrets/`，不得提交。
```

- [ ] **Step 6: 重新运行 tests，确认转绿**

Run:

```bash
uv run python -m pytest tests/test_relay_trojan_compose_layout.py -q
```

Expected:
- PASS，compose layout 与 env example 合同稳定

- [ ] **Step 7: 提交本任务**

```bash
git add tests/test_relay_trojan_compose_layout.py infra/compose/relay-trojan templates/services/relay-trojan.prod2.env.example
git commit -m "feat: add relay trojan compose assets"
```

### Task 3: 抽离 Cloudflare client 并增加 relay DNS helper

**Files:**
- Create: `tests/test_relay_trojan_dns_cli.py`
- Create: `ops/scripts/cloudflare/client.py`
- Create: `ops/scripts/relay_trojan/ensure_dns_record.py`
- Modify: `ops/scripts/onepanel/public_ingress.py`

- [ ] **Step 1: 写失败测试，冻结 DNS helper 的输入输出**

创建 `tests/test_relay_trojan_dns_cli.py`：

```python
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]


class RelayTrojanDnsCliTests(unittest.TestCase):
    @patch("ops.scripts.relay_trojan.ensure_dns_record.CloudflareClient")
    def test_helper_upserts_gray_cloud_a_record(self, client_cls) -> None:
        client = client_cls.return_value
        client.ensure_dns_record.return_value = {"changed": True, "action": "created", "record": {"name": "relay.zzzai.fun"}}
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / "prod-jump.env"
            env_file.write_text("CLOUDFLARE_API_TOKEN=test-token\n", encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    "ops/scripts/relay_trojan/ensure_dns_record.py",
                    "--cloudflare-env-file",
                    str(env_file),
                    "--zone-name",
                    "zzzai.fun",
                    "--record-name",
                    "relay.zzzai.fun",
                    "--record-type",
                    "A",
                    "--record-content",
                    "38.12.32.94",
                    "--proxied",
                    "false",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual("relay.zzzai.fun", payload["record"]["name"])
        client.ensure_dns_record.assert_called_once()
```

- [ ] **Step 2: 运行 focused tests，确认先红**

Run:

```bash
cd /root/work/OP_Linux/.worktrees/prod2-clash-relay-plan
uv run python -m pytest tests/test_relay_trojan_dns_cli.py -q
```

Expected:
- FAIL，因为 helper 与共用 Cloudflare client 还不存在

- [ ] **Step 3: 创建共用 Cloudflare client**

写入 `ops/scripts/cloudflare/client.py`：

```python
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


class CloudflareError(RuntimeError):
    pass


class CloudflareClient:
    def __init__(self, token: str) -> None:
        self.token = token

    def request(self, method: str, path: str, *, query: dict[str, Any] | None = None, body: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"https://api.cloudflare.com/client/v4{path}"
        if query:
            url = f"{url}?{urllib.parse.urlencode(query)}"
        data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
        request = urllib.request.Request(
            url,
            data=data,
            method=method.upper(),
            headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise CloudflareError(exc.read().decode("utf-8", errors="replace")) from exc
        if not payload.get("success"):
            raise CloudflareError(json.dumps(payload, ensure_ascii=False))
        return payload

    def get_zone_id(self, zone_name: str) -> str:
        payload = self.request("GET", "/zones", query={"name": zone_name})
        result = payload.get("result", [])
        if not result:
            raise CloudflareError(f"Cloudflare zone not found: {zone_name}")
        return str(result[0]["id"])

    def ensure_dns_record(self, *, zone_name: str, record_name: str, record_type: str, content: str, proxied: bool) -> dict[str, Any]:
        zone_id = self.get_zone_id(zone_name)
        existing = self.request("GET", f"/zones/{zone_id}/dns_records", query={"type": record_type, "name": record_name}).get("result", [])
        body = {"type": record_type, "name": record_name, "content": content, "proxied": proxied}
        if not existing:
            created = self.request("POST", f"/zones/{zone_id}/dns_records", body=body)["result"]
            return {"changed": True, "action": "created", "record": created}
        record = existing[0]
        if record.get("content") == content and bool(record.get("proxied")) == proxied:
            return {"changed": False, "action": "unchanged", "record": record}
        updated = self.request("PUT", f"/zones/{zone_id}/dns_records/{record['id']}", body=body)["result"]
        return {"changed": True, "action": "updated", "record": updated}
```

- [ ] **Step 4: 创建 relay DNS helper，并让 public ingress 复用共用 client**

写入 `ops/scripts/relay_trojan/ensure_dns_record.py`：

```python
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from ops.scripts.cloudflare.client import CloudflareClient, load_shell_env_file


def parse_bool(raw: str) -> bool:
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Ensure relay DNS record in Cloudflare.")
    parser.add_argument("--cloudflare-env-file", required=True)
    parser.add_argument("--zone-name", required=True)
    parser.add_argument("--record-name", required=True)
    parser.add_argument("--record-type", default="A")
    parser.add_argument("--record-content", required=True)
    parser.add_argument("--proxied", default="false")
    args = parser.parse_args()

    env = load_shell_env_file(Path(args.cloudflare_env_file))
    client = CloudflareClient(env["CLOUDFLARE_API_TOKEN"])
    result = client.ensure_dns_record(
        zone_name=args.zone_name,
        record_name=args.record_name,
        record_type=args.record_type,
        content=args.record_content,
        proxied=parse_bool(args.proxied),
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

并在 `ops/scripts/onepanel/public_ingress.py` 里把：

```python
from ops.scripts.onepanel.client import load_config, send_signed_request
```

改成：

```python
from ops.scripts.cloudflare.client import CloudflareClient, CloudflareError, load_shell_env_file
from ops.scripts.onepanel.client import load_config, send_signed_request
```

同时删除原文件中重复的 `load_shell_env_file`、`CloudflareClient`、`CloudflareError` 定义。

- [ ] **Step 5: 重新运行 tests，确认转绿**

Run:

```bash
uv run python -m pytest tests/test_relay_trojan_dns_cli.py tests/test_service_cli.py -q
```

Expected:
- PASS，DNS helper 可被测试桩驱动，public ingress 仍能导入共用 client

- [ ] **Step 6: 提交本任务**

```bash
git add tests/test_relay_trojan_dns_cli.py ops/scripts/cloudflare/client.py ops/scripts/relay_trojan/ensure_dns_record.py ops/scripts/onepanel/public_ingress.py
git commit -m "feat: add relay dns helper"
```

### Task 4: 实现 Clash profile renderer

**Files:**
- Create: `tests/test_relay_trojan_profile_renderer.py`
- Create: `ops/scripts/relay_trojan/render_clash_profile.py`

- [ ] **Step 1: 写失败测试，冻结 profile 渲染规则**

创建 `tests/test_relay_trojan_profile_renderer.py`：

```python
import unittest

from ops.scripts.relay_trojan.render_clash_profile import render_profile


class RelayTrojanProfileRendererTests(unittest.TestCase):
    def test_render_profile_keeps_rules_and_rewrites_proxy_sets(self) -> None:
        source = {
            "mode": "rule",
            "proxies": [{"name": "旧节点A", "type": "ss", "server": "a.example.com", "port": 443, "cipher": "aes-128-gcm", "password": "x"}],
            "proxy-groups": [
                {"name": "GPT", "type": "select", "proxies": ["国外流量", "旧节点A", "直接连接"]},
                {"name": "国外流量", "type": "select", "proxies": ["旧节点A", "直接连接"]},
            ],
            "rules": ["DOMAIN-SUFFIX,openai.com,GPT", "MATCH,国外流量"],
        }

        rendered = render_profile(
            source,
            node_name="Prod2|Relay",
            server="relay.zzzai.fun",
            port=24443,
            password="test-password",
            sni="relay.zzzai.fun",
        )

        self.assertEqual("Prod2|Relay", rendered["proxies"][0]["name"])
        self.assertEqual(["Prod2|Relay", "直接连接"], rendered["proxy-groups"][1]["proxies"])
        self.assertEqual(source["rules"], rendered["rules"])
```

- [ ] **Step 2: 运行 focused tests，确认先红**

Run:

```bash
cd /root/work/OP_Linux/.worktrees/prod2-clash-relay-plan
uv run python -m pytest tests/test_relay_trojan_profile_renderer.py -q
```

Expected:
- FAIL，因为 renderer 还不存在

- [ ] **Step 3: 实现 renderer**

写入 `ops/scripts/relay_trojan/render_clash_profile.py`：

```python
from __future__ import annotations

import argparse
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml


def _new_trojan_node(*, node_name: str, server: str, port: int, password: str, sni: str) -> dict[str, Any]:
    return {
        "name": node_name,
        "type": "trojan",
        "server": server,
        "port": port,
        "password": password,
        "sni": sni,
        "udp": True,
        "skip-cert-verify": False,
    }


def render_profile(source: dict[str, Any], *, node_name: str, server: str, port: int, password: str, sni: str) -> dict[str, Any]:
    rendered = deepcopy(source)
    rendered["proxies"] = [_new_trojan_node(node_name=node_name, server=server, port=port, password=password, sni=sni)]
    for group in rendered.get("proxy-groups", []):
        proxies = group.get("proxies")
        if not isinstance(proxies, list):
            continue
        next_proxies: list[str] = []
        for item in proxies:
            if item in {"DIRECT", "直接连接"}:
                next_proxies.append(item)
                continue
            if item == group.get("name"):
                next_proxies.append(item)
                continue
            if item not in next_proxies:
                next_proxies.append(node_name)
        deduped: list[str] = []
        for item in next_proxies:
            if item not in deduped:
                deduped.append(item)
        group["proxies"] = deduped
    return rendered


def main() -> int:
    parser = argparse.ArgumentParser(description="Render prod2 relay Clash profile.")
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--node-name", default="Prod2|Relay")
    parser.add_argument("--server", required=True)
    parser.add_argument("--port", required=True, type=int)
    parser.add_argument("--password", required=True)
    parser.add_argument("--sni", required=True)
    args = parser.parse_args()

    source = yaml.safe_load(Path(args.source).read_text(encoding="utf-8"))
    rendered = render_profile(source, node_name=args.node_name, server=args.server, port=args.port, password=args.password, sni=args.sni)
    Path(args.output).write_text(yaml.safe_dump(rendered, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: 重新运行 tests，确认转绿**

Run:

```bash
uv run python -m pytest tests/test_relay_trojan_profile_renderer.py -q
```

Expected:
- PASS，规则原样保留，分组与节点集合按单一 `Prod2|Relay` 节点重写

- [ ] **Step 5: 提交本任务**

```bash
git add tests/test_relay_trojan_profile_renderer.py ops/scripts/relay_trojan/render_clash_profile.py
git commit -m "feat: add relay clash profile renderer"
```

### Task 5: 更新 inventory、runbook 和长期边界文档

**Files:**
- Create: `docs/runbooks/prod2-main-relay-trojan.md`
- Modify: `inventory/servers/prod2-main/inventory.json`
- Modify: `inventory/servers/prod2-main/README.md`
- Modify: `docs/architecture/control-plane.md`
- Modify: `README.md`
- Modify: `tests/test_docs_no_legacy_terms.py`

- [ ] **Step 1: 写失败测试，冻结“relay 不是 website”这条边界**

在 `tests/test_docs_no_legacy_terms.py` 中加入：

```python
self.assertIn("非 HTTP 协议入口继续附着在 `service` 事实中，不进入 `website publish`", control_plane_text)
runbook_text = (REPO_ROOT / "docs" / "runbooks" / "prod2-main-relay-trojan.md").read_text(encoding="utf-8")
self.assertIn("`relay.zzzai.fun:24443` 不属于 `website` 对象", runbook_text)
self.assertIn("uv run python -m ops.cli service verify --target prod2-main --name relay-trojan", runbook_text)
```

- [ ] **Step 2: 运行 focused tests，确认先红**

Run:

```bash
cd /root/work/OP_Linux/.worktrees/prod2-clash-relay-plan
uv run python -m pytest tests/test_docs_no_legacy_terms.py -q
```

Expected:
- FAIL，因为 runbook 和 control-plane 文本尚未同步

- [ ] **Step 3: 修改 `inventory/servers/prod2-main/inventory.json`**

在 `services` 节点新增：

```json
"relay-trojan": {
  "control_plane": "compose",
  "container_name": "relay-trojan-prod",
  "image": "ghcr.io/xtls/xray-core:25.3.6",
  "status": "planned",
  "runtime_root": "/data/relay-trojan",
  "config_files": [
    "/opt/op_linux/secrets/services/relay-trojan.prod2.env",
    "/data/relay-trojan/config/config.json"
  ],
  "host_binding": "0.0.0.0:24443",
  "container_port": 24443,
  "public_endpoint": {
    "domain": "relay.zzzai.fun",
    "port": 24443,
    "protocol": "trojan",
    "transport": "tcp+tls",
    "cloudflare_proxy": false,
    "certificate_mode": "Let's Encrypt DNS-01"
  },
  "rollback_entry": {
    "kind": "none",
    "note": "prod2-main 首次上线独立 relay，无历史控制面"
  },
  "docker_networks": [
    "zqf_network"
  ]
}
```

- [ ] **Step 4: 更新 README、runbook 与 architecture**

在 `inventory/servers/prod2-main/README.md` 增加一行摘要：

```md
- `relay-trojan`：`compose` / `relay-trojan-prod` / `relay.zzzai.fun:24443`
```

创建 `docs/runbooks/prod2-main-relay-trojan.md`，最小内容必须包括：

```md
# prod2-main relay-trojan

- 本手册定义 `prod2-main` 上 `relay-trojan` 的正式运行口径。
- `relay.zzzai.fun:24443` 不属于 `website` 对象；它是附着在 `service` 上的非 HTTP 公网协议端点。
- 正式服务核验入口：
  `uv run python -m ops.cli service verify --target prod2-main --name relay-trojan --repo-root /root/work/OP_Linux`
- Cloudflare DNS 入口：
  `uv run python ops/scripts/relay_trojan/ensure_dns_record.py --cloudflare-env-file /root/work/OP_Linux/secrets/env/prod-jump.env --zone-name zzzai.fun --record-name relay.zzzai.fun --record-type A --record-content 38.12.32.94 --proxied false`
- 证书目录：
  `/data/relay-trojan/certs/fullchain.pem`
  `/data/relay-trojan/certs/privkey.pem`
```

在 `docs/architecture/control-plane.md` 的 `website` / `service` 边界中补一句：

```md
非 HTTP 协议入口继续附着在 `service` 事实中，不进入 `website publish`。
```

在 `README.md` 的 active docs 区补一条：

```md
- `docs/runbooks/prod2-main-relay-trojan.md`: prod2 relay 节点运行与验证手册
```

- [ ] **Step 5: 重新运行 tests，确认转绿**

Run:

```bash
uv run python -m pytest tests/test_docs_no_legacy_terms.py tests/test_relay_trojan_compose_layout.py tests/test_service_cli.py -q
```

Expected:
- PASS，文档与 inventory 边界一致

- [ ] **Step 6: 提交本任务**

```bash
git add docs/runbooks/prod2-main-relay-trojan.md inventory/servers/prod2-main/inventory.json inventory/servers/prod2-main/README.md docs/architecture/control-plane.md README.md tests/test_docs_no_legacy_terms.py
git commit -m "docs: register prod2 relay trojan service"
```

### Task 6: 本地 secret、远端部署、Cloudflare、Windows profile 验证闭环

**Files:**
- Local only: `secrets/hosts/prod2-main/relay-trojan/service.env`
- Local only: `secrets/hosts/prod2-main/relay-trojan/config.json`
- Local only: `secrets/services/relay-trojan.prod2.env`
- Local only: `/mnt/c/Users/Administrator/AppData/Roaming/Clash Nyanpasu/config/profiles/prod2-relay-local.yaml`

- [ ] **Step 1: 创建本地 secret 真源目录，不加入 git**

Run:

```bash
cd /root/work/OP_Linux/.worktrees/prod2-clash-relay-plan
mkdir -p secrets/hosts/prod2-main/relay-trojan secrets/services
chmod 700 secrets/hosts secrets/hosts/prod2-main secrets/hosts/prod2-main/relay-trojan
```

Expected:
- `git status --short` 不出现 `secrets/` 相关跟踪项

- [ ] **Step 2: 生成本地密码并写入 local env**

Run:

```bash
PASSWORD="$(openssl rand -base64 32 | tr -d '\n')"
cat > secrets/hosts/prod2-main/relay-trojan/service.env <<EOF
RELAY_TROJAN_IMAGE_REF=ghcr.io/xtls/xray-core:25.3.6
RELAY_TROJAN_CONTAINER_NAME=relay-trojan-prod
RELAY_TROJAN_PUBLIC_DOMAIN=relay.zzzai.fun
RELAY_TROJAN_PUBLIC_PORT=24443
RELAY_TROJAN_PASSWORD=${PASSWORD}
RELAY_TROJAN_CERT_FULLCHAIN=/data/relay-trojan/certs/fullchain.pem
RELAY_TROJAN_CERT_KEY=/data/relay-trojan/certs/privkey.pem
EOF
chmod 600 secrets/hosts/prod2-main/relay-trojan/service.env
cp secrets/hosts/prod2-main/relay-trojan/service.env secrets/services/relay-trojan.prod2.env
chmod 600 secrets/services/relay-trojan.prod2.env
```

Expected:
- `secrets/services/relay-trojan.prod2.env` 可被 compose 读取

- [ ] **Step 3: 生成本地 config.json**

Run:

```bash
python - <<'PY'
from pathlib import Path
import json

env = {}
for line in Path("secrets/hosts/prod2-main/relay-trojan/service.env").read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    k, v = line.split("=", 1)
    env[k] = v

payload = {
    "log": {"loglevel": "warning"},
    "inbounds": [{
        "tag": "relay-trojan",
        "listen": "0.0.0.0",
        "port": 24443,
        "protocol": "trojan",
        "settings": {"clients": [{"password": env["RELAY_TROJAN_PASSWORD"]}]},
        "streamSettings": {
            "network": "tcp",
            "security": "tls",
            "tlsSettings": {
                "certificates": [{
                    "certificateFile": env["RELAY_TROJAN_CERT_FULLCHAIN"],
                    "keyFile": env["RELAY_TROJAN_CERT_KEY"],
                }]
            },
        },
    }],
    "outbounds": [{"tag": "direct", "protocol": "freedom"}],
}
path = Path("secrets/hosts/prod2-main/relay-trojan/config.json")
path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
path.chmod(0o600)
PY
```

Expected:
- `secrets/hosts/prod2-main/relay-trojan/config.json` 存在且权限为 `600`

- [ ] **Step 4: 在远端准备目录并签发 DNS-01 证书**

先确保朝晞云与主机侧都已放行 `24443/tcp`，再运行：

```bash
ssh -F secrets/ssh/config prod2-main 'mkdir -p /data/relay-trojan/config /data/relay-trojan/certs /data/relay-trojan/logs /data/apps/letsencrypt /data/apps/letsencrypt/lib'
scp -F secrets/ssh/config secrets/services/relay-trojan.prod2.env prod2-main:/tmp/relay-trojan.prod2.env
scp -F secrets/ssh/config secrets/hosts/prod2-main/relay-trojan/config.json prod2-main:/tmp/relay-trojan-config.json
ssh -F secrets/ssh/config prod2-main 'install -Dm600 /tmp/relay-trojan.prod2.env /opt/op_linux/secrets/services/relay-trojan.prod2.env && install -Dm600 /tmp/relay-trojan-config.json /data/relay-trojan/config/config.json'
```

使用 Cloudflare token 签发证书：

```bash
TOKEN="$(awk -F= '$1==\"CLOUDFLARE_API_TOKEN\" {print $2}' secrets/env/prod-jump.env)"
ssh -F secrets/ssh/config prod2-main "cat > /tmp/cloudflare.ini <<EOF
dns_cloudflare_api_token = ${TOKEN}
EOF
install -Dm600 /tmp/cloudflare.ini /data/apps/letsencrypt/cloudflare.ini"
ssh -F secrets/ssh/config prod2-main 'docker run --rm --network host -v /data/apps/letsencrypt:/etc/letsencrypt -v /data/apps/letsencrypt/lib:/var/lib/letsencrypt -v /data/apps/letsencrypt/cloudflare.ini:/cloudflare.ini:ro certbot/dns-cloudflare:latest certonly --dns-cloudflare --dns-cloudflare-credentials /cloudflare.ini --dns-cloudflare-propagation-seconds 120 -n --agree-tos -m admin@zzzai.fun -d relay.zzzai.fun'
ssh -F secrets/ssh/config prod2-main 'cp /data/apps/letsencrypt/live/relay.zzzai.fun/fullchain.pem /data/relay-trojan/certs/fullchain.pem && cp /data/apps/letsencrypt/live/relay.zzzai.fun/privkey.pem /data/relay-trojan/certs/privkey.pem && chmod 600 /data/relay-trojan/certs/fullchain.pem /data/relay-trojan/certs/privkey.pem'
```

Expected:
- 远端 `/data/relay-trojan/certs/fullchain.pem` 与 `privkey.pem` 已生成

- [ ] **Step 5: 应用 Cloudflare DNS 并拉起远端服务**

Run:

```bash
uv run python ops/scripts/relay_trojan/ensure_dns_record.py \
  --cloudflare-env-file secrets/env/prod-jump.env \
  --zone-name zzzai.fun \
  --record-name relay.zzzai.fun \
  --record-type A \
  --record-content 38.12.32.94 \
  --proxied false

ssh -F secrets/ssh/config prod2-main 'cd /opt/op_linux/infra/compose/relay-trojan && docker compose -f docker-compose.prod2.yml up -d'
uv run python -m ops.cli service verify --target prod2-main --name relay-trojan --repo-root /root/work/OP_Linux/.worktrees/prod2-clash-relay-plan
```

Expected:
- DNS helper 返回 `created` 或 `updated`
- `service verify` 返回 `ok=true`

- [ ] **Step 6: 生成 Windows 本地 profile 并导入 Nyanpasu**

先在 WSL 渲染目标文件：

```bash
python ops/scripts/relay_trojan/render_clash_profile.py \
  --source /mnt/c/Users/Administrator/AppData/Roaming/Clash\ Nyanpasu/config/profiles/rDaD8Jn0hFaZ.yaml \
  --output /mnt/c/Users/Administrator/AppData/Roaming/Clash\ Nyanpasu/config/profiles/prod2-relay-local.yaml \
  --node-name Prod2\|Relay \
  --server relay.zzzai.fun \
  --port 24443 \
  --password "$(awk -F= '$1==\"RELAY_TROJAN_PASSWORD\" {print $2}' secrets/hosts/prod2-main/relay-trojan/service.env)" \
  --sni relay.zzzai.fun
```

然后在 Windows 侧通过 Nyanpasu 官方支持的 `Local Profile` 导入该文件：

1. 打开 `Clash Nyanpasu`
2. 进入“配置”
3. 点击右下角 `+`
4. 选择 `Local Profile`
5. 选择 `C:\Users\Administrator\AppData\Roaming\Clash Nyanpasu\config\profiles\prod2-relay-local.yaml`
6. 命名为 `Prod2 Relay`

Expected:
- 原 `Remote Profile` 仍保留
- 新 `Prod2 Relay` local profile 可单独切换

- [ ] **Step 7: 执行最终验证**

Run:

```bash
ssh -F secrets/ssh/config prod2-main 'ss -ltnp | grep 24443'
openssl s_client -connect relay.zzzai.fun:24443 -servername relay.zzzai.fun </dev/null 2>/dev/null | openssl x509 -noout -subject -issuer
uv run python -m pytest tests/test_service_cli.py tests/test_relay_trojan_compose_layout.py tests/test_relay_trojan_dns_cli.py tests/test_relay_trojan_profile_renderer.py tests/test_docs_no_legacy_terms.py -q
```

Expected:
- `24443` 正在监听
- TLS 证书主题包含 `relay.zzzai.fun`
- 代码与文档回归测试全绿

- [ ] **Step 8: 记录未自动化项并不要提交 secrets**

Run:

```bash
git status --short
```

Expected:
- 只有 tracked 代码与文档变更已提交
- `secrets/` 与 Windows profile 文件不会进入 git
