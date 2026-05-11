"""Chat Page Object."""

from __future__ import annotations

from playwright.sync_api import Page

from tests.e2e.pages.base import BasePage


class ChatPage(BasePage):
    def __init__(self, page: Page) -> None:
        super().__init__(page)

    def navigate(self) -> None:
        self.navigate_to("chat")

    def send_message(self, text: str) -> None:
        input_el = self.page.locator(".chat-input, textarea.chat-input")
        input_el.fill(text)
        self.page.locator("button:has-text('发送'), button:has-text('Send')").click()
        self.page.wait_for_timeout(1000)

    def message_count(self) -> int:
        return self.page.locator(".chat-message, .chat-msg").count()

    def last_message_text(self) -> str:
        msgs = self.page.locator(".chat-message, .chat-msg")
        return msgs.last.inner_text()

    def has_welcome_message(self) -> bool:
        return self.page.locator(".chat-welcome, .chat-message").count() > 0

    def input_placeholder(self) -> str:
        return self.page.locator(".chat-input, textarea.chat-input").get_attribute("placeholder") or ""
