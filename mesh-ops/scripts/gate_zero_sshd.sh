#!/usr/bin/env bash
# Gate Zero — Lenovo sshd check. Run this ON the Lenovo, in the VS Code terminal.
#
# Read-only by default: it reports whether openssh-server is installed,
# whether sshd is enabled/running, whether anything listens on :22, and
# whether Tailscale sees this box. It changes NOTHING.
#
#   bash gate_zero_sshd.sh            # check only
#   bash gate_zero_sshd.sh --fix      # install + enable + start sshd (sudo)
#
# Paste the full output back to MUZI — it is the evidence that updates
# mesh alert rows 1,2,3,5,6,7,8,9,10,13,14,18 (12 blocked-on-Lenovo rows).
set -u

echo "=== GATE ZERO: sshd on $(hostname) — $(date -Is) ==="

echo "-- openssh-server package --"
if dpkg -l openssh-server 2>/dev/null | grep -q '^ii'; then
  echo "installed: YES"
else
  echo "installed: NO"
fi

echo "-- service state --"
for unit in ssh sshd; do
  if systemctl list-unit-files "$unit.service" >/dev/null 2>&1 && \
     systemctl list-unit-files "$unit.service" | grep -q "$unit"; then
    echo "$unit: enabled=$(systemctl is-enabled "$unit" 2>/dev/null || echo unknown)" \
         "active=$(systemctl is-active "$unit" 2>/dev/null || echo unknown)"
  fi
done

echo "-- listening on :22 --"
if ss -tlnp 2>/dev/null | grep -q ':22 '; then
  ss -tlnp | grep ':22 '
else
  echo "nothing listening on :22"
fi

echo "-- firewall (ufw, if present) --"
if command -v ufw >/dev/null 2>&1; then sudo -n ufw status 2>/dev/null || ufw status 2>/dev/null || echo "ufw present, status needs sudo"; else echo "no ufw"; fi

echo "-- tailscale self --"
if command -v tailscale >/dev/null 2>&1; then tailscale status --self 2>/dev/null || tailscale status | head -5; else echo "tailscale CLI not found"; fi

echo "-- local banner test --"
(exec 3<>/dev/tcp/127.0.0.1/22 && head -c 60 <&3; echo) 2>/dev/null || echo "no SSH banner on 127.0.0.1:22"

if [ "${1:-}" = "--fix" ]; then
  echo "=== --fix: installing + enabling sshd (sudo) ==="
  sudo apt-get update -qq && sudo apt-get install -y openssh-server
  sudo systemctl enable --now ssh || sudo systemctl enable --now sshd
  echo "-- after fix --"
  ss -tlnp | grep ':22 ' || echo "STILL nothing on :22 — send MUZI this whole output"
fi

echo "=== END GATE ZERO ==="
