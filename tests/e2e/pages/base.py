"""Base Page Object with shared helpers for all views."""

from __future__ import annotations

from playwright.sync_api import Page, expect


class BasePage:
    def __init__(self, page: Page) -> None:
        self.page = page

    # ── Navigation ──

    def navigate_to(self, view: str) -> None:
        """Click a sidebar nav item by view key (dashboard/topology/capability-map/chat)."""
        self.page.click(f".nav-item >> text={self._nav_label(view)}")
        self.page.wait_for_timeout(300)

    def _nav_label(self, view: str) -> str:
        labels = {
            "dashboard": "概览",
            "topology": "拓扑",
            "capability-map": "能力地图",
            "chat": "对话",
        }
        return labels.get(view, view)

    # ── Common assertions ──

    def expect_topbar_title(self, title: str) -> None:
        expect(self.page.locator(".topbar-title")).to_have_text(title)

    def expect_connected(self) -> None:
        """Assert the live status dot is not in disconnected state."""
        dot = self.page.locator(".sidebar-footer-dot")
        expect(dot).not_to_have_class("disconnected")

    # ── i18n ──

    def toggle_locale(self) -> None:
        self.page.click(".sidebar-locale-btn")
        self.page.wait_for_timeout(500)

    def current_locale_button_text(self) -> str:
        return self.page.locator(".sidebar-locale-btn").inner_text()

    # ── Refresh ──

    def click_refresh(self) -> None:
        btn = self.page.locator("button:has-text('刷新'), button:has-text('Refresh')")
        if btn.count() > 0:
            btn.first.click()
            self.page.wait_for_timeout(500)

    # ── Loading / Error states ──

    def expect_no_error(self) -> None:
        error = self.page.locator(".error-state")
        expect(error).to_have_count(0)

    def expect_loading_skeleton(self) -> bool:
        return self.page.locator(".skeleton").count() > 0
