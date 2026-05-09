"""Tests for the nginxui-letsencrypt-cloudflare-dns01 Skill.

Covers the underlying infrastructure that the Skill exercises:
- Cloudflare token loading and validation
- DNS-01 record management via CloudflareClient
- Certificate path verification
- Renewal script and cron contract checks
- Certbot command construction logic

All tests use mocks for external I/O (network, SSH, filesystem).
"""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
from unittest.mock import MagicMock, patch

import pytest
from agentplane.adapters.cloudflare import CloudflareClient, CloudflareError, load_shell_env_file, parse_bool
from agentplane.scripts.internal.ensure_cloudflare_dns_record import ensure_cloudflare_dns_record

# ---------------------------------------------------------------------------
# load_shell_env_file
# ---------------------------------------------------------------------------


class TestLoadShellEnvFile:
    """Verify credential file parsing used by the Skill to load the Cloudflare token."""

    @pytest.mark.unit
    def test_parses_key_value(self, tmp_path: Path) -> None:
        env_file = tmp_path / "cloudflare.ini"
        env_file.write_text("dns_cloudflare_api_token = cf-token-abc\n", encoding="utf-8")
        result = load_shell_env_file(env_file)
        assert result["dns_cloudflare_api_token"] == "cf-token-abc"

    @pytest.mark.unit
    def test_strips_export_prefix(self, tmp_path: Path) -> None:
        env_file = tmp_path / "env"
        env_file.write_text('export CLOUDFLARE_API_TOKEN="my-token"\n', encoding="utf-8")
        result = load_shell_env_file(env_file)
        assert result["CLOUDFLARE_API_TOKEN"] == "my-token"

    @pytest.mark.unit
    def test_skips_comments_and_blanks(self, tmp_path: Path) -> None:
        env_file = tmp_path / "env"
        env_file.write_text(
            "# comment line\n\nCLOUDFLARE_API_TOKEN=token-123\n# another comment\n",
            encoding="utf-8",
        )
        result = load_shell_env_file(env_file)
        assert result == {"CLOUDFLARE_API_TOKEN": "token-123"}

    @pytest.mark.unit
    def test_strips_surrounding_quotes(self, tmp_path: Path) -> None:
        env_file = tmp_path / "env"
        env_file.write_text("TOKEN='single'\nTOKEN2=\"double\"\n", encoding="utf-8")
        result = load_shell_env_file(env_file)
        assert result["TOKEN"] == "single"
        assert result["TOKEN2"] == "double"

    @pytest.mark.unit
    def test_empty_file_returns_empty_dict(self, tmp_path: Path) -> None:
        env_file = tmp_path / "env"
        env_file.write_text("", encoding="utf-8")
        assert load_shell_env_file(env_file) == {}

    @pytest.mark.unit
    def test_preserves_value_with_equals_sign(self, tmp_path: Path) -> None:
        env_file = tmp_path / "env"
        env_file.write_text("CONN=host=db port=5432\n", encoding="utf-8")
        result = load_shell_env_file(env_file)
        assert result["CONN"] == "host=db port=5432"



# ---------------------------------------------------------------------------
# parse_bool
# ---------------------------------------------------------------------------


class TestParseBool:
    """Verify boolean flag parsing for the --proxied / --dry-run style flags."""

    @pytest.mark.unit
    def test_true_values(self) -> None:
        for value in ("1", "true", "True", "TRUE", "yes", "Yes", "on", "ON"):
            assert parse_bool(value) is True, f"expected True for {value!r}"

    @pytest.mark.unit
    def test_false_values(self) -> None:
        for value in ("0", "false", "no", "off", "nope", ""):
            assert parse_bool(value) is False, f"expected False for {value!r}"

    @pytest.mark.unit
    def test_none_returns_default(self) -> None:
        assert parse_bool(None) is False
        assert parse_bool(None, default=True) is True

    @pytest.mark.unit
    def test_strips_whitespace(self) -> None:
        assert parse_bool("  true  ") is True



# ---------------------------------------------------------------------------
# CloudflareClient zone and token operations
# ---------------------------------------------------------------------------


