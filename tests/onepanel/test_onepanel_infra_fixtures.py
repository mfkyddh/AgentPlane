from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock
from unittest.mock import patch

import pytest
from agentplane.scripts.onepanel import (
    env_targets,  # type: ignore  # noqa: E402
    public_ingress,  # type: ignore  # noqa: E402
)
from agentplane.scripts.onepanel.compose_policy import (  # type: ignore  # noqa: E402
    enforce_zqf_network,
    normalize_compose_for_app,
    requires_host_network,
)
from agentplane.scripts.onepanel.fixture_manager import (
    apply_fixture,
    cleanup_fixture,
    plan_fixture,
    resolve_fixture_spec,
    resolve_suite_targets,
)
from agentplane.scripts.onepanel.verification import run_verification_suite
from tests.support.constants import CONTAINER_OPENRESTY, CONTAINER_SUB2API, FAKE_HOST_BINDING
from tests.support.paths import REPO_ROOT

pytestmark = pytest.mark.e2e

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
ONEPANEL_SCRIPTS = REPO_ROOT / "agentplane" / "scripts" / "onepanel"
if str(ONEPANEL_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(ONEPANEL_SCRIPTS))
