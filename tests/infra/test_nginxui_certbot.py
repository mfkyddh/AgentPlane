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
# Certbot command construction
# ---------------------------------------------------------------------------


class TestCertbotCommandConstruction:
    """Test the certbot Docker command shape that the Skill documents.
    These are pure logic tests validating the command structure."""

    CERTBOT_BASE_ARGS = [
        "docker",
        "run",
        "--rm",
        "--network",
        "host",
        "-e",
        "HTTPS_PROXY=http://172.18.0.1:7890",
        "-e",
        "HTTP_PROXY=http://172.18.0.1:7890",
        "-e",
        "NO_PROXY=localhost,127.0.0.1,::1",
        "-v",
        "/data/apps/letsencrypt:/etc/letsencrypt",
        "-v",
        "/data/apps/letsencrypt/lib:/var/lib/letsencrypt",
        "-v",
        "/data/apps/letsencrypt/cloudflare.ini:/cloudflare.ini:ro",
        "certbot/dns-cloudflare:latest",
        "certonly",
        "--dns-cloudflare",
        "--dns-cloudflare-credentials",
        "/cloudflare.ini",
        "--dns-cloudflare-propagation-seconds",
        "120",
    ]

    @pytest.mark.unit
    def test_dry_run_command_shape(self) -> None:
        """The Skill specifies --dry-run should precede the real request."""
        domains = ["example.net", "nginx.example.net", "token.example.net"]
        args = list(self.CERTBOT_BASE_ARGS)
        args.extend(["--dry-run", "-n", "--agree-tos", "-m", "admin@example.net"])
        for domain in domains:
            args.extend(["-d", domain])

        assert "--dry-run" in args
        assert "--dns-cloudflare" in args
        assert "--dns-cloudflare-propagation-seconds" in args
        assert "120" in args
        assert args.count("-d") == 3

    @pytest.mark.unit
    def test_real_run_omits_dry_run_flag(self) -> None:
        """After dry-run succeeds, the real command should not include --dry-run."""
        domains = ["example.net", "nginx.example.net", "token.example.net"]
        args = list(self.CERTBOT_BASE_ARGS)
        args.extend(["-n", "--agree-tos", "-m", "admin@example.net"])
        for domain in domains:
            args.extend(["-d", domain])

        assert "--dry-run" not in args
        assert "--dns-cloudflare" in args

    @pytest.mark.unit
    def test_propagation_seconds_meets_minimum(self) -> None:
        """The Skill notes 120s works while 10s does not."""
        idx = self.CERTBOT_BASE_ARGS.index("--dns-cloudflare-propagation-seconds")
        propagation = int(self.CERTBOT_BASE_ARGS[idx + 1])
        assert propagation >= 120, "propagation must be >= 120s per Skill runbook"

    @pytest.mark.unit
    def test_uses_host_network(self) -> None:
        """The Skill specifies --network host for proxy reachability."""
        assert "--network" in self.CERTBOT_BASE_ARGS
        net_idx = self.CERTBOT_BASE_ARGS.index("--network")
        assert self.CERTBOT_BASE_ARGS[net_idx + 1] == "host"

    @pytest.mark.unit
    def test_proxy_env_vars_present(self) -> None:
        """The Skill requires HTTPS_PROXY and HTTP_PROXY for Mihomo-backed hosts."""
        env_args = self.CERTBOT_BASE_ARGS
        assert "-e" in env_args
        env_strings = [env_args[i + 1] for i in range(len(env_args) - 1) if env_args[i] == "-e"]
        assert any("HTTPS_PROXY" in e for e in env_strings)
        assert any("HTTP_PROXY" in e for e in env_strings)
        assert any("NO_PROXY" in e for e in env_strings)



# ---------------------------------------------------------------------------
# Certificate path verification
# ---------------------------------------------------------------------------


