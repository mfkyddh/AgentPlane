"""Tests for the site-migration-ops skill workflow.

Covers the full site migration lifecycle:
- Parallel validation (old entry stays online while new path is verified)
- Ingress reconcile (plan / apply)
- Domain cutover verification
- Ledger refresh after migration
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from agentplane.domain.ingress.lifecycle import (
    apply_ingress_truth_offboard,
    apply_ingress_truth_onboard,
    plan_ingress_truth_offboard,
    plan_ingress_truth_onboard,
)
from agentplane.domain.ingress.models import IngressDefinition

pytestmark = [pytest.mark.unit]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TARGET = "prod0-main"


def _inventory_file(tmp_path: Path, target: str) -> Path:
    return tmp_path / "inventory" / "servers" / target / "inventory.json"


def _write_inventory(tmp_path: Path, target: str, payload: dict) -> Path:
    inventory_file = _inventory_file(tmp_path, target)
    inventory_file.parent.mkdir(parents=True, exist_ok=True)
    inventory_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return inventory_file


def _migration_definition() -> IngressDefinition:
    """A representative definition for a site being migrated."""
    return IngressDefinition(
        alias="migrated-app",
        primary_domain="migrated.example.com",
        public_url="https://migrated.example.com",
        proxy="http://127.0.0.1:9090",
        status="Running",
        config_file="/data/1panel/www/conf.d/migrated-app.conf",
        ssl_id=42,
    )


def _old_definition() -> IngressDefinition:
    """The existing entry before migration (different proxy / ssl)."""
    return IngressDefinition(
        alias="migrated-app",
        primary_domain="migrated.example.com",
        public_url="https://migrated.example.com",
        proxy="http://127.0.0.1:8080",
        status="Running",
        config_file="/data/1panel/www/conf.d/migrated-app.conf",
        ssl_id=10,
    )


def _entry_from(definition: IngressDefinition) -> dict:
    return {
        "alias": definition.alias,
        "primary_domain": definition.primary_domain,
        "public_url": definition.public_url,
        "proxy": definition.proxy,
        "status": definition.status,
        "config_file": definition.config_file,
        "ssl_id": definition.ssl_id,
    }




class FakeWebsiteExecutor:
    """Minimal stub for 1Panel website API calls."""

    def __init__(self, *, existing: dict | None, https: dict | None = None) -> None:
        self.requests: list[tuple[str, str, dict | None]] = []
        self._existing = existing
        self._https = https or {}
        self._created = False

    def api_request(self, method: str, path: str, body: dict | None = None) -> object:
        self.requests.append((method, path, body))
        if path == "/api/v2/websites/search":
            if self._existing is None and not self._created:
                return {"items": []}
            website_id = 9 if self._existing is None else int(self._existing["id"])
            alias = "migrated-app" if self._existing is None else str(self._existing["alias"])
            primary_domain = "migrated.example.com" if self._existing is None else str(self._existing["primaryDomain"])
            proxy = "http://127.0.0.1:9090" if self._existing is None else str(self._existing["proxy"])
            return {
                "items": [
                    {
                        "id": website_id,
                        "alias": alias,
                        "primaryDomain": primary_domain,
                        "status": "Running",
                        "proxy": proxy,
                    }
                ]
            }
        if path == "/api/v2/websites/7":
            if self._existing is None:
                raise AssertionError("Unexpected detail request when website is missing")
            return dict(self._existing)
        if path == "/api/v2/websites/7/https":
            if self._existing is None:
                raise AssertionError("Unexpected https request when website is missing")
            return dict(self._https)
        if path == "/api/v2/websites/9":
            return {
                "id": 9,
                "alias": "migrated-app",
                "primaryDomain": "migrated.example.com",
                "proxy": "http://127.0.0.1:9090",
                "status": "Running",
            }
        if path == "/api/v2/websites/9/https":
            return {"enable": True, "httpsPort": "443", "SSL": {"id": 42}}
        if path == "/api/v2/websites":
            self._created = True
            return {"id": 9}
        raise AssertionError(f"Unexpected request: {method} {path} {body}")


# ---------------------------------------------------------------------------
# Parallel validation: old entry stays online until new path is verified
# ---------------------------------------------------------------------------


class TestParallelValidation(unittest.TestCase):
    """The old public entry must remain untouched until the new ingress passes verification."""

    def test_onboard_does_not_touch_existing_entries(self) -> None:
        """Adding a new alias must not mutate other aliases in the same inventory."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            other_entry = {
                "alias": "other-site",
                "primary_domain": "other.example.com",
                "public_url": "https://other.example.com",
                "proxy": "http://127.0.0.1:3000",
                "status": "Running",
            }
            _write_inventory(root, TARGET, {"services": {"public_ingresses": [other_entry]}})

            definition = _migration_definition()
            apply_ingress_truth_onboard(root, TARGET, definition, execute=True)

            payload = json.loads(_inventory_file(root, TARGET).read_text(encoding="utf-8"))
            ingresses = payload["services"]["public_ingresses"]
            self.assertEqual(len(ingresses), 2)
            self.assertEqual(ingresses[0]["alias"], "other-site")
            self.assertEqual(ingresses[0]["proxy"], "http://127.0.0.1:3000")
            self.assertEqual(ingresses[1]["alias"], "migrated-app")

    def test_offboard_only_removes_target_alias(self) -> None:
        """Removing the migrated alias leaves other aliases intact."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            other_entry = {
                "alias": "keep-me",
                "primary_domain": "keep.example.com",
                "public_url": "https://keep.example.com",
                "proxy": "http://127.0.0.1:4000",
                "status": "Running",
            }
            _write_inventory(
                root, TARGET, {"services": {"public_ingresses": [other_entry, _entry_from(_migration_definition())]}}
            )

            apply_ingress_truth_offboard(root, TARGET, "migrated-app", execute=True)

            payload = json.loads(_inventory_file(root, TARGET).read_text(encoding="utf-8"))
            ingresses = payload["services"]["public_ingresses"]
            self.assertEqual(len(ingresses), 1)
            self.assertEqual(ingresses[0]["alias"], "keep-me")



# ---------------------------------------------------------------------------
# Ingress reconcile: plan and apply
# ---------------------------------------------------------------------------


class TestIngressReconcile(unittest.TestCase):
    """Reconcile creates the 1Panel website when it is missing."""

    def test_plan_reconcile_missing_site_returns_create_step(self) -> None:
        from agentplane.domain.ingress.handlers import plan_ingress_operation

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_inventory(root, TARGET, {"services": {"public_ingresses": [_entry_from(_migration_definition())]}})
            executor = FakeWebsiteExecutor(existing=None)

            with patch("agentplane.domain.ingress.handlers._executor_for_target", return_value=executor):
                payload = plan_ingress_operation(root, TARGET, "migrated-app", "reconcile")

            self.assertEqual(payload["operation"], "reconcile")
            self.assertEqual(payload["drift"]["status"], "missing")
            self.assertEqual(len(payload["steps"]), 1)
            self.assertEqual(payload["steps"][0]["kind"], "create")
            self.assertEqual(payload["steps"][0]["body"]["website_alias"], "migrated-app")

    def test_apply_reconcile_creates_site_and_post_verifies(self) -> None:
        from agentplane.cli.ingress import handle_ingress_command

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_inventory(root, TARGET, {"services": {"public_ingresses": [_entry_from(_migration_definition())]}})
            executor = FakeWebsiteExecutor(existing=None)

            args = SimpleNamespace(
                ingress_action="apply",
                target=TARGET,
                alias="migrated-app",
                operation="reconcile",
                repo_root=str(root),
                execute=True,
                write=False,
            )

            with patch("agentplane.domain.ingress.handlers._executor_for_target", return_value=executor):
                payload = handle_ingress_command(args)

            self.assertEqual(payload["command"], "ingress")
            self.assertEqual(payload["action"], "apply")
            self.assertTrue(payload["payload"]["ok"])
            self.assertEqual(payload["payload"]["result"]["action"], "created")
            self.assertTrue(payload["payload"]["verified"]["ok"])

    def test_plan_reconcile_matched_site_returns_noop(self) -> None:
        from agentplane.domain.ingress.handlers import plan_ingress_operation

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_inventory(root, TARGET, {"services": {"public_ingresses": [_entry_from(_migration_definition())]}})
            executor = FakeWebsiteExecutor(
                existing={
                    "id": 7,
                    "alias": "migrated-app",
                    "primaryDomain": "migrated.example.com",
                    "proxy": "http://127.0.0.1:9090",
                    "status": "Running",
                },
                https={"enable": True, "httpsPort": "443", "SSL": {"id": 42}},
            )

            with patch("agentplane.domain.ingress.handlers._executor_for_target", return_value=executor):
                payload = plan_ingress_operation(root, TARGET, "migrated-app", "reconcile")

            self.assertEqual(payload["drift"]["status"], "matched")
            self.assertEqual(len(payload["steps"]), 0)

    def test_apply_reconcile_without_execute_raises(self) -> None:
        from agentplane.domain.ingress.handlers import apply_ingress_operation

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_inventory(root, TARGET, {"services": {"public_ingresses": [_entry_from(_migration_definition())]}})

            with self.assertRaises(ValueError) as ctx:
                apply_ingress_operation(root, TARGET, "migrated-app", "reconcile", execute=False)
            self.assertIn("--execute", str(ctx.exception))



# ---------------------------------------------------------------------------
# Domain cutover verification
# ---------------------------------------------------------------------------


class TestDomainCutoverVerification(unittest.TestCase):
    """Verify that the live ingress matches the declared definition after cutover."""

    def test_verify_passes_when_live_matches_declared(self) -> None:
        from agentplane.domain.ingress.handlers import verify_ingress

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_inventory(root, TARGET, {"services": {"public_ingresses": [_entry_from(_migration_definition())]}})
            executor = FakeWebsiteExecutor(
                existing={
                    "id": 7,
                    "alias": "migrated-app",
                    "primaryDomain": "migrated.example.com",
                    "proxy": "http://127.0.0.1:9090",
                    "status": "Running",
                },
                https={"enable": True, "httpsPort": "443", "SSL": {"id": 42}},
            )

            with patch("agentplane.domain.ingress.handlers._executor_for_target", return_value=executor):
                payload = verify_ingress(root, TARGET, "migrated-app")

            self.assertTrue(payload["ok"])
            self.assertEqual(len(payload["failures"]), 0)
            self.assertTrue(payload["checks"]["alias"]["ok"])
            self.assertTrue(payload["checks"]["proxy"]["ok"])
            self.assertTrue(payload["checks"]["https"]["ok"])
            self.assertTrue(payload["checks"]["ssl_id"]["ok"])

    def test_verify_fails_when_proxy_drifts(self) -> None:
        from agentplane.domain.ingress.handlers import verify_ingress

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_inventory(root, TARGET, {"services": {"public_ingresses": [_entry_from(_migration_definition())]}})
            executor = FakeWebsiteExecutor(
                existing={
                    "id": 7,
                    "alias": "migrated-app",
                    "primaryDomain": "migrated.example.com",
                    "proxy": "http://127.0.0.1:8080",
                    "status": "Running",
                },
                https={"enable": True, "httpsPort": "443", "SSL": {"id": 42}},
            )

            with patch("agentplane.domain.ingress.handlers._executor_for_target", return_value=executor):
                payload = verify_ingress(root, TARGET, "migrated-app")

            self.assertFalse(payload["ok"])
            self.assertIn("proxy", payload["failures"])
            self.assertFalse(payload["checks"]["proxy"]["ok"])
            self.assertEqual(payload["checks"]["proxy"]["actual"], "http://127.0.0.1:8080")
            self.assertEqual(payload["checks"]["proxy"]["expected"], "http://127.0.0.1:9090")

    def test_verify_fails_when_site_missing(self) -> None:
        from agentplane.domain.ingress.handlers import verify_ingress

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_inventory(root, TARGET, {"services": {"public_ingresses": [_entry_from(_migration_definition())]}})
            executor = FakeWebsiteExecutor(existing=None)

            with patch("agentplane.domain.ingress.handlers._executor_for_target", return_value=executor):
                payload = verify_ingress(root, TARGET, "migrated-app")

            self.assertFalse(payload["ok"])
            self.assertIn("missing", payload["failures"])
            self.assertFalse(payload["checks"]["exists"]["ok"])

    def test_verify_fails_when_https_disabled(self) -> None:
        from agentplane.domain.ingress.handlers import verify_ingress

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_inventory(root, TARGET, {"services": {"public_ingresses": [_entry_from(_migration_definition())]}})
            executor = FakeWebsiteExecutor(
                existing={
                    "id": 7,
                    "alias": "migrated-app",
                    "primaryDomain": "migrated.example.com",
                    "proxy": "http://127.0.0.1:9090",
                    "status": "Running",
                },
                https={"enable": False, "httpsPort": "", "SSL": {"id": 99}},
            )

            with patch("agentplane.domain.ingress.handlers._executor_for_target", return_value=executor):
                payload = verify_ingress(root, TARGET, "migrated-app")

            self.assertFalse(payload["ok"])
            self.assertIn("https", payload["failures"])
            self.assertIn("ssl_id", payload["failures"])
