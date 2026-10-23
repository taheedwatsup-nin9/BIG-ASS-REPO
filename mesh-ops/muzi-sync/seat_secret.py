#!/usr/bin/env python3
"""seat_secret.py — decrypt MUZI's sealed handoff from the live thread into ~/.config/cr8mor/.env.

MUZI encrypts "KEY=value" lines with the Lenovo's public key (RSA-OAEP-SHA256) and posts
"SEALED #2 <base64>" on the board. Only the Lenovo's private key (~/.config/cr8mor/handoff_key.pem,
mode 600) can open it. Values are written to .env (600) and NEVER printed; only key names are.
Usage: seat_secret.py            (reads MUZI's newest SEALED post from the live thread)
"""
import base64, json, os, re, subprocess, urllib.request
ENV = os.path.expanduser("~/.config/cr8mor/.env")
KEY = os.path.expanduser("~/.config/cr8mor/handoff_key.pem")
html = urllib.request.urlopen("https://bac-live-thread.zeabur.app/", timeout=15).read().decode()
anon = re.search(r'SUPABASE_ANON_KEY\s*=\s*"([^"]+)"', html).group(1)
q = ("https://dgxabvxwiqrzzdmwdxha.supabase.co/rest/v1/bac_messages?select=created_at,body"
     "&author=eq.MUZI&body=like.*SEALED*&order=created_at.desc&limit=20")
rows = json.load(urllib.request.urlopen(urllib.request.Request(q, headers={"apikey": anon, "Authorization": "Bearer " + anon}), timeout=15))
# Posts that merely MENTION "SEALED #2" exist too; take the newest real ciphertext (>= 400 base64 chars).
found = None
for r in rows:
    for m in re.finditer(r"SEALED #2\s+([A-Za-z0-9+/=\s]+)", r["body"]):
        b = re.sub(r"\s", "", m.group(1))
        if len(b) >= 400:
            found = (r, b); break
    if found:
        break
if not found:
    raise SystemExit("no full SEALED #2 ciphertext from MUZI yet")
rows = [found[0]]
ct = base64.b64decode(found[1])
pt = subprocess.run(["openssl", "pkeyutl", "-decrypt", "-inkey", KEY, "-pkeyopt", "rsa_padding_mode:oaep",
                     "-pkeyopt", "rsa_oaep_md:sha256"], input=ct, capture_output=True, check=True).stdout.decode()
new = {k.strip(): v.strip() for k, v in (l.split("=", 1) for l in pt.splitlines() if "=" in l)}
lines = open(ENV).read().splitlines()
seen = set()
for i, l in enumerate(lines):
    k = l.split("=", 1)[0].strip()
    if k in new:
        lines[i] = f"{k}={new[k]}"; seen.add(k)
lines += [f"{k}={v}" for k, v in new.items() if k not in seen]
old = os.umask(0o077)
open(ENV, "w").write("\n".join(lines) + "\n")
os.umask(old); os.chmod(ENV, 0o600)
print("seated:", ", ".join(sorted(new)), "(values not shown) from post", rows[0]["created_at"][:16])
