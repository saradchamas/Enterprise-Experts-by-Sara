#!/usr/bin/env python3
"""PreToolUse hook: blocks edits and risky commands that an active review does not allow.
Exit code 2 blocks the tool call and shows the message to Claude; 0 lets it proceed."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "enterprise-experts" / "scripts"))

try:
    from ee.guard import decide
    event = json.load(sys.stdin)
    allowed, message = decide(event)
except Exception as exc:  # a broken guard must not silently allow, nor block all work outside reviews
    print(f"Enterprise Experts guard could not evaluate this call: {exc}", file=sys.stderr)
    sys.exit(0 if "event" not in dir() else 2)
if not allowed:
    print(message, file=sys.stderr)
    sys.exit(2)
sys.exit(0)
