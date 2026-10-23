#!/usr/bin/env python3
"""embed_nomic.py — fill brain_chunks.embedding_nomic with the network-wide standard model.

Standard (Taheed 2026-10-23, ~/AGENTS.md): nomic-embed-text 768-d via the Zeabur Ollama.
Documents are prefixed "search_document: " (nomic's task prefix; queries must use "search_query: ").
Man-page chunks (titles like tor_1, sudoers_5) are skipped. Only rows whose embedding_nomic IS NULL
are written (PATCH guarded), so re-runs resume. Existing service-key path; no new credentials.
Embedding evicts dolphin3 from Ollama while it runs (MAX_LOADED_MODELS=1).
Usage: python3 embed_nomic.py [--limit N]
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

OLLAMA = "https://ollama-cr8.zeabur.app/api/embed"
MODEL = "nomic-embed-text"
PREFIX = "search_document: "
MANPAGE_RE = r"^[A-Za-z0-9._+-]+_[0-9][a-z]*$"
PAGE, BATCH, STREAMS = 256, 32, 2


def config():
    env = {k: v for k, v in os.environ.items() if k.startswith("SUPABASE")}
    for line in open(os.path.expanduser("~/.config/cr8mor/supabase.env")):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.replace("export ", "").strip()] = v.strip().strip('"').strip("'")
    return env["SUPABASE_URL"].rstrip("/"), env["SUPABASE_SERVICE_ROLE_KEY"]


URL, KEY = config()
HDR = {"apikey": KEY, "Authorization": f"Bearer {KEY}", "Content-Type": "application/json",
       "Prefer": "return=minimal"}


def http(url, data=None, method=None, headers=None, timeout=300):
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    return urllib.request.urlopen(req, timeout=timeout).read()


def fetch(after_id):
    q = (f"{URL}/rest/v1/brain_chunks?select=id,content&embedding_nomic=is.null&id=gt.{after_id}"
         f"&title=not.match.{urllib.parse.quote(MANPAGE_RE)}&order=id.asc&limit={PAGE}")
    return json.loads(http(q, headers=HDR, timeout=60))


def embed_and_write(rows):
    texts = [PREFIX + (r["content"] or " ") for r in rows]
    for attempt in range(4):
        try:
            vecs = json.loads(http(OLLAMA, json.dumps({"model": MODEL, "input": texts}).encode(),
                                   headers={"Content-Type": "application/json"}))["embeddings"]
            break
        except Exception:
            time.sleep(10 * (attempt + 1))
    else:
        return 0, len(rows)
    ok = bad = 0
    for r, v in zip(rows, vecs):
        try:
            http(f"{URL}/rest/v1/brain_chunks?id=eq.{r['id']}&embedding_nomic=is.null",
                 json.dumps({"embedding_nomic": v}).encode(), "PATCH", HDR, 60)
            ok += 1
        except Exception:
            bad += 1
    return ok, bad


def main():
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None
    done = failed = after = 0
    t0 = time.time()
    with ThreadPoolExecutor(STREAMS) as pool:
        while True:
            rows = fetch(after)
            if not rows:
                break
            after = rows[-1]["id"]
            for ok, bad in pool.map(embed_and_write, [rows[i:i + BATCH] for i in range(0, len(rows), BATCH)]):
                done += ok
                failed += bad
            print(f"{time.strftime('%H:%M:%S')} embedded {done} failed {failed} "
                  f"({done / max(time.time() - t0, 1):.1f}/s) last id {after}", flush=True)
            if limit and done >= limit:
                break
    print(f"DONE embedded {done} failed {failed} in {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
