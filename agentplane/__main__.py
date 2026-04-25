"""Allow running ``python -m agentplane`` as a CLI entry point."""

import sys

from agentplane.cli.app import main

sys.exit(main())
