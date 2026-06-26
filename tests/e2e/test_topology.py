"""E2E tests for Topology view."""

import pytest


@pytest.mark.e2e
class TestTopology:
    def test_navigate_to_topology(self, topology_page):
        """Can navigate to topology view."""
        topology_page.navigate()
        topology_page.expect_topbar_title("拓扑")

    def test_topology_loads_without_error(self, topology_page):
        """Topology view loads without error state."""
        topology_page.navigate()
        topology_page.expect_no_error()

    def test_targets_visible_or_empty(self, topology_page):
        """Topology shows targets or empty state — no crash."""
        topology_page.navigate()
        count = topology_page.target_count()
        if count == 0:
            assert topology_page.has_empty_state(), "No targets but no empty state shown"

    def test_target_expand_collapse(self, topology_page):
        """Clicking a target header toggles its children."""
        topology_page.navigate()
        if topology_page.target_count() == 0:
            pytest.skip("No targets to expand")
        # First target is auto-expanded on load; click to collapse
        topology_page.expand_target(0)
        assert not topology_page.is_target_expanded(0)
        # Click again to re-expand
        topology_page.expand_target(0)
        assert topology_page.is_target_expanded(0)

    def test_refresh_loads_data(self, topology_page):
        """Clicking refresh on topology view loads data."""
        topology_page.navigate()
        topology_page.click_refresh()
        topology_page.expect_no_error()

    def test_app_detail_panel(self, topology_page):
        """Clicking an app card opens the detail panel."""
        topology_page.navigate()
        topology_page.click_refresh()  # ensure data loaded
        if topology_page.target_count() == 0:
            pytest.skip("No targets")
        topology_page.expand_target(0)
        if topology_page.app_card_count() == 0:
            pytest.skip("No app cards to click")
        topology_page.click_app_card(0)
        assert topology_page.detail_panel_visible()
        assert len(topology_page.detail_title()) > 0

    def test_detail_panel_close(self, topology_page):
        """Detail panel can be closed."""
        topology_page.navigate()
        topology_page.click_refresh()
        if topology_page.target_count() == 0:
            pytest.skip("No targets")
        topology_page.expand_target(0)
        if topology_page.app_card_count() == 0:
            pytest.skip("No app cards")
        topology_page.click_app_card(0)
        assert topology_page.detail_panel_visible()
        topology_page.close_detail()
        assert not topology_page.detail_panel_visible()
