from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from agentplane.domain.service.models import ServiceDefinition
from tests.support.constants import DOMAIN_RELAY, IP_CLOUDFLARE_RECORD, TARGET_PROD

pytestmark = pytest.mark.unit

SERVICE_NAME = "relay-trojan"

_FAKE_DEFINITION = ServiceDefinition(
    name=SERVICE_NAME,
    runtime_kind="docker",
    control_plane="compose",
    supported_operations=("restart", "reconcile"),
    supported_targets=(TARGET_PROD,),
    inventory_key=SERVICE_NAME,
    metadata={},
)

_DECLARED_WITH_ENDPOINT: dict[str, Any] = {
    "control_plane": "compose",
    "container_name": "relay-trojan-prod",
    "public_endpoint": {
        "domain": DOMAIN_RELAY,
        "port": 24443,
        "protocol": "trojan",
        "transport": "tcp+tls",
        "dns": {
            "provider": "cloudflare",
            "zone_name": "example.org",
            "record_type": "A",
            "record_content": IP_CLOUDFLARE_RECORD,
            "proxied": False,
        },
        "certificate": {
            "fullchain_path": "/data/relay-trojan/certs/fullchain.pem",
            "privkey_path": "/data/relay-trojan/certs/privkey.pem",
            "renew_script_path": "/usr/local/bin/renew-relay-trojan-cert.sh",
            "renew_cron": "17 3 1 * * /usr/local/bin/renew-relay-trojan-cert.sh",
        },
    },
}

_DECLARED_DNS_ONLY: dict[str, Any] = {
    "control_plane": "compose",
    "container_name": "relay-trojan-prod",
    "public_endpoint": {
        "domain": DOMAIN_RELAY,
        "dns": {
            "provider": "cloudflare",
            "zone_name": "example.org",
            "record_type": "A",
            "record_content": IP_CLOUDFLARE_RECORD,
            "proxied": False,
        },
    },
}

_CF_ENV_FILE = Path("/fake/cloudflare.env")


def _make_cf_record(content: str = IP_CLOUDFLARE_RECORD, proxied: bool = False) -> dict[str, Any]:
    return {"id": "rec-1", "name": DOMAIN_RELAY, "type": "A", "content": content, "proxied": proxied}


def _mock_run_shell_command_ok(*_a: Any, **_kw: Any) -> dict[str, Any]:
    return {"ok": True, "returncode": 0, "stdout": "", "stderr": ""}


def _mock_run_shell_command_fail(*_a: Any, **_kw: Any) -> dict[str, Any]:
    return {"ok": False, "returncode": 1, "stdout": "", "stderr": "not found"}


