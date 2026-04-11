import argparse
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
ONEPANEL_SCRIPTS = REPO_ROOT / "agentplane" / "scripts" / "onepanel"
if str(ONEPANEL_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(ONEPANEL_SCRIPTS))

from agentplane.scripts.onepanel import app_lifecycle  # type: ignore  # noqa: E402


class OnePanelAppLifecycleTests(unittest.TestCase):
    def test_command_install_uses_empty_params_when_detail_params_is_none(self) -> None:
        with patch.object(app_lifecycle, "TargetExecutor") as executor_cls, patch.object(
            app_lifecycle, "get_target", return_value=object()
        ), patch.object(app_lifecycle, "normalize_compose_for_app", return_value="services: {}"), patch.object(
            app_lifecycle, "requires_host_network", return_value=False
        ):
            executor = executor_cls.return_value
            executor.api_request.side_effect = [
                {"id": 11, "type": "website"},
                {"id": 22, "params": None, "dockerCompose": "raw-compose", "hostMode": False},
                {"id": 33},
            ]

            result = app_lifecycle.command_install(
                argparse.Namespace(
                    env="prod0-main",
                    env_file=None,
                    app="openresty",
                    version="1.27.5",
                    param=[],
                    name=None,
                    container=None,
                    specify_ip=None,
                    restart_policy="always",
                    pull_image=False,
                    wait=False,
                )
            )

            self.assertEqual({"id": 33}, result)
            executor.api_request.assert_called_with(
                "POST",
                "/api/v2/apps/install",
                {
                    "appDetailId": 22,
                    "name": "openresty",
                    "params": {},
                    "advanced": True,
                    "cpuQuota": 0,
                    "memoryLimit": 0,
                    "memoryUnit": "M",
                    "containerName": "",
                    "allowPort": True,
                    "editCompose": True,
                    "dockerCompose": "services: {}",
                    "hostMode": False,
                    "pullImage": False,
                    "gpuConfig": False,
                    "webUI": "",
                    "type": "website",
                    "specifyIP": "",
                    "restartPolicy": "always",
                },
            )

    def test_build_default_params_returns_empty_for_missing_or_non_mapping_params(self) -> None:
        self.assertEqual({}, app_lifecycle.build_default_params({}))

        for value in ([], "invalid", 42):
            with self.subTest(params=value):
                self.assertEqual({}, app_lifecycle.build_default_params({"params": value}))

    def test_build_default_params_keeps_form_field_defaults(self) -> None:
        detail = {
            "params": {
                "formFields": [
                    {"envKey": "PANEL_DB_HOST", "default": "postgres"},
                    {"envKey": "PANEL_PORT", "default": 8080},
                ]
            }
        }

        self.assertEqual(
            {"PANEL_DB_HOST": "postgres", "PANEL_PORT": 8080},
            app_lifecycle.build_default_params(detail),
        )

    def test_start_command_uses_installed_op_start(self) -> None:
        with patch.object(app_lifecycle, "TargetExecutor") as executor_cls, patch.object(
            app_lifecycle, "get_target", return_value=object()
        ):
            executor = executor_cls.return_value
            executor.api_request.return_value = {"ok": True}

            result = app_lifecycle.command_operate(
                argparse.Namespace(env="prod0-main", env_file=None, install_id=3, app=None, name=None, operate="start")
            )

            self.assertEqual({"installId": 3, "operate": "start"}, result)
            executor.api_request.assert_called_once_with(
                "POST",
                "/api/v2/apps/installed/op",
                {
                    "installId": 3,
                    "operate": "start",
                    "forceDelete": False,
                    "deleteBackup": False,
                    "deleteDB": False,
                    "deleteImage": False,
                    "backup": False,
                    "pullImage": False,
                    "dockerCompose": "",
                    "favorite": False,
                },
            )

    def test_stop_command_uses_installed_op_stop(self) -> None:
        with patch.object(app_lifecycle, "TargetExecutor") as executor_cls, patch.object(
            app_lifecycle, "get_target", return_value=object()
        ):
            executor = executor_cls.return_value
            executor.api_request.return_value = {"ok": True}

            result = app_lifecycle.command_operate(
                argparse.Namespace(env="prod0-main", env_file=None, install_id=7, app=None, name=None, operate="stop")
            )

            self.assertEqual({"installId": 7, "operate": "stop"}, result)
            executor.api_request.assert_called_once_with(
                "POST",
                "/api/v2/apps/installed/op",
                {
                    "installId": 7,
                    "operate": "stop",
                    "forceDelete": False,
                    "deleteBackup": False,
                    "deleteDB": False,
                    "deleteImage": False,
                    "backup": False,
                    "pullImage": False,
                    "dockerCompose": "",
                    "favorite": False,
                },
            )


if __name__ == "__main__":
    unittest.main()
