#!/usr/bin/env python3
"""Entry point: python enterprise_experts.py <command> ...  (see `--help`)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ee.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