class TestVerifyServicePublicEndpoint:
    def test_all_checks_pass_dns_and_cert(self) -> None:
        mock_cf = MagicMock()
        mock_cf.return_value.find_dns_record.return_value = _make_cf_record()
        mock_load_env = MagicMock(return_value={"CLOUDFLARE_API_TOKEN": "fake-token"})

        with (
            patch(
                "agentplane.domain.service.public_endpoint.resolve_service",
                return_value=(_FAKE_DEFINITION, _DECLARED_WITH_ENDPOINT),
            ),
            patch("agentplane.domain.service.public_endpoint.CloudflareClient", mock_cf),
            patch("agentplane.domain.service.public_endpoint.load_shell_env_file", mock_load_env),
            patch("agentplane.domain.service.public_endpoint.run_shell_command", _mock_run_shell_command_ok),
        ):
            from agentplane.domain.service.public_endpoint import verify_service_public_endpoint

            result = verify_service_public_endpoint(
                Path("/repo"), TARGET_PROD, SERVICE_NAME, cloudflare_env_file=_CF_ENV_FILE
            )

        assert result["ok"] is True
        assert result["failures"] == []
        assert result["checks"]["public_endpoint_declared"]["ok"] is True
        assert result["checks"]["dns_exists"]["ok"] is True
        assert result["checks"]["dns_content"]["ok"] is True
        assert result["checks"]["dns_proxied"]["ok"] is True
        assert result["checks"]["cert_fullchain_readable"]["ok"] is True
        assert result["checks"]["cert_privkey_readable"]["ok"] is True
        assert result["checks"]["renew_script_executable"]["ok"] is True
        assert result["checks"]["renew_cron_present"]["ok"] is True

    def test_dns_record_missing(self) -> None:
        mock_cf = MagicMock()
        mock_cf.return_value.find_dns_record.return_value = None
        mock_load_env = MagicMock(return_value={"CLOUDFLARE_API_TOKEN": "fake-token"})

        with (
            patch(
                "agentplane.domain.service.public_endpoint.resolve_service",
                return_value=(_FAKE_DEFINITION, _DECLARED_WITH_ENDPOINT),
            ),
            patch("agentplane.domain.service.public_endpoint.CloudflareClient", mock_cf),
            patch("agentplane.domain.service.public_endpoint.load_shell_env_file", mock_load_env),
            patch("agentplane.domain.service.public_endpoint.run_shell_command", _mock_run_shell_command_ok),
        ):
            from agentplane.domain.service.public_endpoint import verify_service_public_endpoint

            result = verify_service_public_endpoint(
                Path("/repo"), TARGET_PROD, SERVICE_NAME, cloudflare_env_file=_CF_ENV_FILE
            )

        assert result["ok"] is False
        assert "dns_exists" in result["failures"]
        assert result["checks"]["dns_exists"]["ok"] is False
        assert result["checks"]["dns_content"]["actual"] is None

    def test_dns_content_mismatch(self) -> None:
        mock_cf = MagicMock()
        mock_cf.return_value.find_dns_record.return_value = _make_cf_record(content="1.2.3.4")
        mock_load_env = MagicMock(return_value={"CLOUDFLARE_API_TOKEN": "fake-token"})

        with (
            patch(
                "agentplane.domain.service.public_endpoint.resolve_service",
                return_value=(_FAKE_DEFINITION, _DECLARED_WITH_ENDPOINT),
            ),
            patch("agentplane.domain.service.public_endpoint.CloudflareClient", mock_cf),
            patch("agentplane.domain.service.public_endpoint.load_shell_env_file", mock_load_env),
            patch("agentplane.domain.service.public_endpoint.run_shell_command", _mock_run_shell_command_ok),
        ):
            from agentplane.domain.service.public_endpoint import verify_service_public_endpoint

            result = verify_service_public_endpoint(
                Path("/repo"), TARGET_PROD, SERVICE_NAME, cloudflare_env_file=_CF_ENV_FILE
            )

        assert result["ok"] is False
        assert "dns_content" in result["failures"]
        assert result["checks"]["dns_content"]["actual"] == "1.2.3.4"
        assert result["checks"]["dns_content"]["expected"] == IP_CLOUDFLARE_RECORD

    def test_dns_proxied_mismatch(self) -> None:
        mock_cf = MagicMock()
        mock_cf.return_value.find_dns_record.return_value = _make_cf_record(proxied=True)
        mock_load_env = MagicMock(return_value={"CLOUDFLARE_API_TOKEN": "fake-token"})

        with (
            patch(
                "agentplane.domain.service.public_endpoint.resolve_service",
                return_value=(_FAKE_DEFINITION, _DECLARED_WITH_ENDPOINT),
            ),
            patch("agentplane.domain.service.public_endpoint.CloudflareClient", mock_cf),
            patch("agentplane.domain.service.public_endpoint.load_shell_env_file", mock_load_env),
            patch("agentplane.domain.service.public_endpoint.run_shell_command", _mock_run_shell_command_ok),
        ):
            from agentplane.domain.service.public_endpoint import verify_service_public_endpoint

            result = verify_service_public_endpoint(
                Path("/repo"), TARGET_PROD, SERVICE_NAME, cloudflare_env_file=_CF_ENV_FILE
            )

        assert result["ok"] is False
        assert "dns_proxied" in result["failures"]
        assert result["checks"]["dns_proxied"]["actual"] is True
        assert result["checks"]["dns_proxied"]["expected"] is False

    def test_certificate_files_not_readable(self) -> None:
        mock_cf = MagicMock()
        mock_cf.return_value.find_dns_record.return_value = _make_cf_record()
        mock_load_env = MagicMock(return_value={"CLOUDFLARE_API_TOKEN": "fake-token"})

        with (
            patch(
                "agentplane.domain.service.public_endpoint.resolve_service",
                return_value=(_FAKE_DEFINITION, _DECLARED_WITH_ENDPOINT),
            ),
            patch("agentplane.domain.service.public_endpoint.CloudflareClient", mock_cf),
            patch("agentplane.domain.service.public_endpoint.load_shell_env_file", mock_load_env),
            patch("agentplane.domain.service.public_endpoint.run_shell_command", _mock_run_shell_command_fail),
        ):
            from agentplane.domain.service.public_endpoint import verify_service_public_endpoint

            result = verify_service_public_endpoint(
                Path("/repo"), TARGET_PROD, SERVICE_NAME, cloudflare_env_file=_CF_ENV_FILE
            )

        assert result["ok"] is False
        assert "cert_fullchain_readable" in result["failures"]
        assert "cert_privkey_readable" in result["failures"]
        assert "renew_script_executable" in result["failures"]
        assert "renew_cron_present" in result["failures"]

    def test_dns_only_no_certificate(self) -> None:
        mock_cf = MagicMock()
        mock_cf.return_value.find_dns_record.return_value = _make_cf_record()
        mock_load_env = MagicMock(return_value={"CLOUDFLARE_API_TOKEN": "fake-token"})

        with (
            patch(
                "agentplane.domain.service.public_endpoint.resolve_service",
                return_value=(_FAKE_DEFINITION, _DECLARED_DNS_ONLY),
            ),
            patch("agentplane.domain.service.public_endpoint.CloudflareClient", mock_cf),
            patch("agentplane.domain.service.public_endpoint.load_shell_env_file", mock_load_env),
        ):
            from agentplane.domain.service.public_endpoint import verify_service_public_endpoint

            result = verify_service_public_endpoint(
                Path("/repo"), TARGET_PROD, SERVICE_NAME, cloudflare_env_file=_CF_ENV_FILE
            )

        assert result["ok"] is True
        assert "cert_fullchain_readable" not in result["checks"]

    def test_unsupported_dns_provider_raises(self) -> None:
        declared = {
            "public_endpoint": {
                "domain": "test.example.com",
                "dns": {
                    "provider": "route53",
                    "zone_name": "example.com",
                    "record_type": "A",
                    "record_content": "1.2.3.4",
                },
            }
        }
        with patch(
            "agentplane.domain.service.public_endpoint.resolve_service", return_value=(_FAKE_DEFINITION, declared)
        ):
            from agentplane.domain.service.public_endpoint import verify_service_public_endpoint

            with pytest.raises(ValueError, match="unsupported public endpoint dns provider"):
                verify_service_public_endpoint(
                    Path("/repo"), TARGET_PROD, SERVICE_NAME, cloudflare_env_file=_CF_ENV_FILE
                )

    def test_missing_cloudflare_env_file_raises(self) -> None:
        with patch(
            "agentplane.domain.service.public_endpoint.resolve_service",
            return_value=(_FAKE_DEFINITION, _DECLARED_DNS_ONLY),
        ):
            from agentplane.domain.service.public_endpoint import verify_service_public_endpoint

            with pytest.raises(ValueError, match="--cloudflare-env-file"):
                verify_service_public_endpoint(Path("/repo"), TARGET_PROD, SERVICE_NAME, cloudflare_env_file=None)

    def test_no_public_endpoint_contract_raises(self) -> None:
        declared = {"control_plane": "compose", "container_name": "relay-trojan-prod"}
        with patch(
            "agentplane.domain.service.public_endpoint.resolve_service", return_value=(_FAKE_DEFINITION, declared)
        ):
            from agentplane.domain.service.public_endpoint import verify_service_public_endpoint

            with pytest.raises(ValueError, match="has no public_endpoint contract"):
                verify_service_public_endpoint(
                    Path("/repo"), TARGET_PROD, SERVICE_NAME, cloudflare_env_file=_CF_ENV_FILE
                )

    def test_service_not_declared_raises(self) -> None:
        with patch("agentplane.domain.service.public_endpoint.resolve_service", return_value=(_FAKE_DEFINITION, None)):
            from agentplane.domain.service.public_endpoint import verify_service_public_endpoint

            with pytest.raises(ValueError, match="does not exist in inventory"):
                verify_service_public_endpoint(
                    Path("/repo"), TARGET_PROD, SERVICE_NAME, cloudflare_env_file=_CF_ENV_FILE
                )


