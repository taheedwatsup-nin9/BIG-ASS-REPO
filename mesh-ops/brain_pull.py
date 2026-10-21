#!/usr/bin/env python3
"""Pull from the shared brain (Supabase brain_memory). MUZI 2026-10-21.

The read half of Phase 2 (the write half is import_hermes_v2.py).
Any agent on a machine that holds a brain key in its env can run this
on session start (and hourly) to load shared context:

    python3 brain_pull.py                      # digest of the newest rows
    python3 brain_pull.py --source hermes_chat # only Hermes conversations
    python3 brain_pull.py --tag cr8app         # only rows with a tag
    python3 brain_pull.py --search "caller"    # title/content search
    python3 brain_pull.py --titles-only        # inventory, no content

Key handling matches the sync: the key is read from the environment
or from ~/.config/cr8mor/supabase.env — never hardcoded, never
printed. Reads use whichever key the env provides; on the Lenovo
that is the service key, so RLS is bypassed there. Agents elsewhere
need a key with SELECT on brain_memory (scoped read keys are the
sb_secret migration job).

Output is a plain-text digest sized for an agent's context window:
title, source, and content truncated per row (--max-chars).
"""
import argparse
import json
import os
import sys
import urllib.request
import urllib.parse

DEFAULT_ENV_FILE = os.path.expanduser("~/.config/cr8mor/supabase.env")
DEFAULT_URL = "https://dgxabvxwiqrzzdmwdxha.supabase.co"
KEY_NAMES = ("SUPABASE_SERVICE_KEY", "SUPABASE_SERVICE_ROLE_KEY",
             "SERVICE_ROLE_KEY", "SUPABASE_KEY",
             "SUPABASE_ANON_KEY")  # anon last: works only if RLS allows reads
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


def main():
    ap = argparse.ArgumentParser(description="Pull shared-brain context from brain_memory.")
    ap.add_argument("--source", help="only rows with this source (e.g. hermes_chat)")
    ap.add_argument("--tag", help="only rows carrying this tag")
    ap.add_argument("--search", help="case-insensitive search over title and content")
    ap.add_argument("--limit", type=int, default=20, help="max rows (default 20)")
    ap.add_argument("--max-chars", type=int, default=1200,
                    help="content chars per row in the digest (default 1200)")
    ap.add_argument("--titles-only", action="store_true",
                    help="print title/source/size only, no content")
    args = ap.parse_args()

    url, key = resolve_config()
    if not key:
        print("FATAL: no Supabase key found in the environment or " + DEFAULT_ENV_FILE,
              file=sys.stderr)
        sys.exit(2)

    params = {"select": "source,title,content,tags", "order": "id.desc",
              "limit": str(args.limit)}
    if args.source:
        params["source"] = f"eq.{args.source}"
    if args.search:
        q = urllib.parse.quote(f"*{args.search}*")
        params["or"] = f"(title.ilike.{q},content.ilike.{q})"
    endpoint = f"{url}/rest/v1/brain_memory?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(endpoint, headers={
        "apikey": key, "Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        rows = json.load(resp)

    if args.tag:
        rows = [r for r in rows if args.tag in (r.get("tags") or [])]

    if not rows:
        print("(brain pull: no rows matched)")
        return
    for r in rows:
        content = r.get("content") or ""
        if args.titles_only:
            print(f"- [{r.get('source')}] {r.get('title')} ({len(content)} chars)")
        else:
            body = content if len(content) <= args.max_chars else \
                content[:args.max_chars] + f"\n…[truncated, {len(content)} chars total]"
            print(f"## [{r.get('source')}] {r.get('title')}\n{body}\n")
    print(f"(brain pull: {len(rows)} rows)")


if __name__ == "__main__":
    main()
