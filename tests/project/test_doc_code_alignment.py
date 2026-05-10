"""Contract tests verifying documentation claims against actual code.

These tests ensure architecture.md and other core docs don't contradict the codebase.
If a test fails, the documentation needs updating (or the code drifted).
"""

from __future__ import annotations

import unittest

import pytest
from tests.support.paths import REPO_ROOT

pytestmark = pytest.mark.integration


class TestArchitectureDocCodeAlignment(unittest.TestCase):
    """Verify architecture.md claims match the codebase."""

    def test_five_domain_directories_exist(self) -> None:
        """architecture.md claims 5 domains: infra, service, app, ingress, project."""
        domain_root = REPO_ROOT / "agentplane" / "domain"
        expected = {"infra", "service", "app", "ingress", "project"}
        actual = {p.name for p in domain_root.iterdir() if p.is_dir() and not p.name.startswith("_")}
        self.assertTrue(expected.issubset(actual), f"Missing domains: {expected - actual}")

    def test_provider_protocol_exists(self) -> None:
        """architecture.md references ProviderProtocol in agentplane/providers/protocol.py."""
        protocol_file = REPO_ROOT / "agentplane" / "providers" / "protocol.py"
        self.assertTrue(protocol_file.exists(), "ProviderProtocol file missing")

    def test_provider_protocol_method_count_within_limit(self) -> None:
        """architecture.md states ProviderProtocol has ≤15 methods."""
        from agentplane.providers.protocol import ProviderProtocol

        methods = [
            name for name in dir(ProviderProtocol)
            if not name.startswith("_") and callable(getattr(ProviderProtocol, name, None))
        ]
        self.assertLessEqual(len(methods), 15, f"ProviderProtocol has {len(methods)} methods, exceeds limit of 15")

    def test_stub_provider_exists_for_contract_testing(self) -> None:
        """architecture.md references StubProvider for protocol replaceability proof."""
        stub_file = REPO_ROOT / "agentplane" / "providers" / "stub_provider.py"
        self.assertTrue(stub_file.exists(), "StubProvider file missing")

    def test_onepanel_adapter_exists(self) -> None:
        """architecture.md references OnePanelAdapter bridging to existing gateway."""
        adapter_file = REPO_ROOT / "agentplane" / "providers" / "onepanel_adapter.py"
        self.assertTrue(adapter_file.exists(), "OnePanelAdapter file missing")

    def test_projection_lifecycle_exists(self) -> None:
        """architecture.md describes projection lifecycle (onboarding/offboarding)."""
        lifecycle_file = REPO_ROOT / "agentplane" / "domain" / "app" / "projection_lifecycle.py"
        self.assertTrue(lifecycle_file.exists(), "projection_lifecycle.py missing")

    def test_contract_tests_directory_exists(self) -> None:
        """architecture.md references contract tests in tests/contracts/."""
        contracts_dir = REPO_ROOT / "tests" / "contracts"
        self.assertTrue(contracts_dir.is_dir(), "tests/contracts/ directory missing")