class TestPlanServicePublicEndpoint:
    def test_plan_returns_correct_structure(self) -> None:
        with patch(
            "agentplane.domain.service.public_endpoint.resolve_service",
            return_value=(_FAKE_DEFINITION, _DECLARED_DNS_ONLY),
        ):
            from agentplane.domain.service.public_endpoint import plan_service_public_endpoint

            result = plan_service_public_endpoint(
                Path("/repo"), TARGET_PROD, SERVICE_NAME, cloudflare_env_file=_CF_ENV_FILE
            )

        assert result["operation"] == "reconcile"
        assert result["service"]["name"] == SERVICE_NAME
        assert result["public_endpoint"]["domain"] == DOMAIN_RELAY
        assert len(result["steps"]) == 1

        step = result["steps"][0]
        inputs = step["inputs"]
        assert inputs["zone_name"] == "example.org"
        assert inputs["record_name"] == DOMAIN_RELAY
        assert inputs["record_type"] == "A"
        assert inputs["record_content"] == IP_CLOUDFLARE_RECORD
        assert inputs["proxied"] is False
        assert "ensure_cloudflare_dns_record.py" in step["display"]

    def test_plan_verify_after_apply_section(self) -> None:
        with patch(
            "agentplane.domain.service.public_endpoint.resolve_service",
            return_value=(_FAKE_DEFINITION, _DECLARED_DNS_ONLY),
        ):
            from agentplane.domain.service.public_endpoint import plan_service_public_endpoint

            result = plan_service_public_endpoint(
                Path("/repo"), TARGET_PROD, SERVICE_NAME, cloudflare_env_file=_CF_ENV_FILE
            )

        verify = result["verify_after_apply"]
        assert verify["command"] == "service public-endpoint verify"
        assert verify["args"]["target"] == TARGET_PROD
        assert verify["args"]["name"] == SERVICE_NAME

    def test_plan_no_dns_contract_raises(self) -> None:
        declared = {"public_endpoint": {"domain": DOMAIN_RELAY}}
        with patch(
            "agentplane.domain.service.public_endpoint.resolve_service", return_value=(_FAKE_DEFINITION, declared)
        ):
            from agentplane.domain.service.public_endpoint import plan_service_public_endpoint

            with pytest.raises(ValueError, match="has no public_endpoint.dns contract"):
                plan_service_public_endpoint(Path("/repo"), TARGET_PROD, SERVICE_NAME, cloudflare_env_file=_CF_ENV_FILE)

    def test_plan_non_cloudflare_provider_raises(self) -> None:
        declared = {
            "public_endpoint": {
                "domain": DOMAIN_RELAY,
                "dns": {"provider": "aws", "zone_name": "example.org", "record_type": "A", "record_content": "1.2.3.4"},
            }
        }
        with patch(
            "agentplane.domain.service.public_endpoint.resolve_service", return_value=(_FAKE_DEFINITION, declared)
        ):
            from agentplane.domain.service.public_endpoint import plan_service_public_endpoint

            with pytest.raises(ValueError, match="requires public_endpoint.dns.provider=cloudflare"):
                plan_service_public_endpoint(Path("/repo"), TARGET_PROD, SERVICE_NAME, cloudflare_env_file=_CF_ENV_FILE)


