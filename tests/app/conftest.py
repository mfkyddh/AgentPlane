"""Per-directory default markers.

Instead of adding @pytest.mark.e2e to every single test class/function,
we use pytestmark at the directory conftest level. Individual tests or
files can override by declaring their own pytestmark.
"""

import pytest

# All tests under tests/app/ are E2E (full CLI subprocess) unless overridden.
pytestmark = [pytest.mark.e2e]
