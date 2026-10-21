#!/usr/bin/env python3
"""Import Hermes data into Supabase brain_memory table. (v2.3, MUZI 2026-10-21)

What this syncs:
1) The 5 core/config files from the real Hermes home.
2) ANSWERED conversations from ~/.hermes/state.db (v2.3): one
   brain_memory row per session that has at least one assistant
   reply, keyed on the full sessions.id (embedded in the title).
   - 22 of 47 surveyed sessions have a user turn and NO reply —
     failed provider calls. They are skipped, like the dumps.
   - Tool-role messages are EXCLUDED from the transcript (they are
     half the bytes and the likeliest place for a secret to ride
     along); the row's header counts them as omitted.
   - The whole history is ~38 KB, so a full rebuild each run is
     fine; no incremental logic yet. message_uid is populated on
     100% of messages if a per-message design is ever needed.

What it NEVER syncs: sessions/request_dump_*.json. Claude's inspection
of the actual files (2026-10-21) showed all 23 are API ERROR dumps —
{error, reason, request, session_id, timestamp} from failed provider
calls — carrying request headers and full prompt bodies. They are
failure logs, not conversation history.

v2.1 fix (ground truth traced on the Lenovo via Claude, 2026-10-21):
v1/v2 read HERMES_DIR=/tmp/hermes_data, a staging folder that NOTHING
on the machine ever wrote to — it does not even exist. Every nightly
hermes-sync run since the journal begins (2026-09-17) imported 0 rows
and still exited as success. v2.1+ reads the sources from their real
homes: ~/.hermes (a symlink to ~/Documents/Agent_Workspaces/hermes).
gemini_brain_digest.md exists nowhere; it stays an optional skip.
An empty input set is a FAILURE (exit 3), never a silent success.

v2 changes (kept):
- NO hardcoded credentials. The Supabase service key is read from the
  environment (the hermes-sync unit already loads
  ~/.config/cr8mor/supabase.env via EnvironmentFile) or by parsing
  that env file directly. The script FAILS LOUDLY if no key is found.
- TLS certificate verification is ON (v1 disabled it).
- A failed delete no longer gets silently swallowed before the
  insert; the row is counted failed and skipped.
- --dry-run walks everything and prints what WOULD be written (titles
  and sizes only, never transcript content), with no network calls
  and no key required.
"""
import json
import os
import glob
import sqlite3
import sys
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime

# Real Hermes home; os.path.realpath resolves the ~/.hermes symlink.
HERMES_HOME = os.path.realpath(os.path.expanduser("~/.hermes"))
STATE_DB = os.path.join(HERMES_HOME, "state.db")
DEFAULT_ENV_FILE = os.path.expanduser("~/.config/cr8mor/supabase.env")
DEFAULT_URL = "https://dgxabvxwiqrzzdmwdxha.supabase.co"
KEY_NAMES = ("SUPABASE_SERVICE_KEY", "SUPABASE_SERVICE_ROLE_KEY",
             "SERVICE_ROLE_KEY", "SUPABASE_KEY")
URL_NAMES = ("SUPABASE_URL",)


def load_env_file(path):
    vals = {}
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                vals[k.strip()] = v.strip().strip('"').strip("'")
    except FileNotFoundError:
        pass
    return vals


def resolve_config():
    file_vals = load_env_file(os.environ.get("CR8MOR_ENV_FILE", DEFAULT_ENV_FILE))
    merged = dict(file_vals)
    merged.update({k: v for k, v in os.environ.items() if v})
    key = next((merged[n] for n in KEY_NAMES if merged.get(n)), None)
    url = next((merged[n] for n in URL_NAMES if merged.get(n)), DEFAULT_URL)
    return url.rstrip("/"), key


SUPABASE_URL, SUPABASE_SERVICE_KEY = resolve_config()
DRY_RUN = "--dry-run" in sys.argv


def upsert_to_supabase(source, title, content, tags):
    """Delete-by-exact-title then insert. Titles are unique by
    construction, so this is collision-safe without any schema change.
    (If the optional unique index from brain_memory_unique_title.sql
    is applied, this stays compatible.)"""
    if DRY_RUN:
        print(f"  [dry-run] would write: {title} ({len(content)} chars, source={source})")
        return
    headers = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }
    del_url = f"{SUPABASE_URL}/rest/v1/brain_memory?title=eq.{urllib.parse.quote(title)}"
    del_req = urllib.request.Request(del_url, headers=headers, method="DELETE")
    urllib.request.urlopen(del_req, timeout=10)  # raises on error: caller counts it failed
    record = {"source": source, "title": title, "content": content, "tags": tags}
    ins_req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/brain_memory",
        data=json.dumps(record).encode(),
        headers=headers,
        method="POST")
    urllib.request.urlopen(ins_req, timeout=15)


def import_files(file_map, section_label):
    """file_map: relpath under HERMES_HOME -> (source, title, tags).
    Returns (success, failed, inputs_found)."""
    success = failed = found = 0
    print(section_label)
    for relpath, (source, title, tags) in file_map.items():
        fpath = os.path.join(HERMES_HOME, relpath)
        if not os.path.exists(fpath):
            print(f"  skip {relpath} (not found)")
            continue
        found += 1
        try:
            with open(fpath) as f:
                content = f.read()
            upsert_to_supabase(source, title, content, tags)
            print(f"  ok {title} ({len(content)} chars)")
            success += 1
        except Exception as e:
            print(f"  FAIL {relpath}: {e}")
            failed += 1
    return success, failed, found


