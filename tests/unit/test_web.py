"""Unit tests for agentplane.web modules.

Covers: models, api, agent_router, server.
All tests use tmp_path or mocks — zero network, zero real LLM calls.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from agentplane.web.models import (
    AppInfo,
    AppsResponse,
    ChatInbound,
    ChatMessage,
    HostInfo,
    HostsResponse,
    OperationInfo,
    OperationsResponse,
)
from starlette.testclient import TestClient

# ---------------------------------------------------------------------------
# models.py
# ---------------------------------------------------------------------------


pytestmark = pytest.mark.unit


class TestModels:
    def test_host_info_roundtrip(self) -> None:
        h = HostInfo(
            target="wsl", hostname="box", ip="1.2.3.4",
            label="lab", provider="hetzner", status="connected", last_seen="2026-01-01",
        )
        assert h.target == "wsl"
        assert HostInfo.model_validate(h.model_dump()) == h

    def test_hosts_response(self) -> None:
        resp = HostsResponse(hosts=[])
        assert resp.hosts == []

    def test_app_info_roundtrip(self) -> None:
        a = AppInfo(
            app="myapp", target="wsl", repo_name="repo",
            service_key="svc", control_plane="cp", public_url="https://x",
        )
        assert AppInfo.model_validate(a.model_dump()) == a

    def test_apps_response(self) -> None:
        resp = AppsResponse(apps=[])
        assert resp.apps == []

    def test_operation_info(self) -> None:
        op = OperationInfo(
            timestamp="2026-01-01", target="wsl", object_type="app",
            action="apply", result="ok", op_id="op-1",
        )
        assert op.op_id == "op-1"

    def test_operations_response(self) -> None:
        resp = OperationsResponse(operations=[])
        assert resp.operations == []

    def test_chat_message(self) -> None:
        msg = ChatMessage(type="chat_message", payload={"text": "hi"})
        assert msg.type == "chat_message"

    def test_chat_inbound_defaults(self) -> None:
        msg = ChatInbound(text="hello")
        assert msg.type == "chat_message"
        assert msg.token is None

    def test_chat_inbound_with_token(self) -> None:
        msg = ChatInbound(text="hello", token="abc")
        assert msg.token == "abc"


# ---------------------------------------------------------------------------
# api.py
# ---------------------------------------------------------------------------


class TestApi:
    def test_list_hosts_empty(self, tmp_path: Path) -> None:
        from agentplane.web.api import list_hosts

        result = list_hosts(tmp_path)
        assert result == {"hosts": []}

    def test_list_hosts_with_inventory(self, tmp_path: Path) -> None:
        from agentplane.web.api import list_hosts

        inv_dir = tmp_path / "inventory" / "servers" / "wsl"
        inv_dir.mkdir(parents=True)
        (inv_dir / "inventory.json").write_text(
            json.dumps({
                "hostname": "wsl-box",
                "ssh": {"infra": "10.0.0.1"},
                "label": "dev",
                "provider": "local",
                "services": ["nginx"],
            }),
            encoding="utf-8",
        )
        result = list_hosts(tmp_path)
        assert len(result["hosts"]) == 1
        host = result["hosts"][0]
        assert host["target"] == "wsl"
        assert host["hostname"] == "wsl-box"
        assert host["ip"] == "10.0.0.1"
        assert host["status"] == "connected"

    def test_host_status_unknown_without_services(self, tmp_path: Path) -> None:
        from agentplane.web.api import list_hosts

        inv_dir = tmp_path / "inventory" / "servers" / "wsl"
        inv_dir.mkdir(parents=True)
        (inv_dir / "inventory.json").write_text(
            json.dumps({"hostname": "wsl-box", "services": []}),
            encoding="utf-8",
        )
        result = list_hosts(tmp_path)
        assert result["hosts"][0]["status"] == "unknown"

    def test_list_hosts_corrupt_json(self, tmp_path: Path) -> None:
        from agentplane.web.api import list_hosts

        inv_dir = tmp_path / "inventory" / "servers" / "wsl"
        inv_dir.mkdir(parents=True)
        (inv_dir / "inventory.json").write_text("not-json", encoding="utf-8")
        result = list_hosts(tmp_path)
        assert result == {"hosts": []}

    def test_list_apps_empty(self, tmp_path: Path) -> None:
        from agentplane.web.api import list_apps

        result = list_apps(tmp_path)
        assert result == {"apps": []}

    def test_list_operations_empty(self, tmp_path: Path) -> None:
        from agentplane.web.api import list_operations

        result = list_operations(tmp_path)
        assert result == {"operations": []}

    def test_list_operations_with_data(self, tmp_path: Path) -> None:
        from agentplane.web.api import list_operations

        inv_dir = tmp_path / "inventory" / "servers" / "wsl"
        inv_dir.mkdir(parents=True)
        (inv_dir / "inventory.json").write_text(
            json.dumps({
                "object_ledgers": {
                    "last_operations": {
                        "app": {
                            "timestamp": "2026-01-01T00:00:00Z",
                            "action": "apply",
                            "result": "ok",
                            "op_id": "op-1",
                        },
                    },
                },
            }),
            encoding="utf-8",
        )
        result = list_operations(tmp_path)
        assert len(result["operations"]) == 1
        assert result["operations"][0]["object_type"] == "app"

    def test_get_data_mtime_empty(self, tmp_path: Path) -> None:
        from agentplane.web.api import get_data_mtime

        result = get_data_mtime(tmp_path)
        assert result["mtime"] == 0.0

    def test_get_data_mtime_with_file(self, tmp_path: Path) -> None:
        from agentplane.web.api import get_data_mtime

        inv_dir = tmp_path / "inventory" / "servers" / "wsl"
        inv_dir.mkdir(parents=True)
        (inv_dir / "inventory.json").write_text("{}", encoding="utf-8")
        result = get_data_mtime(tmp_path)
        assert result["mtime"] > 0.0


# ---------------------------------------------------------------------------
# agent_router.py
# ---------------------------------------------------------------------------


class TestAgentRouter:
    def test_validate_command_valid_search(self) -> None:
        from agentplane.web.agent_router import validate_command

        cmd = {"command": "app search", "args": ["wsl"]}
        result = validate_command(cmd)
        assert result == cmd

    def test_validate_command_blocked_apply(self) -> None:
        from agentplane.web.agent_router import validate_command

        cmd = {"command": "app apply", "args": ["wsl"]}
        result = validate_command(cmd)
        assert result["command"] == "blocked"

    def test_validate_command_blocked_delete(self) -> None:
        from agentplane.web.agent_router import validate_command

        cmd = {"command": "app delete", "args": ["wsl", "myapp"]}
        result = validate_command(cmd)
        assert result["command"] == "blocked"

    def test_validate_command_unknown_verb(self) -> None:
        from agentplane.web.agent_router import validate_command

        cmd = {"command": "app deploy", "args": ["wsl"]}
        result = validate_command(cmd)
        assert result["command"] == "blocked"

    def test_validate_command_invalid_format(self) -> None:
        from agentplane.web.agent_router import validate_command

        cmd = {"command": "single"}
        result = validate_command(cmd)
        assert result["command"] == "error"
        assert "Invalid command format" in result["reason"]

    def test_validate_command_wrong_arg_count(self) -> None:
        from agentplane.web.agent_router import validate_command

        cmd = {"command": "app search", "args": ["wsl", "extra"]}
        result = validate_command(cmd)
        assert result["command"] == "error"
        assert "Expected 1 args" in result["reason"]

    def test_validate_command_invalid_target(self) -> None:
        from agentplane.web.agent_router import validate_command

        cmd = {"command": "app search", "args": ["unknown-target"]}
        result = validate_command(cmd)
        assert result["command"] == "error"
        assert "Invalid target" in result["reason"]

    def test_validate_command_passthrough_blocked(self) -> None:
        from agentplane.web.agent_router import validate_command

        cmd = {"command": "blocked", "reason": "nope"}
        result = validate_command(cmd)
        assert result == cmd

    def test_validate_command_passthrough_error(self) -> None:
        from agentplane.web.agent_router import validate_command

        cmd = {"command": "error", "reason": "bad"}
        result = validate_command(cmd)
        assert result == cmd

    def test_execute_command_valid(self, tmp_path: Path) -> None:
        from agentplane.web.agent_router import execute_command

        cmd = {"command": "app search", "args": ["wsl"]}
        result = execute_command(tmp_path, cmd)
        assert result["status"] == "success"
        assert result["command"] == "app search"

    def test_execute_command_unknown_handler(self, tmp_path: Path) -> None:
        from agentplane.web.agent_router import execute_command

        cmd = {"command": "unknown cmd", "args": []}
        result = execute_command(tmp_path, cmd)
        assert result["status"] == "error"
        assert "No handler" in result["message"]

    def test_call_llm_no_api_key(self) -> None:
        from agentplane.web.agent_router import call_llm

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": ""}, clear=False):
            import asyncio
            result = asyncio.get_event_loop().run_until_complete(call_llm("hi", []))
            assert result["command"] == "error"
            assert "ANTHROPIC_API_KEY" in result["reason"]

    def test_handle_chat_message_blocked(self, tmp_path: Path) -> None:
        from agentplane.web.agent_router import handle_chat_message

        with patch("agentplane.web.agent_router.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = {"command": "app apply", "args": ["wsl"]}
            import asyncio
            result = asyncio.get_event_loop().run_until_complete(
                handle_chat_message(tmp_path, "deploy myapp", [])
            )
            assert result["type"] == "command_rejected"


# ---------------------------------------------------------------------------
# server.py
# ---------------------------------------------------------------------------


class TestServer:
    def test_create_app_returns_fastapi(self, tmp_path: Path) -> None:
        from agentplane.web.server import create_app

        app = create_app(tmp_path)
        assert app.title == "AgentPlane"

    def test_api_hosts_no_auth(self, tmp_path: Path) -> None:
        from agentplane.web.server import create_app

        app = create_app(tmp_path)
        client = TestClient(app)
        resp = client.get("/api/hosts")
        assert resp.status_code == 200
        assert "hosts" in resp.json()

    def test_api_apps_no_auth(self, tmp_path: Path) -> None:
        from agentplane.web.server import create_app

        app = create_app(tmp_path)
        client = TestClient(app)
        resp = client.get("/api/apps")
        assert resp.status_code == 200
        assert "apps" in resp.json()

    def test_api_operations_no_auth(self, tmp_path: Path) -> None:
        from agentplane.web.server import create_app

        app = create_app(tmp_path)
        client = TestClient(app)
        resp = client.get("/api/operations")
        assert resp.status_code == 200
        assert "operations" in resp.json()

    def test_api_mtime_no_auth(self, tmp_path: Path) -> None:
        from agentplane.web.server import create_app

        app = create_app(tmp_path)
        client = TestClient(app)
        resp = client.get("/api/mtime")
        assert resp.status_code == 200
        assert "mtime" in resp.json()

    def test_api_config_no_auth(self, tmp_path: Path) -> None:
        from agentplane.web.server import create_app

        app = create_app(tmp_path)
        client = TestClient(app)
        resp = client.get("/api/config")
        assert resp.status_code == 200
        assert resp.json()["requires_auth"] is False

    def test_api_config_with_auth(self, tmp_path: Path) -> None:
        from agentplane.web.server import create_app

        app = create_app(tmp_path, token="secret")
        client = TestClient(app)
        resp = client.get("/api/config", headers={"Authorization": "Bearer secret"})
        assert resp.json()["requires_auth"] is True

    def test_api_auth_required_with_token(self, tmp_path: Path) -> None:
        from agentplane.web.server import create_app

        app = create_app(tmp_path, token="secret")
        client = TestClient(app)
        resp = client.get("/api/hosts")
        assert resp.status_code == 401

    def test_api_auth_passes_with_bearer(self, tmp_path: Path) -> None:
        from agentplane.web.server import create_app

        app = create_app(tmp_path, token="secret")
        client = TestClient(app)
        resp = client.get("/api/hosts", headers={"Authorization": "Bearer secret"})
        assert resp.status_code == 200
