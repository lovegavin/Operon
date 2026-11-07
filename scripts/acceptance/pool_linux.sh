#!/usr/bin/env bash
# Real Linux/SSH-side multi-workspace pool acceptance.
#
# Usage:
#   scripts/acceptance/pool_linux.sh CONFIG.json WORKSPACE_A WORKSPACE_B GRAPH_A GRAPH_B OUT.json
#
# CONFIG.json must define the server's Python/code_root, admission_dir, token,
# port, and both workspace roots.  Run this on the authorized Linux host with
# an installed candidate.  It starts a real pool service, drives it through the
# product control client, and leaves raw logs/evidence.  It does not start
# cloud resources or upload private datasets.
set -euo pipefail

CONFIG=${1:?pool config JSON is required}
WORKSPACE_A=${2:?workspace A is required}
WORKSPACE_B=${3:?workspace B is required}
GRAPH_A=${4:?graph A is required}
GRAPH_B=${5:?graph B is required}
OUT=${6:?evidence output path is required}

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
PY=${PYTHON:-python3}
export PYTHONPATH="$ROOT:${PYTHONPATH:-}"
EVIDENCE_DIR=$(dirname "$OUT")
mkdir -p "$EVIDENCE_DIR"
LOG="$EVIDENCE_DIR/pool-server.log"
PID=""

cleanup() {
  if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
    kill -TERM "$PID" 2>/dev/null || true
    for _ in $(seq 1 50); do
      kill -0 "$PID" 2>/dev/null || break
      sleep .2
    done
    kill -KILL "$PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT

read -r HOST PORT TOKEN < <("$PY" - "$CONFIG" <<'PY'
import json, sys
from pathlib import Path
value = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
workspaces = {str(Path(item['root']).expanduser().resolve()) for item in value.get('workspaces', [])}
print(value.get('host', '127.0.0.1'), int(value['port']), value['token'])
PY
)

"$PY" -m biopipe pool serve --config "$CONFIG" --port "$PORT" >"$LOG" 2>&1 &
PID=$!

"$PY" - "$HOST" "$PORT" "$TOKEN" <<'PY'
import sys, time
from biopipe.pool_service import PoolClient
host, port, token = sys.argv[1], int(sys.argv[2]), sys.argv[3]
client = PoolClient((host, port), token, timeout=2)
deadline = time.monotonic() + 90
while time.monotonic() < deadline:
    try:
        client.status(); print('pool-ready'); raise SystemExit(0)
    except OSError:
        time.sleep(.25)
raise SystemExit('pool did not become ready; see pool-server.log')
PY

"$PY" "$ROOT/scripts/acceptance/pool_client_checks.py" \
  --address "$HOST:$PORT" --token "$TOKEN" \
  --workspace-a "$WORKSPACE_A" --workspace-b "$WORKSPACE_B" \
  --principal-a "${POOL_PRINCIPAL_A:-pool-a}" \
  --principal-b "${POOL_PRINCIPAL_B:-pool-b}" \
  --graph-a "$GRAPH_A" --graph-b "$GRAPH_B" --out "$OUT"

echo "evidence: $OUT"
echo "server log: $LOG"
