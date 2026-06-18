"""Unit tests for delivery_handlers_candidate module."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from agentplane.domain.app.delivery_handlers_candidate import _candidate_host_binding

pytestmark = pytest.mark.unit


class TestCandidateHostBinding:
    """Tests for _candidate_host_binding function."""

    def test_adds_1000_when_port_below_64535(self) -> None:
        """Test that adds 1000 when port is below 64535."""
        app_cli = MagicMock()
        app_cli._split_host_binding.return_value = ("127.0.0.1", "8080")

        result = _candidate_host_binding(app_cli, "127.0.0.1:8080")

        assert result == "127.0.0.1:9080"

    def test_subtracts_1000_when_port_above_64535_and_above_1000(self) -> None:
        """Test that subtracts 1000 when port is above 64535 and above 1000."""
        app_cli = MagicMock()
        app_cli._split_host_binding.return_value = ("0.0.0.0", "65000")

        result = _candidate_host_binding(app_cli, "0.0.0.0:65000")

        assert result == "0.0.0.0:64000"

    def test_handles_small_port(self) -> None:
        """Test that handles small port by adding 1000."""
        app_cli = MagicMock()
        app_cli._split_host_binding.return_value = ("0.0.0.0", "500")

        result = _candidate_host_binding(app_cli, "0.0.0.0:500")

        assert result == "0.0.0.0:1500"

    def test_boundary_port_64535(self) -> None:
        """Test boundary case at port 64535."""
        app_cli = MagicMock()
        app_cli._split_host_binding.return_value = ("0.0.0.0", "64535")

        result = _candidate_host_binding(app_cli, "0.0.0.0:64535")

        assert result == "0.0.0.0:65535"

    def test_boundary_port_64536(self) -> None:
        """Test boundary case at port 64536."""
        app_cli = MagicMock()
        app_cli._split_host_binding.return_value = ("0.0.0.0", "64536")

        result = _candidate_host_binding(app_cli, "0.0.0.0:64536")

        assert result == "0.0.0.0:63536"

    def test_boundary_port_1001(self) -> None:
        """Test boundary case at port 1001 (above 1000, above 64535)."""
        app_cli = MagicMock()
        app_cli._split_host_binding.return_value = ("0.0.0.0", "65000")

        result = _candidate_host_binding(app_cli, "0.0.0.0:65000")

        assert result == "0.0.0.0:64000"
