from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from agentplane.domain.app.contracts import APP_DELIVERY_CONTRACT_SCHEMA_V2
from tests.support.paths import REPO_ROOT

pytestmark = pytest.mark.e2e


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return names


def test_app_cli_is_parser_and_dispatch_only() -> None:
    cli_apps = REPO_ROOT / "agentplane" / "cli" / "apps.py"
    text = cli_apps.read_text(encoding="utf-8")

    assert "subprocess.run" not in text
    for name in (
        "validate_contract",
        "render_runtime",
        "inventory_refresh",
        "doc_sync",
        "build_artifact",
        "package_runtime",
        "ship_image",
        "deploy_app",
        "verify_app",
        "rollback_app",
    ):
        assert f"def {name}(" not in text


def test_app_domain_does_not_import_cli_or_onepanel_scripts() -> None:
    for path in (REPO_ROOT / "agentplane" / "domain" / "app").glob("*.py"):
        imports = _imports(path)
        assert not any(name == "agentplane.cli" or name.startswith("agentplane.cli.") for name in imports), path
        assert not any(
            name == "agentplane.scripts.onepanel" or name.startswith("agentplane.scripts.onepanel.") for name in imports
        ), path


def test_public_cli_and_domain_surfaces_do_not_import_onepanel_scripts() -> None:
    checked_roots = (
        REPO_ROOT / "agentplane" / "cli",
        REPO_ROOT / "agentplane" / "domain",
    )
    for root in checked_roots:
        for path in root.rglob("*.py"):
            imports = _imports(path)
            assert not any(
                name == "agentplane.scripts.onepanel" or name.startswith("agentplane.scripts.onepanel.")
                for name in imports
            ), path


def test_onepanel_script_imports_are_provider_internal() -> None:
    provider_files = {
        "gateway.py",
        "onepanel_fixtures.py",
        "onepanel_ingress.py",
        "onepanel_ledgers.py",
        "onepanel_objects.py",
        "onepanel_transition.py",
    }
    for path in (REPO_ROOT / "agentplane" / "providers").glob("*.py"):
        imports = _imports(path)
        imports_scripts = any(
            name == "agentplane.scripts.onepanel" or name.startswith("agentplane.scripts.onepanel.") for name in imports
        )
        if path.name in provider_files:
            continue
        assert not imports_scripts, path


def test_legacy_app_runtime_provider_adapter_is_removed() -> None:
    assert not (REPO_ROOT / "agentplane" / "providers" / "app_runtime.py").exists()


def test_app_delivery_contract_v2_schema_is_public_and_machine_readable() -> None:
    schema_path = REPO_ROOT / APP_DELIVERY_CONTRACT_SCHEMA_V2
    payload = json.loads(schema_path.read_text(encoding="utf-8"))

    assert payload["title"] == "AgentPlane App Delivery Contract v2"
    assert payload["properties"]["schema_version"]["const"] == 2
    assert payload["properties"]["packaging"]["properties"]["image_tag_rule"]["const"]
    assert "runtime" in payload["required"]