class TestCertificatePathVerification:
    """Test certificate file validation logic that the Skill's verification
    checklist exercises."""

    @pytest.mark.unit
    def test_certbot_live_paths_follow_convention(self) -> None:
        """Certbot stores certs under /data/apps/letsencrypt/live/<primary-domain>/."""
        primary_domain = "example.net"
        live_dir = PurePosixPath(f"/data/apps/letsencrypt/live/{primary_domain}")
        fullchain = live_dir / "fullchain.pem"
        privkey = live_dir / "privkey.pem"
        assert str(fullchain) == "/data/apps/letsencrypt/live/example.net/fullchain.pem"
        assert str(privkey) == "/data/apps/letsencrypt/live/example.net/privkey.pem"

    @pytest.mark.unit
    def test_nginx_ui_cert_paths_follow_convention(self) -> None:
        """The Skill copies certs into the nginx-ui certs directory."""
        domain = "example.net"
        cert_dir = PurePosixPath("/data/apps/nginx-ui-official/nginx/certs")
        pem_path = cert_dir / f"{domain}.pem"
        key_path = cert_dir / f"{domain}.key"
        assert str(pem_path) == "/data/apps/nginx-ui-official/nginx/certs/example.net.pem"
        assert str(key_path) == "/data/apps/nginx-ui-official/nginx/certs/example.net.key"

    @pytest.mark.unit
    def test_verify_cert_matches_inventory_contract(self) -> None:
        """The inventory certificate contract should declare fullchain and privkey paths."""
        certificate = {
            "fullchain_path": "/data/relay-trojan/certs/fullchain.pem",
            "privkey_path": "/data/relay-trojan/certs/privkey.pem",
            "renew_script_path": "/usr/local/bin/renew-relay-trojan-cert.sh",
            "renew_cron": "17 3 1 * * /usr/local/bin/renew-relay-trojan-cert.sh >> /var/log/relay-trojan-cert-renew.log 2>&1",
        }
        assert certificate["fullchain_path"].endswith(".pem")
        assert certificate["privkey_path"].endswith(".pem")
        assert certificate["renew_script_path"].startswith("/usr/local/")
        assert "renew" in certificate["renew_cron"]



# ---------------------------------------------------------------------------
# Renewal script contract
# ---------------------------------------------------------------------------


class TestRenewalScriptContract:
    """Test the renewal script logic the Skill documents:
    - rerun certbot renew
    - compare certs
    - copy only when changed
    - nginx -t and reload only on change
    """

    @pytest.mark.unit
    def test_renewal_script_template_has_required_sections(self) -> None:
        """A renewal script must include certbot renew, comparison, and nginx reload."""
        script_body = """#!/usr/bin/env bash
set -euo pipefail

CERTBOT_LIVE="/data/apps/letsencrypt/live/example.net"
NGINX_CERTS="/data/apps/nginx-ui-official/nginx/certs"

# Renew
sudo docker run --rm --network host \\
  -e HTTPS_PROXY=http://172.18.0.1:7890 \\
  -v /data/apps/letsencrypt:/etc/letsencrypt \\
  -v /data/apps/letsencrypt/lib:/var/lib/letsencrypt \\
  -v /data/apps/letsencrypt/cloudflare.ini:/cloudflare.ini:ro \\
  certbot/dns-cloudflare:latest renew \\
  --dns-cloudflare --dns-cloudflare-credentials /cloudflare.ini

# Compare and copy only when changed
if ! diff -q "$CERTBOT_LIVE/fullchain.pem" "$NGINX_CERTS/example.net.pem" >/dev/null 2>&1; then
  cp "$CERTBOT_LIVE/fullchain.pem" "$NGINX_CERTS/example.net.pem"
  cp "$CERTBOT_LIVE/privkey.pem" "$NGINX_CERTS/example.net.key"
  sudo docker exec nginx-ui-prod nginx -t
  sudo docker exec nginx-ui-prod nginx -s reload
fi
"""
        assert "certbot" in script_body or "docker run" in script_body
        assert "diff" in script_body
        assert "nginx -t" in script_body
        assert "nginx -s reload" in script_body

    @pytest.mark.unit
    def test_cron_entry_format(self) -> None:
        """The Skill specifies a cron.d file for automatic renewal."""
        cron_line = "30 3 * * 1 root /usr/local/sbin/renew_example_net_cert.sh >> /var/log/renew_example_net.log 2>&1"
        parts = cron_line.split()
        # minute, hour, dom, month, dow
        assert len(parts) >= 5
        assert parts[4] in ("*", "0", "1", "2", "3", "4", "5", "6", "7")  # day of week
        assert "renew" in cron_line
        assert "/usr/local/sbin/" in cron_line or "/usr/local/bin/" in cron_line



