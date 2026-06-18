"""Unit tests for status_html module."""

from __future__ import annotations

from pathlib import Path

import pytest
from agentplane.domain.project.status_html import (
    _card,
    _render_next_step_section,
    _render_risks_section,
    _render_roadmap_section,
    _target_rows,
    render_status_html,
    write_status_html,
)

pytestmark = pytest.mark.unit


class TestCard:
    """Tests for _card function."""

    def test_renders_card_with_title_and_value(self) -> None:
        """Test that renders card with title and value."""
        result = _card("Test Title", "Test Value")

        assert "Test Title" in result
        assert "Test Value" in result
        assert '<section class="card">' in result

    def test_escapes_html_in_title(self) -> None:
        """Test that escapes HTML in title."""
        result = _card("<script>alert('xss')</script>", "value")

        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_escapes_html_in_value(self) -> None:
        """Test that escapes HTML in value."""
        result = _card("title", "<b>bold</b>")

        assert "<b>" not in result
        assert "&lt;b&gt;" in result

    def test_includes_note(self) -> None:
        """Test that includes note."""
        result = _card("title", "value", "test note")

        assert "test note" in result


class TestTargetRows:
    """Tests for _target_rows function."""

    def test_renders_target_rows(self) -> None:
        """Test that renders target rows."""
        targets = [
            {
                "target": "wsl",
                "inventory_ok": True,
                "compose_services": 5,
                "managed_containers": 3,
                "ledger_counts": {"ingress": 2, "automations": 1},
                "updated_at": "2024-01-01",
            }
        ]

        result = _target_rows(targets)

        assert "wsl" in result
        assert "yes" in result
        assert "5" in result
        assert "3" in result
        assert "2" in result
        assert "1" in result
        assert "2024-01-01" in result

    def test_renders_no_targets_message(self) -> None:
        """Test that renders no targets message."""
        result = _target_rows([])

        assert "No targets found" in result

    def test_handles_missing_updated_at(self) -> None:
        """Test that handles missing updated_at."""
        targets = [
            {
                "target": "wsl",
                "inventory_ok": False,
                "compose_services": 0,
                "managed_containers": 0,
                "ledger_counts": {},
            }
        ]

        result = _target_rows(targets)

        assert "n/a" in result
        assert "no" in result


class TestRenderRoadmapSection:
    """Tests for _render_roadmap_section function."""

    def test_renders_error_when_not_ok(self) -> None:
        """Test that renders error when not ok."""
        roadmap = {"ok": False, "error": "Test error"}

        result = _render_roadmap_section(roadmap)

        assert "Roadmap unavailable" in result
        assert "Test error" in result

    def test_renders_all_complete_when_no_current_phase(self) -> None:
        """Test that renders all complete when no current phase."""
        roadmap = {"ok": True, "current_phase": None}

        result = _render_roadmap_section(roadmap)

        assert "All phases complete" in result

    def test_renders_current_phase(self) -> None:
        """Test that renders current phase."""
        roadmap = {
            "ok": True,
            "current_phase": {
                "id": "M5",
                "name": "Beta",
                "status": "active",
                "gate": "All tests pass",
            },
            "source": {
                "path": "docs/core/roadmap.md",
                "last_verified": "2024-01-01",
            },
        }

        result = _render_roadmap_section(roadmap)

        assert "M5" in result
        assert "Beta" in result
        assert "active" in result
        assert "All tests pass" in result

    def test_renders_next_task(self) -> None:
        """Test that renders next task."""
        roadmap = {
            "ok": True,
            "current_phase": {
                "id": "M5",
                "name": "Beta",
                "status": "active",
                "gate": "All tests pass",
            },
            "next_task": {
                "id": "M5-001",
                "title": "Test task",
                "status": "pending",
            },
            "source": {},
        }

        result = _render_roadmap_section(roadmap)

        assert "M5-001" in result
        assert "Test task" in result
        assert "pending" in result


class TestRenderRisksSection:
    """Tests for _render_risks_section function."""

    def test_renders_no_risks_message(self) -> None:
        """Test that renders no risks message."""
        result = _render_risks_section([])

        assert "No risks detected" in result

    def test_renders_risks(self) -> None:
        """Test that renders risks."""
        risks = [
            {
                "severity": "high",
                "kind": "blocked",
                "message": "Test risk",
                "source_ref": "test/ref",
            }
        ]

        result = _render_risks_section(risks)

        assert "high" in result
        assert "blocked" in result
        assert "Test risk" in result
        assert "test/ref" in result


