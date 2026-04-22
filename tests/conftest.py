import pytest

from tests.support.markers import apply_marker_rules


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    apply_marker_rules(items)
