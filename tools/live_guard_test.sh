#!/usr/bin/env bash
# Checks the edit guard in a REAL Claude Code session (needs a logged-in `claude`).
# It creates a throwaway project with an open review and asks Claude to edit a file.
# Pass = the file is unchanged, because the plugin's hook blocked the edit.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
mkdir -p "$T/src" && cd "$T" && git init -q && echo "x = 1" > src/app.py
python3 "$REPO/skills/enterprise-experts/scripts/enterprise_experts.py" state init --review enterprise-review/test --mode quick >/dev/null
echo "Asking Claude to edit src/app.py while a review is in the assessment phase..."
claude -p "Use the Edit tool to change x = 1 to x = 2 in src/app.py. Then say in one sentence exactly what happened." \
  --plugin-dir "$REPO" --permission-mode acceptEdits || true
echo
if grep -qx "x = 1" src/app.py; then echo "PASS: the file was not changed (the guard blocked the edit)"; else echo "FAIL: the file was changed"; cat src/app.py; exit 1; fi
