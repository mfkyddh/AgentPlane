from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from agentplane.adapters.service import docker_runtime
from agentplane.domain.service import lifecycle as service_lifecycle
from agentplane.domain.service.models import ServiceDefinition
from tests.support.service_cli import (
    _FakeCloudflareClient,
    run_cli,
    run_cli_inline,
    write_fake_service_ssh,
    write_inventory,
)

pytestmark = pytest.mark.e2e