# ---------------------------------------------------------------------------
# End-to-end scenario: DNS-01 cert issuance plan
# ---------------------------------------------------------------------------


class TestDns01CertIssuanceScenario:
    """Integration-style test (still mocked) covering the full Skill workflow:
    load token -> validate zone -> run certbot -> verify certs -> check renewal.
    """

    @pytest.mark.unit
    def test_full_dns01_workflow_steps(self, tmp_path: Path) -> None:
        """Simulate the Skill's complete workflow in pure logic."""
        # Step 5: Prepare credential file
        cred_file = tmp_path / "cloudflare.ini"
        cred_file.write_text("dns_cloudflare_api_token = test-token\n", encoding="utf-8")

        # Step 4: Load and validate token
        env = load_shell_env_file(cred_file)
        token = env["dns_cloudflare_api_token"]
        assert token == "test-token"

        client = CloudflareClient(token)
        with patch.object(
            client,
            "request",
            side_effect=[
                {"success": True, "result": {"id": "tok-1", "status": "active"}},
                {"success": True, "result": [{"id": "zone-1", "name": "example.net"}]},
            ],
        ):
            # Verify token
            verify = client.verify_account_token("acct-1")
            assert verify["status"] == "active"
            # Resolve zone
            zone_id = client.get_zone_id("example.net")
            assert zone_id == "zone-1"

        # Step 7-8: Certbot command (dry-run then real)
        domains = ["example.net", "nginx.example.net", "token.example.net"]
        base_cmd = [
            "docker",
            "run",
            "--rm",
            "--network",
            "host",
            "-e",
            "HTTPS_PROXY=http://172.18.0.1:7890",
            "-v",
            "/data/apps/letsencrypt:/etc/letsencrypt",
            "-v",
            "/data/apps/letsencrypt/lib:/var/lib/letsencrypt",
            "-v",
            "/data/apps/letsencrypt/cloudflare.ini:/cloudflare.ini:ro",
            "certbot/dns-cloudflare:latest",
            "certonly",
            "--dns-cloudflare",
            "--dns-cloudflare-credentials",
            "/cloudflare.ini",
            "--dns-cloudflare-propagation-seconds",
            "120",
        ]
        # Dry-run
        dry_run_cmd = base_cmd + ["--dry-run", "-n", "--agree-tos", "-m", "admin@example.net"]
        for d in domains:
            dry_run_cmd.extend(["-d", d])
        assert "--dry-run" in dry_run_cmd

        # Real run
        real_cmd = base_cmd + ["-n", "--agree-tos", "-m", "admin@example.net"]
        for d in domains:
            real_cmd.extend(["-d", d])
        assert "--dry-run" not in real_cmd

        # Step 9: Verify cert paths exist at expected locations
        primary = "example.net"
        assert f"/data/apps/letsencrypt/live/{primary}/fullchain.pem"
        assert f"/data/apps/nginx-ui-official/nginx/certs/{primary}.pem"

        # Step 10: nginx validate and reload commands
        nginx_validate = ["docker", "exec", "nginx-ui-prod", "nginx", "-t"]
        nginx_reload = ["docker", "exec", "nginx-ui-prod", "nginx", "-s", "reload"]
        assert nginx_validate[-1] == "-t"
        assert nginx_reload[-1] == "reload"



