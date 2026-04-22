import json
from pathlib import Path

from agentplane.domain.website.lifecycle import (
    apply_website_truth_offboard,
    apply_website_truth_onboard,
    plan_website_truth_offboard,
    plan_website_truth_onboard,
)
from agentplane.domain.website.models import WebsiteDefinition

TARGET = "wsl"


def _inventory_file(tmp_path: Path, target: str) -> Path:
    inventory_dir = tmp_path / "inventory" / "servers" / target
    inventory_dir.mkdir(parents=True, exist_ok=True)
    return inventory_dir / "inventory.json"


def _write_inventory(tmp_path: Path, target: str, payload: dict) -> Path:
    inventory_file = _inventory_file(tmp_path, target)
    inventory_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return inventory_file


def _definition() -> WebsiteDefinition:
    return WebsiteDefinition(
        alias="lane5",
        primary_domain="lane5.example.com",
        public_url="https://lane5.example.com",
        proxy="http://127.0.0.1:8080",
        status="Running",
        config_file="/data/lane5/www/conf.d/lane5.conf",
        ssl_id=77,
    )


def _entry_from(definition: WebsiteDefinition) -> dict:
    return {
        "alias": definition.alias,
        "primary_domain": definition.primary_domain,
        "public_url": definition.public_url,
        "proxy": definition.proxy,
        "status": definition.status,
        "config_file": definition.config_file,
        "ssl_id": definition.ssl_id,
    }


def test_plan_onboard_missing_appends_row(tmp_path: Path) -> None:
    definition = _definition()
    _write_inventory(tmp_path, TARGET, {"services": {"public_websites": []}})
    plan = plan_website_truth_onboard(tmp_path, TARGET, definition)
    assert plan["drift"]["status"] == "missing"
    assert len(plan["steps"]) == 1
    assert plan["steps"][0]["kind"] == "append"


def test_apply_onboard_creates_entry_and_verifies(tmp_path: Path) -> None:
    definition = _definition()
    inventory_file = _write_inventory(tmp_path, TARGET, {"services": {"public_websites": []}})
    result = apply_website_truth_onboard(tmp_path, TARGET, definition, execute=True)
    assert result["result"]["action"] == "created"
    assert result["plan"]["drift"]["status"] == "missing"
    assert result["verified"]["drift"]["status"] == "matched"
    assert result["follow_through"]["source_surface"] == "website.truth.onboard"
    payload = json.loads(inventory_file.read_text(encoding="utf-8"))
    websites = payload["services"]["public_websites"]
    assert websites[0]["alias"] == definition.alias


def test_plan_onboard_mismatch_triggers_replace(tmp_path: Path) -> None:
    definition = _definition()
    entry = _entry_from(definition)
    entry["public_url"] = "https://old.example.com"
    _write_inventory(tmp_path, TARGET, {"services": {"public_websites": [entry]}})
    plan = plan_website_truth_onboard(tmp_path, TARGET, definition)
    assert plan["drift"]["status"] == "drift"
    assert plan["steps"][0]["kind"] == "replace"
    result = apply_website_truth_onboard(tmp_path, TARGET, definition, execute=True)
    assert result["result"]["action"] == "updated"
    payload = json.loads(_inventory_file(tmp_path, TARGET).read_text(encoding="utf-8"))
    assert payload["services"]["public_websites"][0]["public_url"] == definition.public_url


def test_remove_and_offboard(tmp_path: Path) -> None:
    definition = _definition()
    _write_inventory(tmp_path, TARGET, {"services": {"public_websites": [_entry_from(definition)]}})
    plan = plan_website_truth_offboard(tmp_path, TARGET, definition.alias)
    assert plan["drift"]["status"] == "drift"
    assert plan["steps"][0]["kind"] == "remove"
    result = apply_website_truth_offboard(tmp_path, TARGET, definition.alias, execute=True)
    assert result["result"]["action"] == "removed"
    inventory_file = _inventory_file(tmp_path, TARGET)
    payload = json.loads(inventory_file.read_text(encoding="utf-8"))
    assert payload["services"]["public_websites"] == []
    assert result["verified"]["drift"]["status"] == "matched"
    assert result["follow_through"]["source_surface"] == "website.truth.offboard"