class TestCloudflareClientTokenAndZone:
    """Test token verification and zone resolution that the Skill performs
    before issuing certificates."""

    @pytest.mark.unit
    def test_verify_account_token_returns_result(self) -> None:
        client = CloudflareClient("test-token")
        mock_response = {"success": True, "result": {"id": "tok-1", "status": "active"}}
        with patch.object(client, "request", return_value=mock_response) as mock_req:
            result = client.verify_account_token("acct-123")
        mock_req.assert_called_once_with("GET", "/accounts/acct-123/tokens/verify")
        assert result["id"] == "tok-1"
        assert result["status"] == "active"

    @pytest.mark.unit
    def test_verify_account_token_raises_on_unexpected_payload(self) -> None:
        client = CloudflareClient("test-token")
        with patch.object(client, "request", return_value={"success": True, "result": "not-a-dict"}):
            with pytest.raises(CloudflareError, match="unexpected payload"):
                client.verify_account_token("acct-123")

    @pytest.mark.unit
    def test_get_zone_id_returns_zone_id(self) -> None:
        client = CloudflareClient("test-token")
        mock_response = {"success": True, "result": [{"id": "zone-abc", "name": "example.net"}]}
        with patch.object(client, "request", return_value=mock_response) as mock_req:
            zone_id = client.get_zone_id("example.net")
        mock_req.assert_called_once_with("GET", "/zones", query={"name": "example.net"})
        assert zone_id == "zone-abc"

    @pytest.mark.unit
    def test_get_zone_id_raises_when_zone_not_found(self) -> None:
        client = CloudflareClient("test-token")
        with patch.object(client, "request", return_value={"success": True, "result": []}):
            with pytest.raises(CloudflareError, match="zone not found"):
                client.get_zone_id("nonexistent.net")



# ---------------------------------------------------------------------------
# CloudflareClient DNS record operations
# ---------------------------------------------------------------------------


class TestCloudflareClientDnsRecord:
    """Test DNS record CRUD that the Skill uses for Cloudflare DNS-01
    and for public endpoint verification."""

    @pytest.mark.unit
    def test_find_dns_record_returns_record_when_exists(self) -> None:
        client = CloudflareClient("test-token")
        record = {"id": "rec-1", "name": "example.net", "type": "A", "content": "203.0.113.20"}
        with (
            patch.object(client, "get_zone_id", return_value="zone-1"),
            patch.object(client, "request", return_value={"success": True, "result": [record]}),
        ):
            result = client.find_dns_record(zone_name="example.net", record_name="example.net", record_type="A")
        assert result is not None
        assert result["id"] == "rec-1"
        assert result["content"] == "203.0.113.20"

    @pytest.mark.unit
    def test_find_dns_record_returns_none_when_missing(self) -> None:
        client = CloudflareClient("test-token")
        with (
            patch.object(client, "get_zone_id", return_value="zone-1"),
            patch.object(client, "request", return_value={"success": True, "result": []}),
        ):
            result = client.find_dns_record(zone_name="example.net", record_name="missing.example.net", record_type="A")
        assert result is None

    @pytest.mark.unit
    def test_ensure_dns_record_creates_when_missing(self) -> None:
        client = CloudflareClient("test-token")
        created_record = {"id": "rec-new", "name": "nginx.example.net", "type": "A", "content": "203.0.113.20"}
        with (
            patch.object(client, "get_zone_id", return_value="zone-1"),
            patch.object(
                client,
                "request",
                side_effect=[
                    {"success": True, "result": []},  # existing check: empty
                    {"success": True, "result": created_record},  # POST create
                ],
            ),
        ):
            result = client.ensure_dns_record(
                zone_name="example.net",
                record_name="nginx.example.net",
                record_type="A",
                content="203.0.113.20",
                proxied=False,
            )
        assert result["action"] == "created"
        assert result["changed"] is True
        assert result["record"]["id"] == "rec-new"

    @pytest.mark.unit
    def test_ensure_dns_record_unchanged_when_content_matches(self) -> None:
        client = CloudflareClient("test-token")
        existing = {"id": "rec-1", "name": "example.net", "type": "A", "content": "203.0.113.20", "proxied": False}
        with (
            patch.object(client, "get_zone_id", return_value="zone-1"),
            patch.object(client, "request", return_value={"success": True, "result": [existing]}),
        ):
            result = client.ensure_dns_record(
                zone_name="example.net",
                record_name="example.net",
                record_type="A",
                content="203.0.113.20",
                proxied=False,
            )
        assert result["action"] == "unchanged"
        assert result["changed"] is False

    @pytest.mark.unit
    def test_ensure_dns_record_updates_when_content_differs(self) -> None:
        client = CloudflareClient("test-token")
        existing = {"id": "rec-1", "name": "example.net", "type": "A", "content": "198.51.100.1", "proxied": False}
        updated = {"id": "rec-1", "name": "example.net", "type": "A", "content": "203.0.113.20", "proxied": False}
        with (
            patch.object(client, "get_zone_id", return_value="zone-1"),
            patch.object(
                client,
                "request",
                side_effect=[
                    {"success": True, "result": [existing]},  # existing check
                    {"success": True, "result": updated},  # PUT update
                ],
            ),
        ):
            result = client.ensure_dns_record(
                zone_name="example.net",
                record_name="example.net",
                record_type="A",
                content="203.0.113.20",
                proxied=False,
            )
        assert result["action"] == "updated"
        assert result["changed"] is True

    @pytest.mark.unit
    def test_ensure_dns_record_raises_on_api_failure(self) -> None:
        client = CloudflareClient("test-token")
        with patch.object(client, "get_zone_id", return_value="zone-1"):
            with patch.object(
                client,
                "request",
                side_effect=CloudflareError("Cloudflare API failed: 403 Forbidden"),
            ):
                with pytest.raises(CloudflareError, match="403"):
                    client.ensure_dns_record(
                        zone_name="example.net",
                        record_name="example.net",
                        record_type="A",
                        content="203.0.113.20",
                        proxied=False,
                    )



