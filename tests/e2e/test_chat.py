"""E2E tests for Chat view."""

import pytest


@pytest.mark.e2e
class TestChat:
    def test_navigate_to_chat(self, chat_page):
        """Can navigate to chat view."""
        chat_page.navigate()
        chat_page.expect_topbar_title("Agent 对话")

    def test_welcome_message(self, chat_page):
        """Chat view shows welcome or initial content."""
        chat_page.navigate()
        assert chat_page.has_welcome_message()

    def test_input_has_placeholder(self, chat_page):
        """Chat input has a placeholder text."""
        chat_page.navigate()
        placeholder = chat_page.input_placeholder()
        assert len(placeholder) > 0, "Chat input has no placeholder"
