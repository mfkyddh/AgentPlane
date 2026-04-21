import json
import tempfile
import unittest
from pathlib import Path

from agentplane.cli import host_automation


class FakeExecutor:
    def __init__(self, cronjobs: list[dict[str, object]] | None = None) -> None:
        self.cronjobs = [dict(item) for item in (cronjobs or [])]
        self.calls: list[tuple[str, str, dict[str, object] | None]] = []
        self.handled_ids: list[int] = []

    def api_request(self, method: str, path: str, body: dict[str, object] | None = None) -> object:
        self.calls.append((method, path, body))
        if path == "/api/v2/cronjobs/search":
            assert body is not None
            info = str(body.get("info", ""))
            items = [item for item in self.cronjobs if not info or info in str(item.get("name", ""))]
            return {"items": items}
        if path == "/api/v2/cronjobs/load/info":
            assert body is not None
            cronjob_id = int(body["id"])
            for item in self.cronjobs:
                if int(item["id"]) == cronjob_id:
                    return dict(item)
            raise RuntimeError("cronjob not found")
        if path == "/api/v2/cronjobs":
            assert body is not None
            created = dict(body)
            created["id"] = max((int(item["id"]) for item in self.cronjobs), default=0) + 1
            created.setdefault("status", "Enable")
            self.cronjobs.append(created)
            return {"id": created["id"]}
        if path == "/api/v2/cronjobs/update":
            assert body is not None
            cronjob_id = int(body["id"])
            for item in self.cronjobs:
                if int(item["id"]) == cronjob_id:
                    item.update(body)
                    return {"id": cronjob_id}
            raise RuntimeError("cronjob not found")
        if path == "/api/v2/cronjobs/status":
            assert body is not None
            cronjob_id = int(body["id"])
            for item in self.cronjobs:
                if int(item["id"]) == cronjob_id:
                    item["status"] = body["status"]
                    return {"id": cronjob_id}
            raise RuntimeError("cronjob not found")
        if path == "/api/v2/cronjobs/handle":
            assert body is not None
            cronjob_id = int(body["id"])
            self.handled_ids.append(cronjob_id)
            return {"id": cronjob_id}
        raise AssertionError(f"unexpected path: {path}")


