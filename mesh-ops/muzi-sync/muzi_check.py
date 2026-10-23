#!/usr/bin/env python3
"""
muzi_check.py — Claude <-> MUZI mutual check, run every few minutes while collating.

Each run:
  1. Reads MUZI's posts on the live thread (Supabase bac_messages, via the public
     viewer's anon key read at runtime) newer than the last run; appends them to
     Claude's BAC inbox and prints them.
  2. Posts one heartbeat line (author Claude, kind heartbeat) through the same n8n
     webhook the board watcher uses: what Claude is doing, and how long MUZI has
     been quiet. If MUZI has been silent past SILENT_MIN, the heartbeat pings MUZI.

Claude's current task line lives in STATUS (one line; Claude updates it as work moves).
Exit code 3 = new MUZI posts arrived (so a caller knows to act).
"""

import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone

VIEWER = "https://bac-live-thread.zeabur.app/"
SUPABASE = "https://dgxabvxwiqrzzdmwdxha.supabase.co/rest/v1/bac_messages"
WEBHOOK = "https://cr8mor-n8n.zeabur.app/webhook/bac-message"
INBOX = os.path.expanduser("~/Desktop/BAC-GROUP/CONFIGURATIONS/inbox/Claude.md")
STATE = os.path.expanduser("~/.local/state/muzi-check.json")
STATUS = os.path.expanduser("~/.local/state/claude-status.txt")
SILENT_MIN = 20


def anon_key():
    html = urllib.request.urlopen(VIEWER, timeout=15).read().decode()
    return re.search(r'SUPABASE_ANON_KEY\s*=\s*"([^"]+)"', html).group(1)


def muzi_posts(since):
    key = anon_key()
    q = f"{SUPABASE}?select=created_at,kind,body&author=eq.MUZI&order=created_at.asc&limit=50"
    if since:
        q += "&created_at=gt." + urllib.request.quote(since)
    req = urllib.request.Request(q, headers={"apikey": key, "Authorization": "Bearer " + key})
    return json.load(urllib.request.urlopen(req, timeout=15))


def last_muzi_time():
    key = anon_key()
    q = f"{SUPABASE}?select=created_at&author=eq.MUZI&order=created_at.desc&limit=1"
    req = urllib.request.Request(q, headers={"apikey": key, "Authorization": "Bearer " + key})
    rows = json.load(urllib.request.urlopen(req, timeout=15))
    return rows[0]["created_at"] if rows else None


def heartbeat(body):
    req = urllib.request.Request(WEBHOOK, method="POST", headers={"Content-Type": "application/json"},
                                 data=json.dumps({"author": "Claude", "kind": "heartbeat", "body": body}).encode())
    urllib.request.urlopen(req, timeout=15)


def main():
    state = json.load(open(STATE)) if os.path.exists(STATE) else {}
    new = muzi_posts(state.get("since"))
    if new:
        with open(INBOX, "a") as f:
            for r in new:
                f.write(f"\n[{r['created_at'][:16]}Z] {r['kind'].upper()} from MUZI (live thread): "
                        f"{' '.join(r['body'].split())[:400]}\n")
        state["since"] = new[-1]["created_at"]
        for r in new:
            print(f"--- MUZI {r['created_at'][:16]}Z {r['kind']}\n{r['body']}\n")

    last = last_muzi_time()
    quiet = int((datetime.now(timezone.utc) - datetime.fromisoformat(last.replace("Z", "+00:00"))).total_seconds() // 60) if last else None
    doing = open(STATUS).read().strip() if os.path.exists(STATUS) else "idle"
    body = f"♥ Claude @ Lenovo {datetime.now():%H:%M} | doing: {doing} | MUZI last post {quiet}m ago"
    if quiet is not None and quiet > SILENT_MIN:
        body += f" | @MUZI you've been quiet {quiet}m — status?"
    if "--no-heartbeat" not in sys.argv:
        heartbeat(body)
    print(body)

    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    json.dump(state, open(STATE, "w"))
    sys.exit(3 if new else 0)


if __name__ == "__main__":
    main()
