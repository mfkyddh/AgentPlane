"""E2E test fixtures — server lifecycle, browser context, page objects."""

from __future__ import annotations

import socket
import threading
import time
from pathlib import Path

import pytest
import uvicorn
from agentplane.web.server import create_app


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def e2e_server(repo_root):
    """Start a test FastAPI server on a random port; yield base URL."""
    port = _free_port()
    app = create_app(repo_root, token=None)
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    # Wait until server is responsive
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                break
        except OSError:
            time.sleep(0.1)
    else:
        raise RuntimeError(f"Server did not start on port {port}")
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture()
def ap_page(context, e2e_server):
    """A fresh Playwright Page navigated to the app (named to avoid shadowing built-in page)."""
    pg = context.new_page()
    pg.goto(e2e_server, wait_until="networkidle")
    pg._e2e_base_url = e2e_server
    yield pg
    pg.close()


@pytest.fixture()
def page(ap_page):
    """Alias so test files can use 'page' as parameter name."""
    return ap_page


@pytest.fixture()
def dashboard_page(page):
    from tests.e2e.pages.dashboard import DashboardPage

    return DashboardPage(page)


@pytest.fixture()
def topology_page(page):
    from tests.e2e.pages.topology import TopologyPage

    return TopologyPage(page)


@pytest.fixture()
def capabilities_page(page):
    from tests.e2e.pages.capabilities import CapabilitiesPage

    return CapabilitiesPage(page)


@pytest.fixture()
def chat_page(page):
    from tests.e2e.pages.chat import ChatPage

    return ChatPage(page)