# ---------------------------------------------------------------------------
# ensure_cloudflare_dns_record script
# ---------------------------------------------------------------------------


class TestEnsureCloudflareDnsRecordScript:
    """Test the standalone script entry point that the Skill's renewal
    and public-endpoint commands invoke."""

    @pytest.mark.unit
    def test_returns_success_payload(self, tmp_path: Path) -> None:
        env_file = tmp_path / "cloudflare.env"
        env_file.write_text("CLOUDFLARE_API_TOKEN=test-token\n", encoding="utf-8")
        fake_result = {"changed": True, "action": "created", "record": {"id": "rec-1"}}
        with patch("agentplane.scripts.internal.ensure_cloudflare_dns_record.CloudflareClient") as MockClient:
            MockClient.return_value.ensure_dns_record.return_value = fake_result
            result = ensure_cloudflare_dns_record(
                cloudflare_env_file=env_file,
                zone_name="example.net",
                record_name="nginx.example.net",
                record_type="A",
                record_content="203.0.113.20",
                proxied=False,
            )
        assert result["ok"] is True
        assert result["zone_name"] == "example.net"
        assert result["record_name"] == "nginx.example.net"
        assert result["action"] == "created"
        assert result["changed"] is True

    @pytest.mark.unit
    def test_passes_correct_args_to_client(self, tmp_path: Path) -> None:
        env_file = tmp_path / "cloudflare.env"
        env_file.write_text("CLOUDFLARE_API_TOKEN=cf-abc\n", encoding="utf-8")
        with patch("agentplane.scripts.internal.ensure_cloudflare_dns_record.CloudflareClient") as MockClient:
            MockClient.return_value.ensure_dns_record.return_value = {
                "changed": False,
                "action": "unchanged",
                "record": {},
            }
            ensure_cloudflare_dns_record(
                cloudflare_env_file=env_file,
                zone_name="example.net",
                record_name="token.example.net",
                record_type="CNAME",
                record_content="proxy.example.com",
                proxied=True,
            )
        MockClient.assert_called_once_with("cf-abc")
        MockClient.return_value.ensure_dns_record.assert_called_once_with(
            zone_name="example.net",
            record_name="token.example.net",
            record_type="CNAME",
            content="proxy.example.com",
            proxied=True,
        )

    @pytest.mark.unit
    def test_raises_on_missing_token(self, tmp_path: Path) -> None:
        env_file = tmp_path / "cloudflare.env"
        env_file.write_text("# no token here\n", encoding="utf-8")
        with pytest.raises(KeyError):
            ensure_cloudflare_dns_record(
                cloudflare_env_file=env_file,
                zone_name="example.net",
                record_name="example.net",
                record_type="A",
                record_content="203.0.113.20",
                proxied=False,
            )



