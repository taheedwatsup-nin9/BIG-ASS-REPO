#!/usr/bin/env python3
"""Import Lenovo Claude Code session logs into Supabase brain_memory. (v1.1, Claude 2026-10-23)

Build order: Taheed 2026-10-23 01:34 "Build them" via MUZI (brain maintenance trio + connector).
Pattern: mirrors import_hermes_v2.py v2.4.1 — one brain_memory row per session, delete-by-exact-
title then insert (idempotent), source-tagged, no hardcoded credentials, TLS on, --dry-run,
empty input = FAILURE (exit 3).

What goes in a row (source="claude_session"):
  - USER and ASSISTANT *text* only. Tool calls, tool results, thinking, images and attachments
    are dropped: tool output is where secrets and file dumps ride along (same rule as Hermes).
  - Every text passes the SECRETS FILTER before anything else touches it (see redact()).
  - Long messages are clipped; a row is capped at ROW_CAP chars (head + tail kept).
Title: "Claude session <YYYY-MM-DD> <first prompt, 60 chars> [<session id>]" — the bracketed id
is the stable key, like the Hermes rows.

Incremental: ~/.local/state/claude-sessions-import.json remembers each log's size; only new or
grown logs are re-imported. Backfill runs OLDEST FIRST (Taheed/MUZI order).
Subagent logs (deeper folders) are imported too, tagged "subagent".

Usage: import_claude_sessions.py [--dry-run] [--limit N] [--leak-check FILE]
  --leak-check FILE: a file of known-secret strings (one per line, kept outside the repo);
  the run aborts before writing if any of them survives the filter.
"""
import glob
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

PROJECTS = os.path.expanduser("~/.claude/projects")
STATE = os.path.expanduser("~/.local/state/claude-sessions-import.json")
DEFAULT_ENV_FILE = os.path.expanduser("~/.config/cr8mor/supabase.env")
KEY_NAMES = ("SUPABASE_SERVICE_KEY", "SUPABASE_SERVICE_ROLE_KEY", "SERVICE_ROLE_KEY", "SUPABASE_KEY")
MSG_CAP, ROW_CAP = 1500, 30000
SOURCE = "claude_session"

