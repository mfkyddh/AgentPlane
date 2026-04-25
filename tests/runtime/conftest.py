"""Per-directory default markers for tests/runtime/.

Runtime tests use mocked subprocess / pure functions — they are
integration-level, not full CLI E2E.
"""

import pytest

pytestmark = [pytest.mark.integration]
