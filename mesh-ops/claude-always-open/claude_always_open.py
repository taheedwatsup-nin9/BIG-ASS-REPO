#!/usr/bin/env python3
"""
claude_always_open.py — fire off Claude remote control at boot, keep it
alive, and announce it. Basic configurable infrastructure, not AI:
a daemon, a child process, a heartbeat file, and a ping.

How the path works (Taheed's setup, 2026-10-22):
  The Lenovo runs `claude --remote-control` in a terminal. Taheed
  authenticated the CLI once through his Claude subscription in the
  browser; the CLI keeps that sign-in on the machine. The CLI prints a
  session URL — that URL is the comm path into the live CLI terminal.

What this daemon does:
  1. Launches `claude --remote-control` as a child process (inheriting
     the user's environment, where Claude's own sign-in lives — there
     are NO credentials in this file and it never reads any).
  2. Watches the child's output for the session URL and writes it, with
     boot time and state, to ~/.local/state/claude-always-open/status.json
     so anything local can find the current session.
  3. Sends ONE boot alert per (re)start to the alert endpoint configured
     in the canonical env file (~/.config/cr8mor/env: MUZI_BRIDGE_URL +
     MUZI_BRIDGE_SECRET) — the alert carries {event: "lenovo-claude-up",
     ts, session_url}. If the env values are absent, the alert is
     skipped and noted in the status file — the daemon still works.
  4. Supervises the child: if it exits, restart with backoff. If no
     session URL appears within URL_TIMEOUT_S (e.g. the CLI wants an
     interactive re-login), status reads "needs-login" and the alert
     says so — it never pretends to be up.

Nothing here listens on any network interface. Nothing is public-facing.

Run it via the systemd user unit (claude-always-open.service), which
restarts this daemon itself if it ever dies. Enable linger once
(`loginctl enable-linger`) and the whole chain starts at boot, before
any desktop login — Taheed only turns the computer on.

Author: MUZI, 2026-10-22 (v2 — rebuilt to Taheed's walkthrough).
"""

import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.request

HOME = os.path.expanduser("~")
STATE_DIR = os.path.join(HOME, ".local", "state", "claude-always-open")
STATUS_FILE = os.path.join(STATE_DIR, "status.json")
ENV_FILE = os.path.join(HOME, ".config", "cr8mor", "env")
CLAUDE_CMD = [os.environ.get("CLAUDE_BIN", os.path.join(HOME, ".local", "bin", "claude")),
              "--remote-control"]
URL_RE = re.compile(r"https://claude\.ai/code/session_[A-Za-z0-9]+")
URL_TIMEOUT_S = 120
BACKOFF_S = [10, 30, 60, 300]

_state = {"boot_ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
          "session_url": None, "state": "starting", "detail": "", "pid": None}


def write_status(**kw):
    _state.update(kw)
    _state["ts"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    os.makedirs(STATE_DIR, exist_ok=True)
    tmp = STATUS_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(_state, f, indent=2)
    os.replace(tmp, STATUS_FILE)


def load_env():
    env = {}
    try:
        with open(ENV_FILE) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip().strip('"').strip("'")
    except FileNotFoundError:
        pass
    return env


def send_alert(event):
    env = load_env()
    url, secret = env.get("MUZI_BRIDGE_URL"), env.get("MUZI_BRIDGE_SECRET")
    if not url or not secret:
        write_status(detail="alert skipped: MUZI_BRIDGE_URL/SECRET not in env file")
        return
    payload = json.dumps({"event": event, "ts": _state["ts"],
                          "session_url": _state.get("session_url"),
                          "host": os.uname().nodename}).encode()
    req = urllib.request.Request(url, data=payload, method="POST",
                                 headers={"Content-Type": "application/json",
                                          "x-muzi-secret": secret})
    try:
        urllib.request.urlopen(req, timeout=15)
        write_status(detail=f"alert sent: {event}")
    except Exception as e:
        write_status(detail=f"alert failed ({event}): {e!r}")


def watch_output(proc):
    for line in proc.stdout:
        m = URL_RE.search(line)
        if m and _state.get("session_url") != m.group(0):
            write_status(session_url=m.group(0), state="up",
                         detail="session URL captured from CLI output")
            send_alert("lenovo-claude-up")


def run_once():
    write_status(state="starting", session_url=None, detail="launching claude")
    proc = subprocess.Popen(CLAUDE_CMD, cwd=HOME, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, bufsize=1)
    write_status(pid=proc.pid)
    threading.Thread(target=watch_output, args=(proc,), daemon=True).start()
    deadline = time.time() + URL_TIMEOUT_S
    while proc.poll() is None:
        if _state.get("session_url") is None and time.time() > deadline:
            write_status(state="needs-login",
                         detail="no session URL within timeout — CLI likely "
                                "wants an interactive login on the machine")
            send_alert("lenovo-claude-needs-login")
            deadline = float("inf")  # alert once, keep supervising
        time.sleep(2)
    return proc.returncode


def main():
    write_status(state="starting", detail="daemon started")
    send_alert("lenovo-boot")
    attempt = 0
    while True:
        try:
            run_once()
        except Exception as e:
            write_status(state="down", detail=f"daemon error: {e!r}")
        wait = BACKOFF_S[min(attempt, len(BACKOFF_S) - 1)]
        attempt += 1
        write_status(state="restarting", detail=f"claude exited; restart in {wait}s")
        time.sleep(wait)


if __name__ == "__main__":
    sys.exit(main())
