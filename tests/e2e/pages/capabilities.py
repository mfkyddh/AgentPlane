"""Capabilities Page Object."""

from __future__ import annotations

from playwright.sync_api import Page

from tests.e2e.pages.base import BasePage


class CapabilitiesPage(BasePage):
    def __init__(self, page: Page) -> None:
        super().__init__(page)

    def navigate(self) -> None:
        self.navigate_to("capability-map")

    def category_count(self) -> int:
        return self.page.locator(".cap-layer").count()

    def expand_category(self, index: int) -> None:
        self.page.locator(".cap-layer-header").nth(index).click()
        self.page.wait_for_timeout(300)

    def skill_count(self) -> int:
        return self.page.locator(".cap-item").count()

    def has_content(self) -> bool:
        return self.page.locator(".cap-layer").count() > 0
