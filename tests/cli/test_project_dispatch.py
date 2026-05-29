"""Unit tests for agentplane.cli.project — dispatch and handler functions.

Covers handle_project_command dispatch, run_health_check, run_status_command,
run_docs_sanity_command, run_secret_scan, run_privacy_scan, run_skills_command,
run_topology_command, run_doc_layer_command.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agentplane.cli.project import (
    handle_project_command,
    run_docs_sanity_command,
    run_doc_layer_command,
    run_health_check,
    run_privacy_scan,
    run_secret_scan,
    run_skills_command,
    run_status_command,
    run_topology_command,
)

pytestmark = pytest.mark.unit


def _ns(**kwargs) -> argparse.Namespace:
    """Helper to create argparse.Namespace with defaults."""
    defaults = {"repo_root": Path("/tmp/test")}
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


# ---------------------------------------------------------------------------
# handle_project_command dispatch
# ---------------------------------------------------------------------------


class TestHandleProjectCommandDispatch:
    @patch("agentplane.cli.project.run_health_check", return_value={"ok": True})
    def test_dispatches_health_check(self, mock_fn) -> None:
        args = _ns(project_action="health-check")
        result = handle_project_command(args)
        assert result == {"ok": True}
        mock_fn.assert_called_once_with(args)

    @patch("agentplane.cli.project.run_status_command", return_value={"ok": True})
    def test_dispatches_status(self, mock_fn) -> None:
        args = _ns(project_action="status")
        result = handle_project_command(args)
        assert result == {"ok": True}

    @patch("agentplane.cli.project.run_docs_sanity_command", return_value={"ok": True})
    def test_dispatches_docs_sanity(self, mock_fn) -> None:
        args = _ns(project_action="docs-sanity")
        result = handle_project_command(args)
        assert result == {"ok": True}

    @patch("agentplane.cli.project.run_doc_layer_command", return_value={"ok": True})
    def test_dispatches_doc_layer(self, mock_fn) -> None:
        args = _ns(project_action="doc-layer")
        result = handle_project_command(args)
        assert result == {"ok": True}

    @patch("agentplane.cli.project.run_secret_scan", return_value={"ok": True})
    def test_dispatches_secret_scan(self, mock_fn) -> None:
        args = _ns(project_action="secret-scan")
        result = handle_project_command(args)
        assert result == {"ok": True}

    @patch("agentplane.cli.project.run_privacy_scan", return_value={"ok": True})
    def test_dispatches_privacy_scan(self, mock_fn) -> None:
        args = _ns(project_action="privacy-scan")
        result = handle_project_command(args)
        assert result == {"ok": True}

    @patch("agentplane.cli.project.run_release_check", return_value={"ok": True})
    def test_dispatches_release_check(self, mock_fn) -> None:
        args = _ns(project_action="release-check")
        result = handle_project_command(args)
        assert result == {"ok": True}

    @patch("agentplane.cli.project.run_provider_command", return_value={"ok": True})
    def test_dispatches_provider(self, mock_fn) -> None:
        args = _ns(project_action="provider")
        result = handle_project_command(args)
        assert result == {"ok": True}

    @patch("agentplane.cli.project.run_skills_command", return_value={"ok": True})
    def test_dispatches_skills(self, mock_fn) -> None:
        args = _ns(project_action="skills")
        result = handle_project_command(args)
        assert result == {"ok": True}

    @patch("agentplane.cli.project.run_topology_command", return_value={"ok": True})
    def test_dispatches_topology(self, mock_fn) -> None:
        args = _ns(project_action="topology")
        result = handle_project_command(args)
        assert result == {"ok": True}

    @patch("agentplane.cli.project._handle_projection", return_value={"ok": True})
    def test_dispatches_projection(self, mock_fn) -> None:
        args = _ns(project_action="projection")
        result = handle_project_command(args)
        assert result == {"ok": True}

    def test_unsupported_action_raises(self) -> None:
        args = _ns(project_action="nonexistent")
        with pytest.raises(ValueError, match="unsupported project action"):
            handle_project_command(args)


# ---------------------------------------------------------------------------
# run_health_check
# ---------------------------------------------------------------------------


class TestRunHealthCheck:
    def test_all_skips(self, tmp_path: Path) -> None:
        args = _ns(
            repo_root=tmp_path,
            skip_ruff=True,
            skip_tests=True,
            skip_cli_help=True,
            skip_secrets=True,
            skip_docs=True,
            onepanel_source_root=None,
            onepanel_baseline=None,
            fail_on_onepanel_drift=False,
        )
        with patch("agentplane.cli.project._skills_check", return_value={"name": "skills-check", "ok": True}):
            result = run_health_check(args)
        assert result["command"] == "project"
        assert result["action"] == "health-check"
        assert result["ok"] is True

    def test_ruff_check_included(self, tmp_path: Path) -> None:
        args = _ns(
            repo_root=tmp_path,
            skip_ruff=False,
            skip_tests=True,
            skip_cli_help=True,
            skip_secrets=True,
            skip_docs=True,
            onepanel_source_root=None,
            onepanel_baseline=None,
            fail_on_onepanel_drift=False,
        )
        with patch("agentplane.cli.project._run_check", return_value={"name": "ruff", "ok": True}), \
             patch("agentplane.cli.project._skills_check", return_value={"name": "skills-check", "ok": True}):
            result = run_health_check(args)
        assert any(c["name"] == "ruff" for c in result["checks"])

    def test_baseline_without_source_root_raises(self, tmp_path: Path) -> None:
        baseline = tmp_path / "baseline.json"
        args = _ns(
            repo_root=tmp_path,
            skip_ruff=True,
            skip_tests=True,
            skip_cli_help=True,
            skip_secrets=True,
            skip_docs=True,
            onepanel_source_root=None,
            onepanel_baseline=baseline,
        )
        with pytest.raises(ValueError, match="--onepanel-baseline requires --onepanel-source-root"):
            run_health_check(args)


# ---------------------------------------------------------------------------
# run_status_command
# ---------------------------------------------------------------------------


class TestRunStatusCommand:
    @patch("agentplane.cli.project.build_repo_status", return_value={"ok": True})
    def test_basic_status(self, mock_status) -> None:
        args = _ns(html=None)
        result = run_status_command(args)
        assert result["ok"] is True
        assert result["dashboard"]["html"] is None

    @patch("agentplane.cli.project.write_status_html")
    @patch("agentplane.cli.project.build_repo_status", return_value={"ok": True})
    def test_with_html_output(self, mock_status, mock_write, tmp_path: Path) -> None:
        html_path = tmp_path / "out.html"
        args = _ns(html=html_path)
        result = run_status_command(args)
        mock_write.assert_called_once()
        assert str(html_path.resolve()) in result["dashboard"]["html"]


# ---------------------------------------------------------------------------
# run_docs_sanity_command
# ---------------------------------------------------------------------------


class TestRunDocsSanityCommand:
    @patch("agentplane.cli.project.run_docs_sanity", return_value=[])
    def test_no_issues(self, mock_fn) -> None:
        result = run_docs_sanity_command(_ns())
        assert result["ok"] is True
        assert result["errors_count"] == 0

    @patch("agentplane.cli.project.run_docs_sanity")
    def test_with_errors(self, mock_fn) -> None:
        issue = MagicMock()
        issue.severity = "error"
        issue.to_dict.return_value = {"severity": "error", "message": "bad"}
        mock_fn.return_value = [issue]
        result = run_docs_sanity_command(_ns())
        assert result["ok"] is False
        assert result["errors_count"] == 1


# ---------------------------------------------------------------------------
# run_doc_layer_command
# ---------------------------------------------------------------------------


class TestRunDocLayerCommand:
    @patch("agentplane.cli.project.run_doc_layer_check", return_value=[])
    def test_no_issues(self, mock_fn) -> None:
        result = run_doc_layer_command(_ns())
        assert result["ok"] is True
        assert result["action"] == "doc-layer"


# ---------------------------------------------------------------------------
# run_secret_scan
# ---------------------------------------------------------------------------


class TestRunSecretScan:
    @patch("agentplane.cli.project.scan_repository_for_secrets", return_value=[])
    def test_no_secrets(self, mock_fn) -> None:
        result = run_secret_scan(_ns(allowlist=None))
        assert result["ok"] is True
        assert result["action"] == "secret-scan"

    @patch("agentplane.cli.project.scan_repository_for_secrets")
    def test_with_issues(self, mock_fn) -> None:
        issue = MagicMock()
        issue.to_dict.return_value = {"file": "test", "line": 1}
        mock_fn.return_value = [issue]
        result = run_secret_scan(_ns(allowlist=None))
        assert result["ok"] is False
        assert len(result["issues"]) == 1


# ---------------------------------------------------------------------------
# run_privacy_scan
# ---------------------------------------------------------------------------


class TestRunPrivacyScan:
    @patch("agentplane.cli.project.scan_repository_for_private_material", return_value=[])
    def test_no_issues(self, mock_fn) -> None:
        result = run_privacy_scan(_ns())
        assert result["ok"] is True
        assert result["action"] == "privacy-scan"


# ---------------------------------------------------------------------------
# run_skills_command
# ---------------------------------------------------------------------------


class TestRunSkillsCommand:
    @patch("agentplane.cli.project.check_skill_surface", return_value=[])
    def test_skills_check_ok(self, mock_fn) -> None:
        args = _ns(project_skills_action="check")
        result = run_skills_command(args)
        assert result["ok"] is True
        assert result["action"] == "skills.check"

    @patch("agentplane.cli.project.check_skill_surface")
    def test_skills_check_with_issues(self, mock_fn) -> None:
        issue = MagicMock()
        issue.to_dict.return_value = {"severity": "error"}
        mock_fn.return_value = [issue]
        args = _ns(project_skills_action="check")
        result = run_skills_command(args)
        assert result["ok"] is False

    @patch("agentplane.cli.project.list_skill_entries", return_value=[])
    def test_skills_list(self, mock_fn) -> None:
        args = _ns(project_skills_action="list")
        result = run_skills_command(args)
        assert result["ok"] is True
        assert result["action"] == "skills.list"

    @patch("agentplane.cli.project.write_skill_export")
    @patch("agentplane.cli.project.export_skill_surface", return_value={"skills": []})
    def test_skills_export(self, mock_export, mock_write) -> None:
        args = _ns(project_skills_action="export", output=None)
        result = run_skills_command(args)
        assert result["ok"] is True
        assert result["action"] == "skills.export"

    @patch("agentplane.cli.project.write_skill_export")
    @patch("agentplane.cli.project.export_skill_surface", return_value={"skills": []})
    def test_skills_export_with_output(self, mock_export, mock_write, tmp_path: Path) -> None:
        out = tmp_path / "skills.json"
        args = _ns(project_skills_action="export", output=out)
        result = run_skills_command(args)
        mock_write.assert_called_once()
        assert result["output"] is not None

    @patch("agentplane.cli.project.skill_sync_report", return_value={"ok": True})
    def test_skills_sync(self, mock_fn) -> None:
        args = _ns(project_skills_action="sync")
        result = run_skills_command(args)
        assert result["ok"] is True
        assert result["action"] == "skills.sync"

    def test_unsupported_skills_action_raises(self) -> None:
        args = _ns(project_skills_action="nonexistent")
        with pytest.raises(ValueError, match="unsupported project skills action"):
            run_skills_command(args)


# ---------------------------------------------------------------------------
# run_topology_command
# ---------------------------------------------------------------------------


class TestRunTopologyCommand:
    @patch("agentplane.cli.project.build_topology")
    def test_json_mode(self, mock_topo) -> None:
        mock_topo.return_value = {"targets": []}
        args = _ns(json_output=True)
        result = run_topology_command(args)
        assert result == {"targets": []}

    @patch("agentplane.cli.project.build_topology")
    def test_human_readable_no_targets(self, mock_topo, capsys) -> None:
        mock_topo.return_value = {"targets": []}
        args = _ns(json_output=False)
        result = run_topology_command(args)
        assert "No targets" in capsys.readouterr().out

    @patch("agentplane.cli.project.build_topology")
    def test_human_readable_with_targets(self, mock_topo, capsys) -> None:
        mock_topo.return_value = {
            "targets": [{
                "target": "wsl",
                "hostname": "wsl-host",
                "ip": None,
                "status": "ok",
                "apps": [{"app": "myapp", "control_plane": "docker", "dependencies": []}],
                "services": [{"name": "postgres", "kind": "docker"}],
            }]
        }
        args = _ns(json_output=False)
        result = run_topology_command(args)
        output = capsys.readouterr().out
        assert "wsl" in output
        assert "myapp" in output
        assert "postgres" in output
