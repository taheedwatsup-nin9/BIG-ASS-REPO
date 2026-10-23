#!/usr/bin/env python3
"""
claude_always_open_v21.py — v2.1 (Claude, 2026-10-22).

v2 launched `claude --remote-control` itself. Without a TTY the CLI drops
into --print mode and exits 1 ("Input must be provided either through
stdin or as a prompt argument"), so v2 could never reach "up".

The Lenovo already has the real source: claude-remote-control.service, a
user unit running `claude remote-control` (server mode, works headless),
enabled at boot with linger on. v2.1 does not start a second CLI. It
watches that unit and its journal, and keeps v2's status file + boot
alert contract:
  ~/.local/state/claude-always-open/status.json
    state: up | down | needs-login,  session_url (environment URL),
    last_session_url, unit_active_since, boot_ts, ts, detail
  Boot alert: same env file + payload as v2 (MUZI_BRIDGE_URL/SECRET in
  ~/.config/cr8mor/.env, legacy ~/.config/cr8mor/env); skipped and noted if absent. No credentials here.
"""

import json
import os
import re
import subprocess
import time
import urllib.request

HOME = os.path.expanduser("~")
STATE_DIR = os.path.join(HOME, ".local", "state", "claude-always-open")
STATUS_FILE = os.path.join(STATE_DIR, "status.json")
# Taheed 2026-10-23: the env file is ~/.config/cr8mor/.env; the old "env" name is kept as a fallback.
ENV_FILES = [os.path.join(HOME, ".config", "cr8mor", ".env"), os.path.join(HOME, ".config", "cr8mor", "env")]
UNIT = os.environ.get("CLAUDE_RC_UNIT", "claude-remote-control.service")
ENV_URL_RE = re.compile(r"https://claude\.ai/code\?environment=env_[A-Za-z0-9]+")
SESSION_RE = re.compile(r"https://claude\.ai/code/session_[A-Za-z0-9]+")
LOGIN_RE = re.compile(r"not logged in|please run /login|authentication|login required", re.I)
POLL_S = 30

_state = {"boot_ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "state": "starting",
          "session_url": None, "last_session_url": None, "unit_active_since": None, "detail": ""}


def write_status(**kw):
    _state.update(kw)
    _state["ts"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    os.makedirs(STATE_DIR, exist_ok=True)
    tmp = STATUS_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(_state, f, indent=2)
    os.chmod(tmp, 0o600)
    os.replace(tmp, STATUS_FILE)


def sh(*args):
    return subprocess.run(args, capture_output=True, text=True, timeout=20).stdout


def load_env():
    env = {}
    for path in reversed(ENV_FILES):          # .env wins over the legacy name
        try:
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        v = v.strip().strip('"').strip("'")
                        if v:
                            env[k.strip()] = v
        except FileNotFoundError:
            pass
    return env


def send_alert(event):
    env = load_env()
    url, secret = env.get("MUZI_BRIDGE_URL"), env.get("MUZI_BRIDGE_SECRET")
    if not url or not secret:
        write_status(detail=f"{event}: alert skipped (MUZI_BRIDGE_URL/SECRET not in env file)")
        return
    payload = json.dumps({"event": event, "ts": _state["ts"], "session_url": _state["session_url"],
                          "host": os.uname().nodename}).encode()
    req = urllib.request.Request(url, data=payload, method="POST",
                                 headers={"Content-Type": "application/json", "x-muzi-secret": secret})
    try:
        urllib.request.urlopen(req, timeout=15)
        write_status(detail=f"alert sent: {event}")
    except Exception as e:
        write_status(detail=f"alert failed ({event}): {type(e).__name__}")


def check():
    active = sh("systemctl", "--user", "is-active", UNIT).strip()
    since = sh("systemctl", "--user", "show", UNIT, "-p", "ActiveEnterTimestamp",
               "--value").strip() or None
    if active != "active":
        return "down", None, None, since, f"{UNIT} is {active or 'unknown'}"
    # Only this run of the unit: journal lines since it last became active.
    log = sh("journalctl", "--user", "-u", UNIT, "-o", "cat", "--no-pager",
             "--since", since or "-1d")
    env_urls, sessions = ENV_URL_RE.findall(log), SESSION_RE.findall(log)
    if env_urls:
        return "up", env_urls[-1], sessions[-1] if sessions else None, since, "unit active, URL from journal"
    if LOGIN_RE.search(log):
        return "needs-login", None, None, since, "unit active but CLI asks for an interactive login"
    return "starting", None, None, since, "unit active, no URL printed yet"


def main():
    write_status(detail="v2.1 daemon started")
    send_alert("lenovo-boot")
    announced = None
    while True:
        try:
            state, url, last, since, detail = check()
        except Exception as e:
            state, url, last, since, detail = "down", None, None, None, f"check error: {type(e).__name__}"
        write_status(state=state, session_url=url, last_session_url=last,
                     unit_active_since=since, detail=detail)
        key = (state, since)
        if state in ("up", "needs-login") and key != announced:
            announced = key
            send_alert("lenovo-claude-up" if state == "up" else "lenovo-claude-needs-login")
        time.sleep(POLL_S)


if __name__ == "__main__":
    main()
