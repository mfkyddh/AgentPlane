"""Unit tests for onepanel low-coverage modules.

Covers: client.py, redaction.py, executor.py, signed_request.py
Focus on pure functions and mocked I/O.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# client.py — load_env_file, normalize_entrance, load_config, build_headers, try_parse_json
# ---------------------------------------------------------------------------


class TestClientHelpers:
    def test_load_env_file_basic(self, tmp_path: Path) -> None:
        from agentplane.scripts.onepanel.client import load_env_file

        env_file = tmp_path / "test.env"
        env_file.write_text(
            "ONEPANEL_BASE_URL=https://panel.example.com\n"
            "ONEPANEL_API_KEY=secret123\n"
            "# comment line\n"
            "\n"
            "ONEPANEL_TIMEOUT_MS=5000\n",
            encoding="utf-8",
        )
        result = load_env_file(env_file)
        assert result["ONEPANEL_BASE_URL"] == "https://panel.example.com"
        assert result["ONEPANEL_API_KEY"] == "secret123"
        assert result["ONEPANEL_TIMEOUT_MS"] == "5000"
        assert len(result) == 3

    def test_load_env_file_strips_whitespace(self, tmp_path: Path) -> None:
        from agentplane.scripts.onepanel.client import load_env_file

        env_file = tmp_path / "test.env"
        env_file.write_text("  KEY = value  \n", encoding="utf-8")
        result = load_env_file(env_file)
        assert result["KEY"] == "value"

    def test_normalize_entrance_none(self) -> None:
        from agentplane.scripts.onepanel.client import normalize_entrance

        assert normalize_entrance(None) is None

    def test_normalize_entrance_strips_slashes(self) -> None:
        from agentplane.scripts.onepanel.client import normalize_entrance

        assert normalize_entrance("/abc/") == "abc"
        assert normalize_entrance("abc") == "abc"

    def test_normalize_entrance_empty_returns_none(self) -> None:
        from agentplane.scripts.onepanel.client import normalize_entrance

        assert normalize_entrance("/") is None
        assert normalize_entrance("") is None
        assert normalize_entrance("  ") is None

    def test_load_config_minimal(self, tmp_path: Path) -> None:
        from agentplane.scripts.onepanel.client import load_config

        env_file = tmp_path / "test.env"
        env_file.write_text(
            "ONEPANEL_BASE_URL=https://panel.example.com\n"
            "ONEPANEL_API_KEY=mykey\n",
            encoding="utf-8",
        )
        config = load_config(env_file)
        assert config.base_url == "https://panel.example.com"
        assert config.connect_base_url == "https://panel.example.com"
        assert config.api_key == "mykey"
        assert config.security_entrance is None
        assert config.timeout_seconds == 30.0
        assert config.skip_tls_verify is False

    def test_load_config_with_all_options(self, tmp_path: Path) -> None:
        from agentplane.scripts.onepanel.client import load_config

        env_file = tmp_path / "test.env"
        env_file.write_text(
            "ONEPANEL_BASE_URL=https://panel.example.com/\n"
            "ONEPANEL_CONNECT_BASE_URL=https://connect.example.com\n"
            "ONEPANEL_API_KEY=mykey\n"
            "ONEPANEL_SECURITY_ENTRANCE=/secret/\n"
            "ONEPANEL_TIMEOUT_MS=5000\n"
            "ONEPANEL_SKIP_TLS_VERIFY=true\n",
            encoding="utf-8",
        )
        config = load_config(env_file)
        assert config.base_url == "https://panel.example.com"
        assert config.connect_base_url == "https://connect.example.com"
        assert config.security_entrance == "secret"
        assert config.timeout_seconds == 5.0
        assert config.skip_tls_verify is True

    def test_build_headers_basic(self) -> None:
        from agentplane.scripts.onepanel.client import build_headers

        headers = build_headers("https://panel.example.com", "mykey", None, None)
        assert headers["Content-Type"] == "application/json"
        assert headers["Host"] == "panel.example.com"
        assert "1Panel-Token" in headers
        assert "1Panel-Timestamp" in headers
        assert "Origin" not in headers

    def test_build_headers_with_entrance(self) -> None:
        from agentplane.scripts.onepanel.client import build_headers

        headers = build_headers("https://panel.example.com", "mykey", "secret", None)
        assert headers["Origin"] == "https://panel.example.com"
        assert headers["Referer"] == "https://panel.example.com/secret/"

    def test_build_headers_with_body(self) -> None:
        from agentplane.scripts.onepanel.client import build_headers

        body = b'{"key": "value"}'
        headers = build_headers("https://panel.example.com", "mykey", None, body)
        assert headers["Content-Length"] == str(len(body))

    def test_try_parse_json_valid(self) -> None:
        from agentplane.scripts.onepanel.client import try_parse_json

        result = try_parse_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_try_parse_json_invalid(self) -> None:
        from agentplane.scripts.onepanel.client import try_parse_json

        result = try_parse_json("not json")
        assert result == "not json"

    def test_send_signed_request_success(self, tmp_path: Path) -> None:
        from agentplane.scripts.onepanel.client import OnePanelConfig, send_signed_request

        config = OnePanelConfig(
            base_url="https://panel.example.com",
            connect_base_url="https://panel.example.com",
            api_key="mykey",
            security_entrance=None,
            timeout_seconds=10.0,
            skip_tls_verify=False,
        )
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b'{"code": 200, "data": {}}'
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = send_signed_request(config, "GET", "/api/v2/test")
            assert result["status"] == 200
            assert result["body"] == {"code": 200, "data": {}}

    def test_send_signed_request_http_error(self, tmp_path: Path) -> None:
        import urllib.error

        from agentplane.scripts.onepanel.client import OnePanelConfig, send_signed_request

        config = OnePanelConfig(
            base_url="https://panel.example.com",
            connect_base_url="https://panel.example.com",
            api_key="mykey",
            security_entrance=None,
            timeout_seconds=10.0,
            skip_tls_verify=False,
        )
        mock_error = urllib.error.HTTPError(
            url="https://panel.example.com/api/v2/test",
            code=403,
            msg="Forbidden",
            hdrs=None,
            fp=MagicMock(read=MagicMock(return_value=b'{"message": "forbidden"}')),
        )

        with patch("urllib.request.urlopen", side_effect=mock_error):
            result = send_signed_request(config, "GET", "/api/v2/test")
            assert result["status"] == 403

    def test_send_signed_request_with_query(self, tmp_path: Path) -> None:
        from agentplane.scripts.onepanel.client import OnePanelConfig, send_signed_request

        config = OnePanelConfig(
            base_url="https://panel.example.com",
            connect_base_url="https://panel.example.com",
            api_key="mykey",
            security_entrance=None,
            timeout_seconds=10.0,
            skip_tls_verify=False,
        )
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b'{"code": 200}'
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response) as mock_open:
            send_signed_request(config, "GET", "/api/v2/test", query={"page": "1"})
            call_args = mock_open.call_args
            request = call_args[0][0]
            assert "page=1" in request.full_url


# ---------------------------------------------------------------------------
# redaction.py — is_sensitive_key
# ---------------------------------------------------------------------------


class TestRedaction:
    def test_sensitive_exact_matches(self) -> None:
        from agentplane.scripts.onepanel.redaction import is_sensitive_key

        for key in ("password", "token", "secret", "apikey", "authorization", "privatekey"):
            assert is_sensitive_key(key) is True, f"{key} should be sensitive"

    def test_sensitive_suffix_matches(self) -> None:
        from agentplane.scripts.onepanel.redaction import is_sensitive_key

        for key in ("my_apikey", "auth_token", "db_password", "ssh_privatekey", "jwt_secretkey"):
            assert is_sensitive_key(key) is True, f"{key} should be sensitive"

    def test_sensitive_secret_suffix(self) -> None:
        from agentplane.scripts.onepanel.redaction import is_sensitive_key

        assert is_sensitive_key("my_secret") is True
        assert is_sensitive_key("client_secret") is True

    def test_not_sensitive_secretfile(self) -> None:
        from agentplane.scripts.onepanel.redaction import is_sensitive_key

        assert is_sensitive_key("secretfile") is False
        assert is_sensitive_key("my_secretfile") is False

    def test_not_sensitive_normal_keys(self) -> None:
        from agentplane.scripts.onepanel.redaction import is_sensitive_key

        for key in ("hostname", "port", "username", "url", "name", "id"):
            assert is_sensitive_key(key) is False, f"{key} should NOT be sensitive"

    def test_empty_key(self) -> None:
        from agentplane.scripts.onepanel.redaction import is_sensitive_key

        assert is_sensitive_key("") is False
        assert is_sensitive_key("   ") is False

    def test_case_insensitive(self) -> None:
        from agentplane.scripts.onepanel.redaction import is_sensitive_key

        assert is_sensitive_key("PASSWORD") is True
        assert is_sensitive_key("Password") is True
        assert is_sensitive_key("APIKEY") is True

    def test_special_characters_normalized(self) -> None:
        from agentplane.scripts.onepanel.redaction import is_sensitive_key

        assert is_sensitive_key("api-key") is True
        assert is_sensitive_key("api_key") is True
        assert is_sensitive_key("my.token") is True

    def test_scrub_persisted_payload(self) -> None:
        from agentplane.scripts.onepanel.redaction import REDACTED, scrub_persisted_payload

        payload = {
            "name": "myapp",
            "password": "secret123",
            "nested": {
                "token": "abc",
                "safe": "value",
            },
            "items": [{"apikey": "key1", "id": "1"}],
        }
        result = scrub_persisted_payload(payload)
        assert result["name"] == "myapp"
        assert result["password"] == REDACTED
        assert result["nested"]["token"] == REDACTED
        assert result["nested"]["safe"] == "value"
        assert result["items"][0]["apikey"] == REDACTED
        assert result["items"][0]["id"] == "1"


# ---------------------------------------------------------------------------
# executor.py — TargetExecutor with mocked I/O
# ---------------------------------------------------------------------------


class TestExecutor:
    def _make_target(self, mode: str = "local") -> MagicMock:
        target = MagicMock()
        target.mode = mode
        target.api_config = MagicMock()
        target.api_config.connect_base_url = "https://panel.example.com"
        target.api_config.base_url = "https://panel.example.com"
        target.api_config.api_key = "mykey"
        target.api_config.security_entrance = None
        target.api_config.timeout_seconds = 10.0
        target.api_config.skip_tls_verify = False
        return target

    def test_target_executor_init(self) -> None:
        from agentplane.scripts.onepanel.executor import TargetExecutor

        target = self._make_target()
        executor = TargetExecutor(target)
        assert executor.target is target

    def test_api_request_routes_local(self) -> None:
        from agentplane.scripts.onepanel.executor import TargetExecutor

        target = self._make_target("local")
        executor = TargetExecutor(target)
        with patch.object(executor, "_local_api_request", return_value={"ok": True}) as mock_local:
            result = executor.api_request("GET", "/test")
            mock_local.assert_called_once_with("GET", "/test", None, query=None)
            assert result == {"ok": True}

    def test_api_request_routes_remote(self) -> None:
        from agentplane.scripts.onepanel.executor import TargetExecutor

        target = self._make_target("remote")
        executor = TargetExecutor(target)
        with patch.object(executor, "_remote_api_request", return_value={"ok": True}) as mock_remote:
            result = executor.api_request("GET", "/test")
            mock_remote.assert_called_once_with("GET", "/test", None, query=None)
            assert result == {"ok": True}

    def test_local_api_request_success(self) -> None:
        from agentplane.scripts.onepanel.executor import TargetExecutor

        target = self._make_target("local")
        executor = TargetExecutor(target)
        mock_response = {"status": 200, "body": {"code": 200, "data": {"id": 1}}}
        with patch("agentplane.scripts.onepanel.executor.run_command"):
            with patch(
                "agentplane.scripts.onepanel.client.send_signed_request",
                return_value=mock_response,
            ):
                result = executor._local_api_request("GET", "/api/test")
                assert result == {"id": 1}

    def test_local_api_request_error_response(self) -> None:
        from agentplane.scripts.onepanel.executor import TargetExecutor

        target = self._make_target("local")
        executor = TargetExecutor(target)
        mock_response = {"status": 200, "body": {"code": 500, "message": "fail"}}
        with patch("agentplane.scripts.onepanel.executor.run_command"):
            with patch(
                "agentplane.scripts.onepanel.client.send_signed_request",
                return_value=mock_response,
            ):
                with pytest.raises(RuntimeError):
                    executor._local_api_request("GET", "/api/test")

    def test_local_api_request_with_body(self) -> None:
        from agentplane.scripts.onepanel.executor import TargetExecutor

        target = self._make_target("local")
        executor = TargetExecutor(target)
        mock_response = {"status": 200, "body": {"code": 200, "data": {}}}
        with patch("agentplane.scripts.onepanel.executor.run_command"):
            with patch(
                "agentplane.scripts.onepanel.client.send_signed_request",
                return_value=mock_response,
            ) as mock_send:
                executor._local_api_request("POST", "/api/test", body={"key": "value"})
                call_kwargs = mock_send.call_args
                assert call_kwargs[1]["body_bytes"] == json.dumps({"key": "value"}, ensure_ascii=False).encode("utf-8")

    def test_shell_local_success(self) -> None:
        from agentplane.scripts.onepanel.executor import TargetExecutor

        target = self._make_target("local")
        target.linux_backend = MagicMock()
        target.linux_backend.shell_argv.return_value = ["echo", "hello"]

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "hello\n"
        mock_result.stderr = ""

        executor = TargetExecutor(target)
        with patch("agentplane.scripts.onepanel.executor.run_command", return_value=mock_result):
            with patch("agentplane.scripts.onepanel.executor.default_linux_backend", return_value=target.linux_backend):
                result = executor.shell("echo hello")
                assert result == "hello"

    def test_shell_local_failure(self) -> None:
        from agentplane.scripts.onepanel.executor import TargetExecutor

        target = self._make_target("local")
        target.linux_backend = MagicMock()
        target.linux_backend.shell_argv.return_value = ["false"]

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "error"

        executor = TargetExecutor(target)
        with patch("agentplane.scripts.onepanel.executor.run_command", return_value=mock_result):
            with patch("agentplane.scripts.onepanel.executor.default_linux_backend", return_value=target.linux_backend):
                with pytest.raises(RuntimeError, match="error"):
                    executor.shell("false")

    def test_shell_remote_success(self) -> None:
        from agentplane.scripts.onepanel.executor import TargetExecutor

        target = self._make_target("remote")
        mock_ssh = MagicMock()
        mock_ssh.local_ssh_args_for_shell.return_value = ["ssh", "echo", "hi"]
        target.build_ssh_target.return_value = mock_ssh

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "hi\n"
        mock_result.stderr = ""

        executor = TargetExecutor(target)
        with patch("agentplane.scripts.onepanel.executor.run_command", return_value=mock_result):
            result = executor.shell("echo hi")
            assert result == "hi"


# ---------------------------------------------------------------------------
# signed_request.py — skipped (uses bare `from client import`, not importable as package)
# ---------------------------------------------------------------------------
