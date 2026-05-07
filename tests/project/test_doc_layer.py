from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
from agentplane.domain.project.doc_layer import _expected_layer, _extract_layer, run_doc_layer_check


class TestExpectedLayer:
    def test_strategy_dir(self) -> None:
        assert _expected_layer("strategy/vision.md") == "strategy"

    def test_strategy_subdir(self) -> None:
        assert _expected_layer("strategy/decisions/001.md") == "strategy"

    def test_project_dir(self) -> None:
        assert _expected_layer("project/charter.md") == "project"

    def test_reference_dir(self) -> None:
        assert _expected_layer("reference/code-style.md") == "engineering"

    def test_architecture_dir(self) -> None:
        assert _expected_layer("architecture/control-plane.md") == "technical"

    def test_runbooks_dir(self) -> None:
        assert _expected_layer("runbooks/wsl-secrets-backup.md") == "technical"

    def test_archive_exempt(self) -> None:
        assert _expected_layer("archive/runbooks/old.md") is None

    def test_history_exempt(self) -> None:
        assert _expected_layer("history/index.md") is None

    def test_getting_started_exempt(self) -> None:
        assert _expected_layer("getting-started/getting-started.md") is None

    def test_tutorials_exempt(self) -> None:
        assert _expected_layer("tutorials/deploy-first-app.md") is None

    def test_maintainers_exempt(self) -> None:
        assert _expected_layer("maintainers/authoring.md") is None

    def test_root_readme_exempt(self) -> None:
        assert _expected_layer("README.md") is None


class TestExtractLayer:
    def test_valid_layer(self) -> None:
        text = textwrap.dedent("""\
            ---
            status: active
            layer: strategy
            ---
            # Title
        """)
        assert _extract_layer(text) == "strategy"

    def test_no_layer_field(self) -> None:
        text = textwrap.dedent("""\
            ---
            status: active
            ---
            # Title
        """)
        assert _extract_layer(text) is None

    def test_no_frontmatter(self) -> None:
        assert _extract_layer("# Title\n") is None


@pytest.mark.unit
class TestRunDocLayerCheck:
    def test_correct_layer_passes(self, tmp_path: Path) -> None:
        docs = tmp_path / "docs" / "strategy"
        docs.mkdir(parents=True)
        (docs / "vision.md").write_text(
            textwrap.dedent("""\
            ---
            status: active
            layer: strategy
            ---
            # Vision
        """),
            encoding="utf-8",
        )
        issues = run_doc_layer_check(tmp_path)
        assert issues == []

    def test_missing_layer_field_is_error(self, tmp_path: Path) -> None:
        docs = tmp_path / "docs" / "reference"
        docs.mkdir(parents=True)
        (docs / "code-style.md").write_text(
            textwrap.dedent("""\
            ---
            status: active
            ---
            # Code Style
        """),
            encoding="utf-8",
        )
        issues = run_doc_layer_check(tmp_path)
        assert len(issues) == 1
        assert issues[0].kind == "missing-layer-field"
        assert issues[0].severity == "error"

    def test_layer_mismatch_is_warning(self, tmp_path: Path) -> None:
        docs = tmp_path / "docs" / "reference"
        docs.mkdir(parents=True)
        (docs / "weird.md").write_text(
            textwrap.dedent("""\
            ---
            status: active
            layer: strategy
            ---
            # Weird
        """),
            encoding="utf-8",
        )
        issues = run_doc_layer_check(tmp_path)
        assert len(issues) == 1
        assert issues[0].kind == "layer-mismatch"
        assert issues[0].severity == "warning"

    def test_invalid_layer_value_is_error(self, tmp_path: Path) -> None:
        docs = tmp_path / "docs" / "strategy"
        docs.mkdir(parents=True)
        (docs / "bad.md").write_text(
            textwrap.dedent("""\
            ---
            status: active
            layer: unknown
            ---
            # Bad
        """),
            encoding="utf-8",
        )
        issues = run_doc_layer_check(tmp_path)
        assert len(issues) == 1
        assert issues[0].kind == "invalid-layer-value"

    def test_exempt_dirs_skipped(self, tmp_path: Path) -> None:
        docs = tmp_path / "docs" / "archive"
        docs.mkdir(parents=True)
        (docs / "old.md").write_text("# Old\n", encoding="utf-8")
        issues = run_doc_layer_check(tmp_path)
        assert issues == []

    def test_no_docs_dir(self, tmp_path: Path) -> None:
        issues = run_doc_layer_check(tmp_path)
        assert issues == []

    def test_technical_layer_in_runbooks(self, tmp_path: Path) -> None:
        docs = tmp_path / "docs" / "runbooks"
        docs.mkdir(parents=True)
        (docs / "ops.md").write_text(
            textwrap.dedent("""\
            ---
            status: active
            layer: technical
            ---
            # Ops
        """),
            encoding="utf-8",
        )
        issues = run_doc_layer_check(tmp_path)
        assert issues == []

    def test_technical_layer_in_architecture(self, tmp_path: Path) -> None:
        docs = tmp_path / "docs" / "architecture"
        docs.mkdir(parents=True)
        (docs / "core.md").write_text(
            textwrap.dedent("""\
            ---
            status: active
            layer: technical
            ---
            # Core
        """),
            encoding="utf-8",
        )
        issues = run_doc_layer_check(tmp_path)
        assert issues == []
