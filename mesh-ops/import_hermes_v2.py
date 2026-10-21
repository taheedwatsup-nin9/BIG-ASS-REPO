#!/usr/bin/env python3
"""Import Hermes data into Supabase brain_memory table. (v2.1, MUZI 2026-10-21)

v2.1 fix (ground truth traced on the Lenovo via Claude, 2026-10-21):
v1/v2 read HERMES_DIR=/tmp/hermes_data, a staging folder that NOTHING on
the machine ever wrote to — it does not even exist. Every nightly
hermes-sync run since the journal begins (2026-09-17) imported 0 rows
and still exited as success. The staging step only ever happened by
hand, once, in the Antigravity scratch session the script was born in.
v2.1 reads the sources from their real homes instead:
  ~/.hermes (a symlink to ~/Documents/Agent_Workspaces/hermes):
    memories/MEMORY.md, memories/USER.md, SOUL.md,
    gateway_state.json, channel_directory.json,
    sessions/request_dump_*.json
  gemini_brain_digest.md exists nowhere; it stays an optional skip.
And an empty input set is a FAILURE (exit 3), never a silent success.

v2 changes (kept):
- NO hardcoded credentials. The Supabase service key is read from the
  environment (the hermes-sync unit already loads
  ~/.config/cr8mor/supabase.env via EnvironmentFile) or by parsing that
  env file directly. The script FAILS LOUDLY if no key is found.
- TLS certificate verification is ON (v1 disabled it).
- Session dump titles carry the time + a short content hash, so two
  same-day dumps can no longer silently overwrite each other (v1 keyed
  titles by date only).
- A failed delete no longer gets silently swallowed before the insert;
  the row is counted failed and skipped.
- --dry-run walks everything and prints what WOULD be written, with no
  network calls and no key required.
"""
import hashlib
import json
import os
import glob
import sys
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime

# Real Hermes home; os.path.realpath resolves the ~/.hermes symlink.
HERMES_HOME = os.path.realpath(os.path.expanduser("~/.hermes"))
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


def session_title(basename, data, content_str):
    parts = basename.replace("request_dump_", "").replace(".json", "").split("_")
    date_str = parts[0] if parts and parts[0] else "unknown"
    time_str = parts[1] if len(parts) > 1 and parts[1] else "000000"
    model = data.get("model", "unknown") if isinstance(data, dict) else "unknown"
    messages = data.get("messages", []) if isinstance(data, dict) else []
    sha8 = hashlib.sha256(content_str.encode()).hexdigest()[:8]
    return f"Hermes Session: {date_str} {time_str} ({len(messages)} msgs, {model}) [{sha8}]"


def main():
    print("Hermes -> Supabase Brain Import (v2.1)")
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

    success = 0
    failed = 0
    inputs_found = 0

    # relpath under HERMES_HOME -> (source, title, tags)
    md_files = {
        "memories/MEMORY.md": ("hermes_memory", "Hermes: Agent Memory", ["hermes", "memory", "cr8app", "agent_knowledge"]),
        "memories/USER.md": ("hermes_user_profile", "Hermes: User Profile", ["hermes", "user", "profile", "preferences"]),
        "SOUL.md": ("hermes_soul", "Hermes: Soul/Identity Config", ["hermes", "soul", "identity", "config"]),
        "gemini_brain_digest.md": ("hermes_brain_digest", "Hermes: Gemini Brain Digest", ["hermes", "brain", "digest"]),
    }
    print("Importing core Hermes files...")
    for relpath, (source, title, tags) in md_files.items():
        fpath = os.path.join(HERMES_HOME, relpath)
        if not os.path.exists(fpath):
            print(f"  skip {relpath} (not found)")
            continue
        inputs_found += 1
        try:
            with open(fpath) as f:
                content = f.read()
            upsert_to_supabase(source, title, content, tags)
            print(f"  ok {title} ({len(content)} chars)")
            success += 1
        except Exception as e:
            print(f"  FAIL {relpath}: {e}")
            failed += 1

    json_configs = {
        "gateway_state.json": ("hermes_gateway", "Hermes: Gateway State", ["hermes", "gateway", "state", "config"]),
        "channel_directory.json": ("hermes_channels", "Hermes: Channel Directory", ["hermes", "channels", "directory"]),
    }
    print("Importing Hermes config files...")
    for relpath, (source, title, tags) in json_configs.items():
        fpath = os.path.join(HERMES_HOME, relpath)
        if not os.path.exists(fpath):
            print(f"  skip {relpath} (not found)")
            continue
        inputs_found += 1
        try:
            with open(fpath) as f:
                content = f.read()
            upsert_to_supabase(source, title, content, tags)
            print(f"  ok {title} ({len(content)} chars)")
            success += 1
        except Exception as e:
            print(f"  FAIL {relpath}: {e}")
            failed += 1

    session_files = sorted(glob.glob(os.path.join(HERMES_HOME, "sessions", "request_dump_*.json")))
    print(f"Importing {len(session_files)} Hermes session dumps...")
    for fpath in session_files:
        basename = os.path.basename(fpath)
        inputs_found += 1
        try:
            with open(fpath) as f:
                data = json.load(f)
            content_str = json.dumps(data, indent=None)
            title = session_title(basename, data, content_str)
            date_str = basename.replace("request_dump_", "").split("_")[0]
            tags = ["hermes", "session", "request_dump", f"date_{date_str}"]
            upsert_to_supabase("hermes_session", title, content_str, tags)
            print(f"  ok {basename} ({len(content_str) / 1024:.0f}KB)")
            success += 1
        except Exception as e:
            print(f"  FAIL {basename}: {e}")
            failed += 1

    print("=" * 60)
    print(f"Import Complete: ok={success} failed={failed} total={success + failed} inputs={inputs_found}")
    if inputs_found == 0:
        print("WARNING: zero inputs found under " + HERMES_HOME +
              " - treating as FAILURE so an empty source can never pass as a sync.")
        sys.exit(3)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