class TestRenderNextStepSection:
    """Tests for _render_next_step_section function."""

    def test_returns_empty_for_empty_next_step(self) -> None:
        """Test that returns empty for empty next step."""
        result = _render_next_step_section({})

        assert result == ""

    def test_renders_next_step(self) -> None:
        """Test that renders next step."""
        next_step = {
            "type": "fix",
            "description": "Fix the issue",
            "target_ref": "test/ref",
        }

        result = _render_next_step_section(next_step)

        assert "fix" in result
        assert "Fix the issue" in result
        assert "test/ref" in result


class TestRenderStatusHtml:
    """Tests for render_status_html function."""

    def test_renders_status_html(self) -> None:
        """Test that renders status HTML."""
        payload = {
            "ok": True,
            "generated_at": "2024-01-01T00:00:00",
            "repo_root": "/test/repo",
            "checks": {
                "docs": {"ok": True, "errors": 0, "warnings": 0},
                "boundaries": {"ok": True, "secret_issues": 0, "privacy_issues": 0},
                "skills": {"ok": True, "count": 5, "domain_counts": {"infra": 2, "app": 3}},
            },
            "summary": {
                "repo_checks_ok": True,
                "public_skills": 5,
                "targets": 2,
                "apps": 3,
            },
            "targets": {
                "items": [
                    {
                        "target": "wsl",
                        "inventory_ok": True,
                        "compose_services": 5,
                        "managed_containers": 3,
                        "ledger_counts": {"ingress": 2, "automations": 1},
                        "updated_at": "2024-01-01",
                    }
                ],
            },
            "recommendations": ["Test recommendation"],
        }

        result = render_status_html(payload)

        assert "<!doctype html>" in result
        assert "AgentPlane Status" in result
        assert "Healthy" in result
        assert "Test recommendation" in result

    def test_renders_unhealthy_status(self) -> None:
        """Test that renders unhealthy status."""
        payload = {
            "ok": False,
            "generated_at": "2024-01-01T00:00:00",
            "repo_root": "/test/repo",
            "checks": {
                "docs": {"ok": False, "errors": 1, "warnings": 0},
                "boundaries": {"ok": True, "secret_issues": 0, "privacy_issues": 0},
                "skills": {"ok": True, "count": 5, "domain_counts": {}},
            },
            "summary": {
                "repo_checks_ok": False,
                "public_skills": 5,
                "targets": 2,
                "apps": 3,
            },
            "targets": {"items": []},
            "recommendations": [],
        }

        result = render_status_html(payload)

        assert "Needs attention" in result


class TestWriteStatusHtml:
    """Tests for write_status_html function."""

    def test_writes_html_file(self, tmp_path: Path) -> None:
        """Test that writes HTML file."""
        payload = {
            "ok": True,
            "generated_at": "2024-01-01T00:00:00",
            "repo_root": "/test/repo",
            "checks": {
                "docs": {"ok": True, "errors": 0, "warnings": 0},
                "boundaries": {"ok": True, "secret_issues": 0, "privacy_issues": 0},
                "skills": {"ok": True, "count": 5, "domain_counts": {}},
            },
            "summary": {
                "repo_checks_ok": True,
                "public_skills": 5,
                "targets": 2,
                "apps": 3,
            },
            "targets": {"items": []},
            "recommendations": [],
        }

        output = tmp_path / "status.html"
        result = write_status_html(payload, output)

        assert result == output
        assert output.exists()
        assert "<!doctype html>" in output.read_text(encoding="utf-8")

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        """Test that creates parent directories."""
        payload = {
            "ok": True,
            "generated_at": "2024-01-01T00:00:00",
            "repo_root": "/test/repo",
            "checks": {
                "docs": {"ok": True, "errors": 0, "warnings": 0},
                "boundaries": {"ok": True, "secret_issues": 0, "privacy_issues": 0},
                "skills": {"ok": True, "count": 5, "domain_counts": {}},
            },
            "summary": {
                "repo_checks_ok": True,
                "public_skills": 5,
                "targets": 2,
                "apps": 3,
            },
            "targets": {"items": []},
            "recommendations": [],
        }

        output = tmp_path / "subdir" / "status.html"
        result = write_status_html(payload, output)

        assert result == output
        assert output.exists()