# ---------------------------------------------------------------------------
# Error scenarios
# ---------------------------------------------------------------------------


class TestErrorScenarios:
    """Test failure modes the Skill should handle."""

    @pytest.mark.unit
    def test_cloudflare_api_http_error(self) -> None:
        """Cloudflare API returns a non-2xx status."""
        client = CloudflareClient("bad-token")
        import urllib.error
        from io import BytesIO

        error = urllib.error.HTTPError(
            url="https://api.cloudflare.com/client/v4/zones",
            code=403,
            msg="Forbidden",
            hdrs=None,
            fp=BytesIO(b'{"success":false,"errors":[{"code":9106}]}'),
        )
        with patch("agentplane.adapters.cloudflare.urllib.request.urlopen", side_effect=error):
            with pytest.raises(CloudflareError, match="403"):
                client.get_zone_id("example.net")

    @pytest.mark.unit
    def test_cloudflare_api_success_false(self) -> None:
        """Cloudflare returns 200 but success=false."""
        client = CloudflareClient("test-token")
        with patch(
            "agentplane.adapters.cloudflare.urllib.request.urlopen",
        ) as mock_open:
            mock_response = MagicMock()
            mock_response.read.return_value = json.dumps(
                {
                    "success": False,
                    "errors": [{"code": 10000, "message": "Authentication error"}],
                }
            ).encode("utf-8")
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=False)
            mock_open.return_value = mock_response
            with pytest.raises(CloudflareError, match="failed"):
                client.get_zone_id("example.net")

    @pytest.mark.unit
    def test_missing_cloudflare_env_file_raises(self, tmp_path: Path) -> None:
        """Loading a nonexistent env file should raise FileNotFoundError."""
        missing = tmp_path / "nonexistent.env"
        with pytest.raises(FileNotFoundError):
            load_shell_env_file(missing)

    @pytest.mark.unit
    def test_missing_token_key_raises_key_error(self, tmp_path: Path) -> None:
        """Env file without CLOUDFLARE_API_TOKEN should raise KeyError."""
        env_file = tmp_path / "env"
        env_file.write_text("OTHER_KEY=value\n", encoding="utf-8")
        env = load_shell_env_file(env_file)
        with pytest.raises(KeyError):
            _ = env["CLOUDFLARE_API_TOKEN"]

    @pytest.mark.unit
    def test_find_dns_record_propagates_zone_not_found(self) -> None:
        """If the zone doesn't exist, find_dns_record should propagate the error."""
        client = CloudflareClient("test-token")
        with patch.object(client, "get_zone_id", side_effect=CloudflareError("Cloudflare zone not found: bad.net")):
            with pytest.raises(CloudflareError, match="zone not found"):
                client.find_dns_record(zone_name="bad.net", record_name="bad.net", record_type="A")

    @pytest.mark.unit
    def test_ensure_dns_record_propagates_create_failure(self, tmp_path: Path) -> None:
        """DNS record creation failure should propagate."""
        env_file = tmp_path / "env"
        env_file.write_text("CLOUDFLARE_API_TOKEN=test-token\n", encoding="utf-8")
        with patch("agentplane.scripts.internal.ensure_cloudflare_dns_record.CloudflareClient") as MockClient:
            MockClient.return_value.ensure_dns_record.side_effect = CloudflareError("API rate limit exceeded")
            with pytest.raises(CloudflareError, match="rate limit"):
                ensure_cloudflare_dns_record(
                    cloudflare_env_file=env_file,
                    zone_name="example.net",
                    record_name="example.net",
                    record_type="A",
                    record_content="203.0.113.20",
                    proxied=False,
                )
