import unittest

from agentplane.scripts.onepanel.object_api import build_app_install_params, plan_app_install, plan_installed_app_operation


class OnePanelAppPlanTests(unittest.TestCase):
    def test_build_app_install_params_returns_empty_for_missing_or_non_mapping_params(self) -> None:
        self.assertEqual({}, build_app_install_params("demo", {}))

        for value in ([], "invalid", 42):
            with self.subTest(params=value):
                self.assertEqual({}, build_app_install_params("demo", {"params": value}))

    def test_build_app_install_params_keeps_form_field_defaults(self) -> None:
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
            build_app_install_params("demo", detail),
        )

    def test_plan_app_install_uses_empty_params_when_detail_params_is_none(self) -> None:
        plan = plan_app_install(
            app_key="openresty",
            app_type="website",
            detail={
                "id": 22,
                "params": None,
                "dockerCompose": "services:\n  openresty:\n    image: nginx:alpine\n",
                "hostMode": False,
            },
        )

        self.assertEqual("/api/v2/apps/install", plan.path)
        self.assertEqual("openresty", plan.body["name"])
        self.assertEqual(
            {
                "WEBSITE_DIR": "/data/1panel/www",
                "PANEL_APP_PORT_HTTP": 80,
                "PANEL_APP_PORT_HTTPS": 443,
            },
            plan.body["params"],
        )
        self.assertIn("services:", plan.body["dockerCompose"])

    def test_start_and_stop_plans_use_installed_app_operation_endpoint(self) -> None:
        for operate in ("start", "stop"):
            with self.subTest(operate=operate):
                plan = plan_installed_app_operation(install_id=3, operate=operate)

                self.assertEqual("/api/v2/apps/installed/op", plan.path)
                self.assertEqual({"installId": 3, "operate": operate}, {k: plan.body[k] for k in ("installId", "operate")})
                self.assertFalse(plan.body["deleteDB"])
                self.assertFalse(plan.body["pullImage"])


if __name__ == "__main__":
    unittest.main()

