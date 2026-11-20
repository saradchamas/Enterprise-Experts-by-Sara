#!/usr/bin/env python3
"""Kept for compatibility with v0.1: same as `enterprise_experts.py discover`."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ee.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main(["discover"] + sys.argv[1:]))
