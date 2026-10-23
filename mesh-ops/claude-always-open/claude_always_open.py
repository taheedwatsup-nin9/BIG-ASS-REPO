#!/usr/bin/env python3
"""
claude_always_open.py — keep the Lenovo's Claude lane up across reboots.

What it does:
  - Runs as a systemd USER service (see claude-always-open.service).
  - Supervises the existing Claude remote-control user service:
    checks `systemctl --user is-active` and that a claude process exists.
  - If either check fails, restarts the Claude service (with backoff so a
    genuinely broken install doesn't get hammered).
  - Writes a heartbeat + health snapshot to
    ~/.local/state/claude-always-open/status.json so any local agent
    (Claude itself, MUZI via the Claude lane) can read lane health.

Security shape (per Taheed, 2026-10-22):
  - NO credentials in this file, ever. The service runs as Taheed's user,
    where Claude Code already holds its own sign-in (~/.claude). This
    script never reads, prints, or copies any credential value.
  - NO network listener. This process opens no sockets at all — nothing
    client-side, nothing public-facing. It only talks to the local
    systemd user manager and writes a local status file.

Author: MUZI, 2026-10-22. Install: see README.md in this folder.
"""

import json
import os
import subprocess
import sys
import time

# --- config ---------------------------------------------------------------
CLAUDE_UNIT = os.environ.get("CLAUDE_ALWAYS_OPEN_UNIT", "claude-remote-control")
CHECK_INTERVAL_S = 30          # how often to check the Claude service
RESTART_BACKOFF_S = [10, 30, 60, 300]  # escalating wait between restarts
STATE_DIR = os.path.expanduser("~/.local/state/claude-always-open")
STATUS_FILE = os.path.join(STATE_DIR, "status.json")
# --------------------------------------------------------------------------


def run(*args):
    return subprocess.run(args, capture_output=True, text=True, timeout=20)


def unit_active(unit):
    try:
        r = run("systemctl", "--user", "is-active", unit)
        return r.stdout.strip() == "active"
    except Exception:
        return False


def claude_process_alive():
    try:
        r = run("pgrep", "-u", str(os.getuid()), "-f", "claude")
        return r.returncode == 0 and r.stdout.strip() != ""
    except Exception:
        return False


def write_status(state, detail):
    os.makedirs(STATE_DIR, exist_ok=True)
    payload = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "unit": CLAUDE_UNIT,
        "state": state,          # "up" | "restarting" | "down"
        "detail": detail,
        "pid": os.getpid(),
    }
    tmp = STATUS_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(payload, f, indent=2)
    os.replace(tmp, STATUS_FILE)


def main():
    write_status("up", "watchdog started")
    backoff_idx = 0
    while True:
        try:
            active = unit_active(CLAUDE_UNIT)
            alive = claude_process_alive()
            if active and alive:
                write_status("up", f"{CLAUDE_UNIT} active, claude process present")
                backoff_idx = 0
            else:
                wait = RESTART_BACKOFF_S[min(backoff_idx, len(RESTART_BACKOFF_S) - 1)]
                write_status(
                    "restarting",
                    f"unit_active={active} process_alive={alive}; restarting "
                    f"{CLAUDE_UNIT} (backoff {wait}s)",
                )
                run("systemctl", "--user", "restart", CLAUDE_UNIT)
                backoff_idx += 1
                time.sleep(wait)
        except Exception as e:  # never die silently — record and keep looping
            try:
                write_status("down", f"watchdog error: {e!r}")
            except Exception:
                pass
        time.sleep(CHECK_INTERVAL_S)


if __name__ == "__main__":
    sys.exit(main())
