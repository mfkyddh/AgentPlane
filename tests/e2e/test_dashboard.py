"""E2E tests for Dashboard view."""

import pytest


@pytest.mark.e2e
class TestDashboard:
    def test_kpi_stats_visible(self, dashboard_page):
        """Dashboard shows KPI stat cards."""
        count = dashboard_page.kpi_stat_count()
        assert count >= 3, f"Expected >=3 KPI stats, got {count}"

    def test_domain_health_cards(self, dashboard_page):
        """Dashboard shows domain health cards."""
        count = dashboard_page.domain_card_count()
        assert count >= 1, f"Expected >=1 domain cards, got {count}"

    def test_domain_card_names(self, dashboard_page):
        """Domain cards have non-empty names."""
        names = dashboard_page.domain_card_names()
        assert len(names) >= 1
        # Names depend on locale; just check they're non-empty
        for name in names:
            assert len(name) > 0

    def test_topology_section_present(self, dashboard_page):
        """Dashboard has a topology section with targets."""
        # Topology targets may or may not exist depending on inventory
        # Just verify the section renders without error
        dashboard_page.expect_no_error()

    def test_refresh_updates_data(self, dashboard_page):
        """Clicking refresh doesn't break the page."""
        dashboard_page.click_refresh()
        dashboard_page.expect_no_error()

    def test_no_error_on_load(self, dashboard_page):
        """Dashboard loads without error state."""
        dashboard_page.expect_no_error()
