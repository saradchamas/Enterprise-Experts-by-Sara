#!/usr/bin/env bash
# Builds the audit image and checks that it works and stays inside its limits.
set -euo pipefail
cd "$(dirname "$0")/.."

REPORTS="$(mktemp -d)"
chmod 777 "$REPORTS"
export PROJECT_DIR="$PWD/tests/fixtures/flawed-node" REPORTS_DIR="$REPORTS"

[ "${SKIP_BUILD:-0}" = 1 ] || docker compose build audit
docker compose run --rm audit >/dev/null
test -s "$REPORTS/discovery.json" || { echo "FAIL: discovery.json was not written"; exit 1; }
if grep -rq "FixturePassw0rd" "$REPORTS"; then echo "FAIL: a secret leaked into the report"; exit 1; fi

set +e
docker compose run --rm audit score --review /reports >/dev/null
code=$?
set -e
[ "$code" -eq 2 ] || { echo "FAIL: scoring an empty review returned $code, expected 2 (invalid)"; exit 1; }

out="$(docker compose run --rm --entrypoint sh audit -c '
  id -u
  touch /project/x 2>/dev/null && echo WROTE_PROJECT
  touch /opt/x 2>/dev/null && echo WROTE_IMAGE
  python -c "import socket; socket.create_connection((\"1.1.1.1\", 443), 3)" 2>/dev/null && echo HAS_NETWORK
  grep CapEff /proc/self/status')"
echo "$out"
echo "$out" | head -1 | grep -qx 10001 || { echo "FAIL: container does not run as the unprivileged user"; exit 1; }
for bad in WROTE_PROJECT WROTE_IMAGE HAS_NETWORK; do
  if echo "$out" | grep -q "$bad"; then echo "FAIL: $bad"; exit 1; fi
done
echo "$out" | grep -q "CapEff:.0000000000000000" || { echo "FAIL: container holds capabilities"; exit 1; }
rm -rf "$REPORTS"
echo "docker smoke test passed"
