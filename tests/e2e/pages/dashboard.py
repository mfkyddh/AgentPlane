"""Dashboard Page Object."""

from __future__ import annotations

from playwright.sync_api import Page

from tests.e2e.pages.base import BasePage


class DashboardPage(BasePage):
    def __init__(self, page: Page) -> None:
        super().__init__(page)

    # ── KPI Stats ──

    def kpi_stat_count(self) -> int:
        return self.page.locator(".stat-card").count()

    def kpi_stat_value(self, index: int) -> str:
        return self.page.locator(".stat-card .stat-value").nth(index).inner_text()

    # ── Domain Health Cards ──

    def domain_card_count(self) -> int:
        return self.page.locator(".domain-card").count()

    def domain_card_names(self) -> list[str]:
        return self.page.locator(".domain-card-name").all_inner_texts()

    # ── Topology section ──

    def topology_target_count(self) -> int:
        return self.page.locator(".topo-target-header").count()

    def expand_topology_target(self, index: int) -> None:
        self.page.locator(".topo-target-header").nth(index).click()
        self.page.wait_for_timeout(300)

    def topology_app_count(self) -> int:
        return self.page.locator(".topo-app-card").count()

    # ── Apps table ──

    def app_row_count(self) -> int:
        return self.page.locator(".apps-table tbody tr, .app-row").count()

    # ── Hosts ──

    def host_count(self) -> int:
        return self.page.locator(".host-row, .host-card").count()

    # ── Operations ──

    def operation_count(self) -> int:
        return self.page.locator(".ops-row, .op-item").count()

    # ── App detail panel ──

    def open_app_detail(self, app_index: int) -> None:
        self.page.locator(".topo-app-card").nth(app_index).click()
        self.page.wait_for_timeout(500)

    def detail_panel_visible(self) -> bool:
        return self.page.locator(".detail-panel").is_visible()

    def close_detail_panel(self) -> None:
        self.page.locator(".detail-close").click()
        self.page.wait_for_timeout(300)

    def detail_panel_title(self) -> str:
        return self.page.locator(".detail-title").inner_text()