# ---------- secrets filter (runs on every text before anything else) ----------
SECRET_PATTERNS = [
    (re.compile(r"\b\d{8,10}:AA[A-Za-z0-9_-]{30,}\b"), "[REDACTED:telegram-token]"),
    (re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"), "[REDACTED:jwt]"),
    (re.compile(r"-----BEGIN [A-Z ]*KEY-----.*?-----END [A-Z ]*KEY-----", re.S), "[REDACTED:pem]"),
    (re.compile(r"\b(sk|rk|pk)-[A-Za-z0-9_-]{16,}"), "[REDACTED:api-key]"),
    (re.compile(r"\b(ghp|gho|ghu|ghs|github_pat)_[A-Za-z0-9_]{20,}"), "[REDACTED:github-token]"),
    (re.compile(r"\bAIza[0-9A-Za-z_-]{30,}"), "[REDACTED:google-key]"),
    (re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"), "[REDACTED:slack-token]"),
    (re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{16,}"), "Bearer [REDACTED]"),
    (re.compile(r"(?i)\b([A-Z0-9_]*(?:KEY|SECRET|TOKEN|PASSWORD|PASS|PIN)[A-Z0-9_]*)\s*[=:]\s*[\"']?[^\s\"']{4,}"),
     r"\1=[REDACTED]"),
    (re.compile(r"(?i)\b(pin|passcode|password)\b[^\n]{0,20}?\b\d{4,8}\b"), r"\1 [REDACTED]"),
    (re.compile(r"SEALED #\d+\s+[A-Za-z0-9+/=]{40,}"), "SEALED [REDACTED:ciphertext]"),
    (re.compile(r"\b[A-Za-z0-9+/_-]{40,}={0,2}"), "[REDACTED:long-token]"),
]


def redact(text):
    hits = 0
    for rx, rep in SECRET_PATTERNS:
        text, n = rx.subn(rep, text)
        hits += n
    return text, hits


# ---------- config (same contract as import_hermes_v2) ----------
def load_env_file(path):
    vals = {}
    try:
        for line in open(path):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                vals[k.strip().removeprefix("export ").strip()] = v.strip().strip('"').strip("'")
    except FileNotFoundError:
        pass
    return vals


def resolve_config():
    merged = load_env_file(os.environ.get("CR8MOR_ENV_FILE", DEFAULT_ENV_FILE))
    merged.update({k: v for k, v in os.environ.items() if v})
    key = next((merged[k] for k in KEY_NAMES if merged.get(k)), None)
    return merged.get("SUPABASE_URL"), key


# ---------- parsing ----------
def texts(content):
    if isinstance(content, str):
        return [content]
    out = []
    for block in content or []:
        if isinstance(block, dict) and block.get("type") == "text":
            out.append(block.get("text", ""))
    return out


def digest(path):
    turns, sid, first_ts, last_ts, first_prompt, hits = [], None, None, None, None, 0
    for line in open(path, errors="ignore"):
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        sid = sid or ev.get("sessionId")
        ts = ev.get("timestamp")
        if ts:
            first_ts = first_ts or ts
            last_ts = ts
        role = ev.get("type")
        if role not in ("user", "assistant") or ev.get("isMeta"):
            continue
        for t in texts((ev.get("message") or {}).get("content")):
            t = t.strip()
            if not t or t.startswith("<") and ("system-reminder" in t[:40] or "command-" in t[:40]):
                continue
            if re.fullmatch(r"\d{4,8}", t):      # a bare number sent on its own is how a PIN arrives
                t, n = "[REDACTED:bare-number]", 1
            else:
                t, n = redact(t)
            hits += n
            if len(t) > MSG_CAP:
                t = t[:MSG_CAP] + " …[clipped]"
            if role == "user" and first_prompt is None:
                first_prompt = re.sub(r"\s+", " ", t)[:60]
            turns.append(f"**{'Taheed' if role == 'user' else 'Claude'}:** {t}")
    # Key on the log FILE name: subagent logs share their parent's sessionId, so sessionId alone
    # collides (v1.0 bug: 5 writes collapsed into 1 row).
    return turns, os.path.basename(path)[:-6], first_ts, last_ts, first_prompt or "(no prompt)", hits


def build_row(path):
    turns, sid, first_ts, last_ts, first_prompt, hits = digest(path)
    if not turns:
        return None
    day = (first_ts or "")[:10] or datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d")
    sub = "/subagents/" in path or os.path.dirname(os.path.dirname(path)) != PROJECTS
    body = "\n\n".join(turns)
    if len(body) > ROW_CAP:
        body = body[:ROW_CAP * 2 // 3] + "\n\n…[middle of session clipped]…\n\n" + body[-ROW_CAP // 3:]
    header = (f"Claude Code session on the Lenovo. Project dir: {os.path.basename(os.path.dirname(path))}. "
              f"From {first_ts} to {last_ts}. {len(turns)} text turns kept; tool calls/results dropped; "
              f"{hits} secret-shaped strings redacted.\n\n")
    title = f"Claude session {day} {re.sub(r'[\\[\\]]', '', first_prompt)} [{sid}]"
    tags = ["claude", "session", "lenovo"] + (["subagent"] if sub else [])
    return {"source": SOURCE, "title": title[:250], "content": header + body, "tags": tags}, hits


def upsert(url, key, row):
    h = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json",
         "Prefer": "return=minimal"}
    q = f"{url}/rest/v1/brain_memory?title=eq.{urllib.parse.quote(row['title'])}&source=eq.{SOURCE}"
    urllib.request.urlopen(urllib.request.Request(q, method="DELETE", headers=h), timeout=30)
    urllib.request.urlopen(urllib.request.Request(f"{url}/rest/v1/brain_memory", method="POST", headers=h,
                                                  data=json.dumps(row).encode()), timeout=30)


def main():
    dry = "--dry-run" in sys.argv
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None
    leak = []
    if "--leak-check" in sys.argv:
        leak = [l.strip() for l in open(sys.argv[sys.argv.index("--leak-check") + 1]) if l.strip()]
    logs = sorted(glob.glob(os.path.join(PROJECTS, "**", "*.jsonl"), recursive=True), key=os.path.getmtime)
    if not logs:
        print("FAIL: no session logs found")
        sys.exit(3)
    state = json.load(open(STATE)) if os.path.exists(STATE) else {}
    todo = [p for p in logs if state.get(p) != os.path.getsize(p)]
    if limit:
        todo = todo[:limit]
    url, key = resolve_config()
    if not dry and not (url and key):
        print("FAIL: Supabase URL/service key not found (env or ~/.config/cr8mor/supabase.env)")
        sys.exit(2)
    ok = skipped = failed = total_hits = 0
    for p in todo:
        built = build_row(p)
        if not built:
            skipped += 1
            state[p] = os.path.getsize(p)
            continue
        row, hits = built
        total_hits += hits
        survivors = [s for s in leak if s in row["content"] or s in row["title"]]
        if survivors:
            print(f"ABORT: {len(survivors)} known secret(s) survived the filter in {os.path.basename(p)}; nothing written")
            sys.exit(4)
        if dry:
            print(f"  [dry-run] {row['title'][:90]} ({len(row['content'])} chars, {hits} redactions)")
            ok += 1
            continue
        try:
            upsert(url, key, row)
            state[p] = os.path.getsize(p)
            ok += 1
        except urllib.error.URLError as e:
            failed += 1
            print(f"  FAILED {os.path.basename(p)}: {type(e).__name__} {getattr(e, 'code', '')}")
    if not dry:
        os.makedirs(os.path.dirname(STATE), exist_ok=True)
        json.dump(state, open(STATE, "w"))
    print(f"{'DRY-RUN ' if dry else ''}done: {ok} ok, {skipped} empty, {failed} failed, "
          f"{total_hits} redactions, {len(logs)} logs total, {len(todo)} processed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