class TestApplyServicePublicEndpoint:
    def test_apply_success(self) -> None:
        fake_dns_result = {"ok": True, "action": "created", "changed": True, "record": {"id": "rec-1"}}
        mock_ensure = MagicMock(return_value=fake_dns_result)
        mock_verify = MagicMock(return_value={"ok": True, "failures": []})
        mock_plan = MagicMock(
            return_value={
                "service": {"name": SERVICE_NAME, "control_plane": "compose", "kind": "docker"},
                "public_endpoint": _DECLARED_DNS_ONLY["public_endpoint"],
                "steps": [
                    {
                        "argv": ["python", "ensure_cloudflare_dns_record.py"],
                        "display": "python ensure_cloudflare_dns_record.py",
                        "inputs": {
                            "zone_name": "example.org",
                            "record_name": DOMAIN_RELAY,
                            "record_type": "A",
                            "record_content": IP_CLOUDFLARE_RECORD,
                            "proxied": False,
                        },
                    }
                ],
            }
        )

        with (
            patch("agentplane.domain.service.public_endpoint.plan_service_public_endpoint", mock_plan),
            patch("agentplane.domain.service.public_endpoint.ensure_cloudflare_dns_record", mock_ensure),
            patch("agentplane.domain.service.public_endpoint.verify_service_public_endpoint", mock_verify),
        ):
            from agentplane.domain.service.public_endpoint import apply_service_public_endpoint

            result = apply_service_public_endpoint(
                Path("/repo"), TARGET_PROD, SERVICE_NAME, cloudflare_env_file=_CF_ENV_FILE, execute=True
            )

        assert result["ok"] is True
        assert result["operation"] == "reconcile"
        assert len(result["results"]) == 1
        assert result["results"][0]["ok"] is True
        assert result["results"][0]["parsed"] == fake_dns_result
        assert result["verified"]["ok"] is True
        mock_ensure.assert_called_once()

    def test_apply_without_execute_raises(self) -> None:
        from agentplane.domain.service.public_endpoint import apply_service_public_endpoint

        with pytest.raises(ValueError, match="requires --execute"):
            apply_service_public_endpoint(
                Path("/repo"), TARGET_PROD, SERVICE_NAME, cloudflare_env_file=_CF_ENV_FILE, execute=False
            )

    def test_apply_dns_error_stops_and_skips_verify(self) -> None:
        mock_ensure = MagicMock(side_effect=RuntimeError("Cloudflare API 500"))
        mock_verify = MagicMock()
        mock_plan = MagicMock(
            return_value={
                "service": {"name": SERVICE_NAME, "control_plane": "compose", "kind": "docker"},
                "public_endpoint": _DECLARED_DNS_ONLY["public_endpoint"],
                "steps": [
                    {
                        "argv": ["python", "ensure_cloudflare_dns_record.py"],
                        "display": "python ensure_cloudflare_dns_record.py",
                        "inputs": {
                            "zone_name": "example.org",
                            "record_name": DOMAIN_RELAY,
                            "record_type": "A",
                            "record_content": IP_CLOUDFLARE_RECORD,
                            "proxied": False,
                        },
                    }
                ],
            }
        )

        with (
            patch("agentplane.domain.service.public_endpoint.plan_service_public_endpoint", mock_plan),
            patch("agentplane.domain.service.public_endpoint.ensure_cloudflare_dns_record", mock_ensure),
            patch("agentplane.domain.service.public_endpoint.verify_service_public_endpoint", mock_verify),
        ):
            from agentplane.domain.service.public_endpoint import apply_service_public_endpoint

            result = apply_service_public_endpoint(
                Path("/repo"), TARGET_PROD, SERVICE_NAME, cloudflare_env_file=_CF_ENV_FILE, execute=True
            )

        assert result["ok"] is False
        assert result["results"][0]["ok"] is False
        assert "Cloudflare API 500" in result["results"][0]["stderr"]
        assert result["verified"]["ok"] is False
        mock_verify.assert_not_called()


