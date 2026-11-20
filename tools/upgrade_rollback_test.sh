#!/usr/bin/env bash
# Installs an older version of the plugin, upgrades it, then rolls it back, using the
# Claude Code CLI and a local clone as the marketplace. Needs: git, claude.
#   tools/upgrade_rollback_test.sh <old-commit-or-tag> <new-commit-or-tag>
set -euo pipefail
OLD="${1:?old ref}"; NEW="${2:?new ref}"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
WORK="$(mktemp -d)"
MP=enterprise-experts-by-sara
PLUGIN="enterprise-experts@$MP"
cleanup() { claude plugin uninstall "$PLUGIN" >/dev/null 2>&1 || true; claude plugin marketplace remove "$MP" >/dev/null 2>&1 || true; rm -rf "$WORK"; }
trap cleanup EXIT
installed() { claude plugin details "$PLUGIN" 2>/dev/null | head -1 | awk '{print $2}'; }
expect() { local got; got="$(installed)"; [ "$got" = "$1" ] || { echo "FAIL: expected version $1, installed is '$got' ($2)"; exit 1; }; echo "ok: $2 -> $got"; }
ver() { git -C "$WORK/src" show "$1:.claude-plugin/plugin.json" | python3 -c "import json,sys; print(json.load(sys.stdin)['version'])"; }

git clone -q "$REPO" "$WORK/src"
OLDV="$(ver "$OLD")"; NEWV="$(ver "$NEW")"
[ "$OLDV" != "$NEWV" ] || { echo "the two refs have the same version ($OLDV)"; exit 1; }

git -C "$WORK/src" checkout -q "$OLD"
claude plugin marketplace add "$WORK/src" >/dev/null
claude plugin install "$PLUGIN" >/dev/null
expect "$OLDV" "fresh install of the old version"

git -C "$WORK/src" checkout -q "$NEW"
claude plugin marketplace update "$MP" >/dev/null
claude plugin update "$PLUGIN" >/dev/null
expect "$NEWV" "upgrade"

git -C "$WORK/src" checkout -q "$OLD"
claude plugin marketplace update "$MP" >/dev/null
claude plugin uninstall "$PLUGIN" >/dev/null
claude plugin install "$PLUGIN" >/dev/null
expect "$OLDV" "rollback (uninstall, then install the earlier version)"
echo "upgrade and rollback test passed: $OLDV -> $NEWV -> $OLDV"
