"""Tests for agentplane.scripts.onepanel.compose_project — pure functions with mock executor."""

from __future__ import annotations

from typing import Any

import pytest
from agentplane.scripts.onepanel.compose_project import (
    COMPOSE_PROJECT_DIR,
    create_compose,
    find_compose,
    operate_compose,
    search_compose,
    update_compose,
)

pytestmark = pytest.mark.unit


class _FakeExecutor:
    """Mock executor that records API calls."""

    def __init__(self, responses: dict[str, Any] | None = None) -> None:
        self._responses = responses or {}
        self.calls: list[tuple[str, str, dict[str, Any] | None]] = []

    def api_request(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        self.calls.append((method, path, body))
        return self._responses.get(path, {})


# ---------------------------------------------------------------------------
# search_compose
# ---------------------------------------------------------------------------


class TestSearchCompose:
    def test_returns_items(self) -> None:
        executor = _FakeExecutor({
            "/api/v2/containers/compose/search": {"items": [{"name": "proj1"}, {"name": "proj2"}]},
        })
        result = search_compose(executor)
        assert len(result) == 2
        assert result[0]["name"] == "proj1"

    def test_empty_items(self) -> None:
        executor = _FakeExecutor({
            "/api/v2/containers/compose/search": {"items": []},
        })
        result = search_compose(executor)
        assert result == []

    def test_non_dict_response(self) -> None:
        executor = _FakeExecutor({
            "/api/v2/containers/compose/search": "bad",
        })
        result = search_compose(executor)
        assert result == []

    def test_non_list_items(self) -> None:
        executor = _FakeExecutor({
            "/api/v2/containers/compose/search": {"items": "bad"},
        })
        result = search_compose(executor)
        assert result == []

    def test_with_info_filter(self) -> None:
        executor = _FakeExecutor({
            "/api/v2/containers/compose/search": {"items": []},
        })
        search_compose(executor, info="test")
        _, _, body = executor.calls[0]
        assert body["info"] == "test"


# ---------------------------------------------------------------------------
# find_compose
# ---------------------------------------------------------------------------


class TestFindCompose:
    def test_found(self) -> None:
        executor = _FakeExecutor({
            "/api/v2/containers/compose/search": {"items": [{"name": "proj1"}, {"name": "proj2"}]},
        })
        result = find_compose(executor, "proj2")
        assert result is not None
        assert result["name"] == "proj2"

    def test_not_found(self) -> None:
        executor = _FakeExecutor({
            "/api/v2/containers/compose/search": {"items": [{"name": "proj1"}]},
        })
        result = find_compose(executor, "missing")
        assert result is None


# ---------------------------------------------------------------------------
# create_compose
# ---------------------------------------------------------------------------


class TestCreateCompose:
    def test_creates_with_correct_payload(self) -> None:
        executor = _FakeExecutor({
            "/api/v2/containers/compose": {"id": 1, "name": "myapp"},
        })
        result = create_compose(executor, name="myapp", content="version: '3'")
        assert result["name"] == "myapp"
        _, path, body = executor.calls[0]
        assert path == "/api/v2/containers/compose"
        assert body["name"] == "myapp"
        assert body["from"] == "edit"

    def test_test_only_endpoint(self) -> None:
        executor = _FakeExecutor({
            "/api/v2/containers/compose/test": {"ok": True},
        })
        create_compose(executor, name="myapp", content="version: '3'", test_only=True)
        _, path, _ = executor.calls[0]
        assert path == "/api/v2/containers/compose/test"

    def test_non_dict_result_raises(self) -> None:
        executor = _FakeExecutor({
            "/api/v2/containers/compose": "bad",
        })
        with pytest.raises(ValueError, match="must be an object"):
            create_compose(executor, name="myapp", content="v")

    def test_force_pull(self) -> None:
        executor = _FakeExecutor({
            "/api/v2/containers/compose": {"ok": True},
        })
        create_compose(executor, name="myapp", content="v", force_pull=True)
        _, _, body = executor.calls[0]
        assert body["forcePull"] is True


# ---------------------------------------------------------------------------
# update_compose
# ---------------------------------------------------------------------------


class TestUpdateCompose:
    def test_updates_with_correct_payload(self) -> None:
        executor = _FakeExecutor({
            "/api/v2/containers/compose/update": {"ok": True},
        })
        result = update_compose(executor, name="myapp", detail_path="/detail", content="v2")
        assert result["ok"] is True
        _, path, body = executor.calls[0]
        assert path == "/api/v2/containers/compose/update"
        assert body["path"] == f"{COMPOSE_PROJECT_DIR}/myapp/docker-compose.yml"
        assert body["detailPath"] == "/detail"

    def test_non_dict_result_raises(self) -> None:
        executor = _FakeExecutor({
            "/api/v2/containers/compose/update": None,
        })
        with pytest.raises(ValueError, match="must be an object"):
            update_compose(executor, name="myapp", detail_path="/d", content="v")


# ---------------------------------------------------------------------------
# operate_compose
# ---------------------------------------------------------------------------


class TestOperateCompose:
    def test_operate_up(self) -> None:
        executor = _FakeExecutor({
            "/api/v2/containers/compose/operate": {"ok": True},
        })
        result = operate_compose(executor, name="myapp", operation="up")
        assert result["ok"] is True
        _, _, body = executor.calls[0]
        assert body["operation"] == "up"

    def test_operate_with_force(self) -> None:
        executor = _FakeExecutor({
            "/api/v2/containers/compose/operate": {"ok": True},
        })
        operate_compose(executor, name="myapp", operation="down", force=True)
        _, _, body = executor.calls[0]
        assert body["force"] is True

    def test_non_dict_result_raises(self) -> None:
        executor = _FakeExecutor({
            "/api/v2/containers/compose/operate": "bad",
        })
        with pytest.raises(ValueError, match="must be an object"):
            operate_compose(executor, name="myapp", operation="up")


# ---------------------------------------------------------------------------
# Golden test
# ---------------------------------------------------------------------------


@pytest.mark.golden
class TestComposeProjectGolden:
    def test_full_crud_roundtrip(self) -> None:
        """Search → find → create → update → operate all work with mock executor."""
        executor = _FakeExecutor({
            "/api/v2/containers/compose/search": {"items": [{"name": "myapp"}]},
            "/api/v2/containers/compose": {"id": 1, "name": "myapp"},
            "/api/v2/containers/compose/update": {"ok": True},
            "/api/v2/containers/compose/operate": {"ok": True},
        })

        items = search_compose(executor)
        assert len(items) == 1

        found = find_compose(executor, "myapp")
        assert found is not None

        created = create_compose(executor, name="myapp", content="version: '3'")
        assert created["name"] == "myapp"

        updated = update_compose(executor, name="myapp", detail_path="/d", content="v2")
        assert updated["ok"] is True

        operated = operate_compose(executor, name="myapp", operation="up")
        assert operated["ok"] is True