def write_inventory(root: Path) -> None:
    inventory_file = root / "inventory" / "servers" / "wsl" / "inventory.json"
    inventory_file.parent.mkdir(parents=True, exist_ok=True)
    inventory_file.write_text(
        json.dumps(
            {
                "automations": [
                    {
                        "name": "wsl-zzz-skills-sync",
                        "controller": "1panel-cronjob",
                        "spec": "0 */2 * * *",
                        "cwd": "<repo-root>",
                        "command": "uv run python -m agentplane.cli host automation apply wsl --name wsl-zzz-skills-sync --operation run --execute",
                        "source_root": "external/codex-skills",
                        "target_repo": "external/zzz-skills",
                        "target_branch": "main",
                    },
                    {
                        "name": "wsl-agentplane-secrets-backup",
                        "controller": "1panel-cronjob",
                        "spec": "0 */5 * * *",
                        "cwd": "<repo-root>",
                        "command": "uv run python -m agentplane.cli host automation apply wsl --name wsl-agentplane-secrets-backup --operation run --execute",
                        "env_file": "secrets/services/secrets-backup.r2.wsl.env",
                    },
                ]
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


class HostAutomationTests(unittest.TestCase):
    def test_search_rejects_unknown_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)

            with self.assertRaisesRegex(ValueError, "unsupported automation target"):
                host_automation.search_host_automations(root, "prod9-unknown")

    def test_search_reads_inventory_automation_truth(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)

            payload = host_automation.search_host_automations(root, "wsl")

            self.assertEqual(2, len(payload["items"]))
            self.assertEqual("wsl-zzz-skills-sync", payload["items"][0]["name"])
            self.assertIn("reconcile", payload["items"][0]["supported_operations"])
            self.assertIn("run", payload["items"][0]["supported_operations"])
            self.assertIn("trigger", payload["items"][0]["supported_operations"])

    def test_plan_reconcile_creates_formal_cronjob_script(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)

            payload = host_automation.plan_host_automation(
                root,
                "wsl",
                "wsl-zzz-skills-sync",
                "reconcile",
                executor=FakeExecutor(),
            )

            self.assertTrue(payload["ok"])
            self.assertEqual("create", payload["actions"][0]["mode"])
            self.assertIn("host automation apply wsl --name wsl-zzz-skills-sync --operation run --execute", payload["actions"][0]["body"]["script"])

    def test_verify_detects_legacy_cronjob_script_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            executor = FakeExecutor(
                [
                    {
                        "id": 1,
                        "name": "wsl-agentplane-secrets-backup",
                        "groupID": 0,
                        "spec": "0 */5 * * *",
                        "executor": "bash",
                        "scriptMode": "input",
                        "script": "cd <repo-root> && uv run python -m agentplane.cli automation backup-secrets-r2",
                        "type": "shell",
                        "user": "root",
                        "status": "Enable",
                    }
                ]
            )

            payload = host_automation.verify_host_automation(
                root,
                "wsl",
                "wsl-agentplane-secrets-backup",
                executor=executor,
            )

            self.assertFalse(payload["ok"])
            self.assertTrue(payload["checks"]["spec_match"])
            self.assertFalse(payload["checks"]["script_match"])

    def test_apply_reconcile_updates_drifted_cronjob(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            executor = FakeExecutor(
                [
                    {
                        "id": 2,
                        "name": "wsl-agentplane-secrets-backup",
                        "groupID": 0,
                        "spec": "0 */5 * * *",
                        "executor": "bash",
                        "scriptMode": "input",
                        "script": "cd <repo-root> && uv run python -m agentplane.cli automation backup-secrets-r2",
                        "type": "shell",
                        "user": "root",
                        "status": "Disable",
                    }
                ]
            )

            payload = host_automation.apply_host_automation(
                root,
                "wsl",
                "wsl-agentplane-secrets-backup",
                "reconcile",
                execute=True,
                executor=executor,
            )

            self.assertTrue(payload["ok"])
            self.assertEqual(["update", "status"], [item["mode"] for item in payload["results"]])
            self.assertEqual("Enable", executor.cronjobs[0]["status"])
            self.assertIn(
                "host automation apply wsl --name wsl-agentplane-secrets-backup --operation run --execute",
                str(executor.cronjobs[0]["script"]),
            )

    def test_apply_run_dispatches_registered_runner(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)
            original = host_automation.AUTOMATION_DEFINITIONS["wsl-zzz-skills-sync"]
            host_automation.AUTOMATION_DEFINITIONS["wsl-zzz-skills-sync"] = host_automation.HostAutomationDefinition(
                name="wsl-zzz-skills-sync",
                runner=lambda repo_root, automation: {"status": "ok_no_changes", "repo_root": str(repo_root), "name": automation["name"]},
            )
            try:
                payload = host_automation.apply_host_automation(
                    root,
                    "wsl",
                    "wsl-zzz-skills-sync",
                    "run",
                    execute=True,
                )
            finally:
                host_automation.AUTOMATION_DEFINITIONS["wsl-zzz-skills-sync"] = original

            self.assertTrue(payload["ok"])
            self.assertEqual("run", payload["operation"])
            self.assertEqual("ok_no_changes", payload["result"]["status"])

    def test_plan_trigger_requires_existing_cronjob(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_inventory(root)

            payload = host_automation.plan_host_automation(
                root,
                "wsl",
                "wsl-agentplane-secrets-backup",
                "trigger",
                executor=FakeExecutor(),
            )

            self.assertFalse(payload["ok"])
            self.assertEqual("cronjob missing", payload["reason"])


if __name__ == "__main__":
    unittest.main()