def sync_state_db():
    """One brain row per ANSWERED session in state.db.
    Returns (success, failed, inputs_found)."""
    print("Importing Hermes conversations from state.db...")
    if not os.path.exists(STATE_DB):
        print("  skip state.db (not found)")
        return 0, 0, 0
    success = failed = found = 0
    conn = sqlite3.connect(f"file:{STATE_DB}?mode=ro", uri=True)
    try:
        sessions = conn.execute(
            "SELECT s.id, s.source, s.model, s.started_at FROM sessions s "
            "WHERE EXISTS (SELECT 1 FROM messages m "
            "              WHERE m.session_id = s.id AND m.role = 'assistant' AND m.active = 1) "
            "ORDER BY s.started_at").fetchall()
        skipped_unanswered = conn.execute(
            "SELECT COUNT(*) FROM sessions s "
            "WHERE NOT EXISTS (SELECT 1 FROM messages m "
            "                  WHERE m.session_id = s.id AND m.role = 'assistant' AND m.active = 1)"
        ).fetchone()[0]
        for session_id, sess_source, model, started_at in sessions:
            found += 1
            try:
                rows = conn.execute(
                    "SELECT role, content FROM messages "
                    "WHERE session_id = ? AND active = 1 AND role IN ('user', 'assistant') "
                    "ORDER BY timestamp, id", (session_id,)).fetchall()
                tool_count = conn.execute(
                    "SELECT COUNT(*) FROM messages "
                    "WHERE session_id = ? AND active = 1 AND role = 'tool'",
                    (session_id,)).fetchone()[0]
                started = datetime.fromtimestamp(started_at)
                title = (f"Hermes Chat: {started:%Y-%m-%d %H:%M} "
                         f"({sess_source}, {model}, {len(rows)} msgs) [{session_id}]")
                header = (f"session_id: {session_id}\nsource: {sess_source} · model: {model} · "
                          f"started: {started.isoformat()}\nmessages: {len(rows)} "
                          f"(tool outputs omitted: {tool_count})\n")
                transcript = "\n\n".join(f"[{role}] {content or ''}" for role, content in rows)
                content = header + "\n" + transcript
                tags = ["hermes", "chat", "state_db", f"source_{sess_source}"]
                upsert_to_supabase("hermes_chat", title, content, tags)
                print(f"  ok {title} ({len(content)} chars)")
                success += 1
            except Exception as e:
                print(f"  FAIL session {session_id}: {e}")
                failed += 1
    finally:
        conn.close()
    if skipped_unanswered:
        print(f"  skipped {skipped_unanswered} unanswered sessions (user turn, no reply)")
    return success, failed, found


def main():
    print("Hermes -> Supabase Brain Import (v2.3)")
    print(f"   Source: {HERMES_HOME}")
    print(f"   Timestamp: {datetime.now().isoformat()}")
    if DRY_RUN:
        print("   Mode: DRY RUN (no writes, no key needed)")
    elif not SUPABASE_SERVICE_KEY:
        print("FATAL: no Supabase service key found. Looked in the process")
        print("environment and the env file for any of: " + ", ".join(KEY_NAMES))
        print("The hermes-sync unit loads ~/.config/cr8mor/supabase.env -")
        print("put the (rotated) service-role key there under one of those names.")
        sys.exit(2)

    md_files = {
        "memories/MEMORY.md": ("hermes_memory", "Hermes: Agent Memory", ["hermes", "memory", "cr8app", "agent_knowledge"]),
        "memories/USER.md": ("hermes_user_profile", "Hermes: User Profile", ["hermes", "user", "profile", "preferences"]),
        "SOUL.md": ("hermes_soul", "Hermes: Soul/Identity Config", ["hermes", "soul", "identity", "config"]),
        "gemini_brain_digest.md": ("hermes_brain_digest", "Hermes: Gemini Brain Digest", ["hermes", "brain", "digest"]),
    }
    json_configs = {
        "gateway_state.json": ("hermes_gateway", "Hermes: Gateway State", ["hermes", "gateway", "state", "config"]),
        "channel_directory.json": ("hermes_channels", "Hermes: Channel Directory", ["hermes", "channels", "directory"]),
    }

    success = failed = inputs_found = 0
    for file_map, label in ((md_files, "Importing core Hermes files..."),
                            (json_configs, "Importing Hermes config files...")):
        s, f, n = import_files(file_map, label)
        success += s
        failed += f
        inputs_found += n

    s, f, n = sync_state_db()
    success += s
    failed += f
    inputs_found += n

    # The request dumps are API error logs, not sessions. Never imported.
    dumps = sorted(glob.glob(os.path.join(HERMES_HOME, "sessions", "request_dump_*.json")))
    if dumps:
        print(f"Skipping {len(dumps)} request_dump files in sessions/ - "
              "API error dumps, not conversation data (see docstring).")

    print("=" * 60)
    print(f"Import Complete: ok={success} failed={failed} total={success + failed} inputs={inputs_found}")
    if inputs_found == 0:
        print("WARNING: zero inputs found under " + HERMES_HOME +
              " - treating as FAILURE so an empty source can never pass as a sync.")
        sys.exit(3)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
