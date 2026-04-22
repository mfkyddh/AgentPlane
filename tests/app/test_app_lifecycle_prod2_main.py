import unittest
from pathlib import Path

from agentplane.domain.app.lifecycle_prod2_main import (
    PRODUCTION_TARGET,
    build_prod2_main_offboarding_plan,
    build_prod2_main_onboarding_plan,
    describe_prod2_main_topology,
)


class Prod2MainLifecyclePolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[2]

    def test_topology_includes_expected_network_and_websites(self) -> None:
        topology = describe_prod2_main_topology(self.repo_root)

        self.assertEqual(PRODUCTION_TARGET, topology['target'])
        self.assertTrue(any(network.get('name') == 'zqf_network' for network in topology['networks']))
        self.assertTrue(any(site.get('alias') == '1panel' for site in topology['websites']))
        resource_apps = {entry['app'] for entry in topology['app_resources']}
        self.assertIn('sub2api', resource_apps)

    def test_onboarding_plan_references_inventory_and_network_steps(self) -> None:
        plan = build_prod2_main_onboarding_plan(self.repo_root)

        self.assertEqual(PRODUCTION_TARGET, plan['target'])
        self.assertGreaterEqual(len(plan['steps']), 2)
        self.assertIn('host inventory', plan['steps'][0]['commands'][0])
        self.assertIn('host network audit', plan['steps'][1]['commands'][0])

    def test_offboarding_plan_mentions_website_publish(self) -> None:
        plan = build_prod2_main_offboarding_plan(self.repo_root)

        self.assertEqual(PRODUCTION_TARGET, plan['target'])
        commands = [cmd for step in plan['steps'] for cmd in step['commands']]
        self.assertTrue(any('website publish plan' in cmd for cmd in commands))

