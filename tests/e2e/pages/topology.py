"""Topology Page Object."""

from __future__ import annotations

from playwright.sync_api import Page

from tests.e2e.pages.base import BasePage


class TopologyPage(BasePage):
    def __init__(self, page: Page) -> None:
        super().__init__(page)

    def navigate(self) -> None:
        self.navigate_to("topology")

    def target_count(self) -> int:
        return self.page.locator(".topo-target-header").count()

    def expand_target(self, index: int) -> None:
        self.page.locator(".topo-target-header").nth(index).click()
        self.page.wait_for_timeout(300)

    def is_target_expanded(self, index: int) -> bool:
        header = self.page.locator(".topo-target-header").nth(index)
        expand_icon = header.locator(".topo-expand")
        return expand_icon.inner_text().strip() == "▼"

    def app_card_count(self) -> int:
        return self.page.locator(".topo-app-card").count()

    def service_card_count(self) -> int:
        return self.page.locator(".topo-svc-card").count()

    def click_app_card(self, index: int) -> None:
        self.page.locator(".topo-app-card").nth(index).click()
        self.page.wait_for_timeout(500)

    def detail_panel_visible(self) -> bool:
        return self.page.locator(".detail-panel").is_visible()

    def detail_title(self) -> str:
        return self.page.locator(".detail-title").inner_text()

    def close_detail(self) -> None:
        self.page.locator(".detail-close").click()
        self.page.wait_for_timeout(300)

    def has_empty_state(self) -> bool:
        return self.page.locator(".empty-state").count() > 0

    def click_refresh(self) -> None:
        self.page.locator(".retry-btn").first.click()
        self.page.wait_for_timeout(1000)