class TestPrivateHelpers:
    def test_string_value_strips_whitespace(self) -> None:
        from agentplane.domain.service.public_endpoint import _string_value

        assert _string_value("  hello  ") == "hello"
        assert _string_value("") == ""
        assert _string_value(None) == ""
        assert _string_value(42) == ""

    def test_required_str_raises_on_empty(self) -> None:
        from agentplane.domain.service.public_endpoint import _required_str

        with pytest.raises(ValueError, match="requires public endpoint field zone_name"):
            _required_str("", field="zone_name", subject="svc")
        with pytest.raises(ValueError, match="requires public endpoint field domain"):
            _required_str(None, field="domain", subject="svc")

    def test_required_str_returns_stripped(self) -> None:
        from agentplane.domain.service.public_endpoint import _required_str

        assert _required_str("  example.org  ", field="zone_name", subject="svc") == "example.org"

    def test_declared_public_endpoint_raises_no_endpoint(self) -> None:
        from agentplane.domain.service.public_endpoint import _declared_public_endpoint

        with pytest.raises(ValueError, match="has no public_endpoint contract"):
            _declared_public_endpoint("svc", {"control_plane": "compose"})

    def test_declared_public_endpoint_raises_none_declared(self) -> None:
        from agentplane.domain.service.public_endpoint import _declared_public_endpoint

        with pytest.raises(ValueError, match="does not exist in inventory"):
            _declared_public_endpoint("svc", None)

    def test_declared_cloudflare_dns_raises_missing_dns(self) -> None:
        from agentplane.domain.service.public_endpoint import _declared_cloudflare_dns

        with pytest.raises(ValueError, match="has no public_endpoint.dns contract"):
            _declared_cloudflare_dns("svc", {"domain": "example.com"})

    def test_declared_cloudflare_dns_raises_wrong_provider(self) -> None:
        from agentplane.domain.service.public_endpoint import _declared_cloudflare_dns

        with pytest.raises(ValueError, match="requires public_endpoint.dns.provider=cloudflare"):
            _declared_cloudflare_dns("svc", {"dns": {"provider": "aws"}})
