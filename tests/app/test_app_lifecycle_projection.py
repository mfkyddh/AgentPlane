import unittest

from agentplane.domain.app.projection_lifecycle import (
    LifecycleIntent,
    LifecycleLayer,
    ProjectionLifecyclePlan,
    ProjectionLifecycleStage,
    default_offboarding_plan,
    default_onboarding_plan,
)


class ProjectionLifecyclePlanTests(unittest.TestCase):
    def test_onboarding_default_plan_sequence(self) -> None:
        plan = default_onboarding_plan(dry_run=False)
        plan.validate()
        summary = plan.summary()

        self.assertEqual(summary["intent"], "onboarding")
        self.assertTrue(summary["write_expected"])
        self.assertEqual(
            summary["layers"],
            ["projection", "runtime-env", "ledger", "doc-sync"],
        )
        self.assertEqual(summary["sequence"][-1], "doc sync confirmation")

    def test_offboarding_default_plan_summary(self) -> None:
        plan = default_offboarding_plan(dry_run=False)
        plan.validate()
        summary = plan.summary()

        self.assertEqual(summary["intent"], "offboarding")
        self.assertEqual(summary["sequence"][0], "projection retirement")
        self.assertIn("ledger retirement", summary["sequence"])
        self.assertEqual(summary["layers"][-1], "doc-sync")

    def test_dry_run_blocks_write_stage(self) -> None:
        plan = ProjectionLifecyclePlan(LifecycleIntent.ONBOARDING, dry_run=True)
        stage = ProjectionLifecycleStage(
            layer=LifecycleLayer.PROJECTION,
            name="projection",
            description="dry-run stub",
            write_mode=True,
        )

        with self.assertRaises(ValueError):
            plan.add_stage(stage)

    def test_missing_doc_sync_fails_validation(self) -> None:
        plan = ProjectionLifecyclePlan(LifecycleIntent.ONBOARDING, dry_run=False)
        plan.add_stage(
            ProjectionLifecycleStage(
                layer=LifecycleLayer.PROJECTION,
                name="inventory projection",
                description="capture inventory",
                write_mode=True,
            )
        )

        with self.assertRaises(ValueError):
            plan.validate()

    def test_out_of_order_stages_rejected(self) -> None:
        plan = ProjectionLifecyclePlan(LifecycleIntent.OFFBOARDING, dry_run=False)
        plan.add_stage(
            ProjectionLifecycleStage(
                layer=LifecycleLayer.RUNTIME_ENV,
                name="runtime cleanup",
                description="capture state",
                write_mode=False,
            )
        )

        with self.assertRaises(ValueError):
            plan.add_stage(
                ProjectionLifecycleStage(
                    layer=LifecycleLayer.PROJECTION,
                    name="projection retirement",
                    description="must not run after runtime stage",
                    write_mode=False,
                )
            )


if __name__ == "__main__":
    unittest.main()

