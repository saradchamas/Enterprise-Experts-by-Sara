#!/usr/bin/env python3
"""Kept for compatibility with v0.1: `scorecard.py <review_dir>` runs the v2 decision engine.

v0.1 took a findings.json path and could return GO for an incomplete review.
v0.2 scores a whole review folder (findings.json + intake.json + evidence-log.json).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ee.cli import main  # noqa: E402

if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--out" and not a.endswith("scorecard.md")]
    target = Path(args[0]) if args else Path(".")
    sys.exit(main(["score", "--review", str(target.parent if target.is_file() else target)]))
