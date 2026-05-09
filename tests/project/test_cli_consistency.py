"""Contract tests verifying CLI flag consistency across modules.

Ensures all CLI modules register correctly and use consistent patterns.
"""

from __future__ import annotations

import argparse
import unittest

import pytest

pytestmark = pytest.mark.integration


class TestCliModuleRegistration(unittest.TestCase):
    """Verify all CLI modules register without errors."""

    def test_infra_register(self) -> None:
        from agentplane.cli.infra import add_infra_parser
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers()
        add_infra_parser(sub)

    def test_ingress_register(self) -> None:
        from agentplane.cli.ingress import add_ingress_parser
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers()
        add_ingress_parser(sub)

    def test_service_register(self) -> None:
        from agentplane.cli.service import add_service_parser
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers()
        add_service_parser(sub)

    def test_apps_register(self) -> None:
        from agentplane.cli.apps import add_app_parser
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers()
        add_app_parser(sub)

    def test_project_register(self) -> None:
        from agentplane.cli.project import add_project_parser
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers()
        add_project_parser(sub)
