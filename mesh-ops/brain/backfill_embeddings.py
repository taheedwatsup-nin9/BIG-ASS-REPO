#!/usr/bin/env python3
"""backfill_embeddings.py — one-time catch-up of brain_chunks embeddings from the Lenovo.

Agreed with MUZI 2026-10-23 (option B), gated on a 20-chunk parity proof:
Supabase/gte-small onnx/model.onnx + mean-pool (attention mask) + L2-normalize reproduced the
stored edge-function vectors with cosine 1.00000 (min over 20). The quantized model did NOT
(min 0.986) and must not be used.

Only rows whose embedding IS NULL are touched (PATCH by id with an `embedding=is.null` guard, so a
row the edge function already filled is never overwritten). Writes use the existing service-key
path (~/.config/cr8mor/supabase.env + SUPABASE_URL from the environment). No new credentials.
Run inside ~/.venvs/gte:  ~/.venvs/gte/bin/python -I backfill_embeddings.py [--limit N]
"""
import json
import os
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import onnxruntime as ort
from huggingface_hub import hf_hub_download
from tokenizers import Tokenizer

PAGE = 200
WRITERS = 8


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
tok = Tokenizer.from_file(hf_hub_download("Supabase/gte-small", "tokenizer.json"))
tok.enable_truncation(512)
opts = ort.SessionOptions()
opts.intra_op_num_threads = 3            # leave a core for the desktop/audio
sess = ort.InferenceSession(hf_hub_download("Supabase/gte-small", "onnx/model.onnx"), opts,
                            providers=["CPUExecutionProvider"])
HAS_TT = "token_type_ids" in [i.name for i in sess.get_inputs()]


def embed(text):
    e = tok.encode(text)
    ids = np.array([e.ids], dtype=np.int64)
    am = np.array([e.attention_mask], dtype=np.int64)
    feeds = {"input_ids": ids, "attention_mask": am}
    if HAS_TT:
        feeds["token_type_ids"] = np.zeros_like(ids)
    h = sess.run(None, feeds)[0][0].astype(np.float64)
    v = (h * am[0][:, None]).sum(0) / am[0].sum()
    return (v / np.linalg.norm(v)).tolist()


def fetch(after_id):
    q = (f"{URL}/rest/v1/brain_chunks?select=id,content&embedding=is.null&id=gt.{after_id}"
         f"&order=id.asc&limit={PAGE}")
    return json.load(urllib.request.urlopen(urllib.request.Request(q, headers=HDR), timeout=60))


def write(row_id, vec):
    q = f"{URL}/rest/v1/brain_chunks?id=eq.{row_id}&embedding=is.null"
    body = json.dumps({"embedding": vec}).encode()
    for attempt in range(3):
        try:
            urllib.request.urlopen(urllib.request.Request(q, data=body, method="PATCH", headers=HDR), timeout=60)
            return True
        except Exception:
            time.sleep(2 * (attempt + 1))
    return False


def main():
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None
    done = failed = 0
    after = 0
    t0 = time.time()
    with ThreadPoolExecutor(WRITERS) as pool:
        while True:
            rows = fetch(after)
            if not rows:
                break
            after = rows[-1]["id"]
            futures = [pool.submit(write, r["id"], embed(r["content"] or " ")) for r in rows]
            for f in futures:
                if f.result():
                    done += 1
                else:
                    failed += 1
            rate = done / max(time.time() - t0, 1)
            print(f"{time.strftime('%H:%M:%S')} embedded {done} failed {failed} ({rate:.1f}/s) last id {after}", flush=True)
            if limit and done >= limit:
                break
    print(f"DONE embedded {done} failed {failed} in {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
