#!/usr/bin/env bash
# CR8 Mesh — VS Code session runner.
#
# One command runs the full logic sequence for a working session and
# drops a timestamped session folder with the results. This is the script
# that affects the session: Copilot (or Taheed) runs it in the VS Code
# terminal, the map stops lying, and the output folder is the evidence.
#
#   bash run_session.sh [path-to-v1-mesh-context.json]
#
# Sequence:
#   1. Gate zero (if run on the Lenovo: sshd check; skipped elsewhere)
#   2. Migrate v1 -> v2 (only if mesh-context-v2.json doesn't exist yet)
#   3. Decay stale claims to unprobed
#   4. Validate (fails loud if any status lacks evidence / counts mismatch)
#   5. Summary counts (computed, never hand-typed)
#   6. Triage walk from the Lenovo (the root of the blocked queue)
set -eu
cd "$(dirname "$0")"

V1="${1:-$HOME/workspace/user/files/mesh-context.json}"
LEGEND="../ALERT-LEGEND.md"
V2="mesh-context-v2.json"
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="../session-output/$STAMP"
mkdir -p "$OUT"

echo "=== CR8 mesh session $STAMP ===" | tee "$OUT/session.log"

if [ -f /etc/os-release ] && command -v systemctl >/dev/null 2>&1 && [ -d /home/taheed ]; then
  bash gate_zero_sshd.sh 2>&1 | tee "$OUT/gate-zero.log" || true
else
  echo "[1/6] gate zero: not on the Lenovo — run gate_zero_sshd.sh there" | tee -a "$OUT/session.log"
fi

if [ ! -f "$V2" ]; then
  echo "[2/6] migrate v1 -> v2" | tee -a "$OUT/session.log"
  python3 migrate_v1_to_v2.py --v1 "$V1" --legend "$LEGEND" --out "$V2" | tee -a "$OUT/session.log"
else
  echo "[2/6] migrate: $V2 already exists, keeping it" | tee -a "$OUT/session.log"
fi

echo "[3/6] decay stale claims" | tee -a "$OUT/session.log"
python3 mesh_logic.py decay "$V2" --write | tee -a "$OUT/session.log"

echo "[4/6] validate" | tee -a "$OUT/session.log"
python3 mesh_logic.py validate "$V2" | tee -a "$OUT/session.log"

echo "[5/6] summary (computed counts)" | tee -a "$OUT/session.log"
python3 mesh_logic.py summary "$V2" | tee "$OUT/summary.json"

echo "[6/6] triage from lenovo" | tee -a "$OUT/session.log"
python3 triage.py "$V2" lenovo | tee "$OUT/triage-lenovo.txt" || true

cp "$V2" "$OUT/mesh-context-v2.json"
echo "=== session output: $OUT ==="