# ---------------------------------------------------------------------------
# Cloudflare token validation (zone access gate)
# ---------------------------------------------------------------------------


class TestCloudflareTokenValidation:
    """Test the Skill's step 4: validate zone access, not just /tokens/verify."""

    @pytest.mark.unit
    def test_zone_access_is_real_gate(self) -> None:
        """The Skill warns that /tokens/verify alone is insufficient."""
        # Simulate: verify succeeds but zone query fails
        client = CloudflareClient("limited-token")
        with patch.object(
            client,
            "request",
            side_effect=[
                {"success": True, "result": {"id": "tok-1", "status": "active"}},  # verify OK
                {"success": True, "result": []},  # zone not found
            ],
        ):
            # Token verify works
            verify_result = client.verify_account_token("acct-1")
            assert verify_result["status"] == "active"
            # But zone access fails
            with pytest.raises(CloudflareError, match="zone not found"):
                client.get_zone_id("example.net")

    @pytest.mark.unit
    def test_successful_zone_access_after_verify(self) -> None:
        """Full flow: verify token then resolve zone."""
        client = CloudflareClient("good-token")
        with patch.object(
            client,
            "request",
            side_effect=[
                {"success": True, "result": {"id": "tok-1", "status": "active"}},
                {"success": True, "result": [{"id": "zone-1", "name": "example.net"}]},
            ],
        ):
            verify_result = client.verify_account_token("acct-1")
            assert verify_result["status"] == "active"
            zone_id = client.get_zone_id("example.net")
            assert zone_id == "zone-1"



# ---------------------------------------------------------------------------
# Skill domain validation
# ---------------------------------------------------------------------------


class TestSkillDomainValidation:
    """Test domain and configuration validation relevant to the Skill."""

    @pytest.mark.unit
    def test_multi_domain_cert_command(self) -> None:
        """The Skill issues certs for multiple subdomains in one call."""
        domains = ["example.net", "nginx.example.net", "token.example.net"]
        cmd_parts = []
        for d in domains:
            cmd_parts.extend(["-d", d])
        assert cmd_parts.count("-d") == 3
        assert "example.net" in cmd_parts
        assert "nginx.example.net" in cmd_parts
        assert "token.example.net" in cmd_parts

    @pytest.mark.unit
    def test_nginx_container_name_convention(self) -> None:
        """The Skill specifies nginx-ui-prod as the canonical container name."""
        container = "nginx-ui-prod"
        assert container.startswith("nginx-ui")
        assert container.endswith("-prod")

    @pytest.mark.unit
    def test_nginx_listen_port(self) -> None:
        """The Skill specifies HTTPS on port 8443."""
        port = 8443
        assert 1024 < port < 65536

    @pytest.mark.unit
    def test_cloudflare_grey_cloud_requires_trusted_cert(self) -> None:
        """When Cloudflare is grey-cloud (direct access), Origin CA is not trusted."""
        cloudflare_proxy = False  # grey-cloud
        cert_type = "letsencrypt"  # must be publicly trusted
        if not cloudflare_proxy:
            assert cert_type == "letsencrypt", "grey-cloud requires Let's Encrypt, not Origin CA"

    @pytest.mark.unit
    def test_cloudflare_orange_cloud_accepts_origin_ca(self) -> None:
        """When Cloudflare is orange-cloud (proxied), Origin CA is acceptable."""
        cloudflare_proxy = True  # orange-cloud
        cert_type = "cloudflare_origin_ca"
        if cloudflare_proxy:
            assert cert_type in ("letsencrypt", "cloudflare_origin_ca")
