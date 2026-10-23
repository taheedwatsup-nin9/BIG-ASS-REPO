#!/usr/bin/env python3
"""
sheet_watcher.py — daemon that runs experiment rows from the Google Sheet "CR8 Experiment Runs".

Light check, no inbound port: every POLL_S seconds it asks Drive for the sheet's
modifiedTime (one tiny request). Only when that changes does it read the Runs tab.
A row whose Deploy box is ticked is queued and run through run.sh, one at a time
(one speaker chain), then the row gets Status / Last run / Result and Deploy is unticked.
Every run is also logged in run_log_lenovo.csv (by run.sh) and the sheet's Log tab.

Auth: borrows the OAuth token rclone keeps for remote "gdrive:" (scope=drive, which the
Sheets API accepts). The token is read at runtime and never printed or written anywhere.
When it is near expiry, a cheap rclone call makes rclone refresh it.

Usage: sheet_watcher.py            (daemon)
       sheet_watcher.py --create   (build the sheet once, print its URL)
"""

import configparser
import csv
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
STIM_DIR = os.path.normpath(os.path.join(HERE, "..", "..", "stimuli"))
STATE = os.path.expanduser("~/.local/state/cr8-sheet-watcher.json")
RCLONE_CONF = os.path.expanduser("~/.config/rclone/rclone.conf")
POLL_S = 5
MAX_CEILING = 0.8          # hard safety cap: no row can drive the Lenovo output above this
TAB = "Runs"
COLS = ["Row", "Experiment", "Stimulus", "Ceiling (stepped)", "Ceiling (fine ±)", "Ramp s",
        "Rate", "Hypothesis / thoughts / questions", "Deploy", "Status", "Last run", "Result file"]
STEPPED = [f"{v/10:.1f}" for v in range(1, 9)]                    # 0.1 … 0.8
FINE = [f"{v/100:+.2f}" for v in range(-5, 6)]                    # -0.05 … +0.05
RAMPS = ["5", "10", "15", "20", "30"]
RATES = ["native", "44100", "48000", "96000"]
EXPERIMENTS = ["test-tone", "exp1", "exp2", "exp3", "exp8"]


def log(msg):
    print(f"{datetime.now():%F %T} {msg}", flush=True)


# ---------- auth (rclone's token, never printed) ----------
def token():
    for attempt in (0, 1):
        cp = configparser.ConfigParser()
        cp.read(RCLONE_CONF)
        tok = json.loads(cp["gdrive"]["token"])
        # rclone writes nanoseconds (e.g. 2026-10-22T23:45:12.123456789-07:00); drop the fraction
        exp = datetime.fromisoformat(re.sub(r"\.\d+", "", tok["expiry"]).replace("Z", "+00:00"))
        if (exp - datetime.now(timezone.utc)).total_seconds() > 120:
            return tok["access_token"]
        # near expiry: any rclone call against gdrive refreshes and rewrites the config
        subprocess.run(["rclone", "lsf", "gdrive:", "--max-depth", "1", "--dirs-only"],
                       capture_output=True, timeout=60)
    raise RuntimeError("could not refresh rclone gdrive token")


def api(method, url, body=None):
    req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body else None,
                                 headers={"Authorization": f"Bearer {token()}",
                                          "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read() or b"{}")


SHEETS = "https://sheets.googleapis.com/v4/spreadsheets"


def get_values(sid, rng):
    return api("GET", f"{SHEETS}/{sid}/values/{urllib.request.quote(rng)}").get("values", [])


def put_values(sid, rng, rows):
    api("PUT", f"{SHEETS}/{sid}/values/{urllib.request.quote(rng)}?valueInputOption=USER_ENTERED",
        {"values": rows})


def append_values(sid, rng, rows):
    api("POST", f"{SHEETS}/{sid}/values/{urllib.request.quote(rng)}:append?valueInputOption=USER_ENTERED",
        {"values": rows})


def modified_time(sid):
    return api("GET", f"https://www.googleapis.com/drive/v3/files/{sid}?fields=modifiedTime")["modifiedTime"]


# ---------- sheet creation ----------
def stimuli():
    return sorted(f for f in os.listdir(STIM_DIR) if f.endswith(".wav")) + ["test_tone_1k_5s.wav"]


def create():
    body = {"properties": {"title": "CR8 Experiment Runs"},
            "sheets": [{"properties": {"title": TAB, "gridProperties": {"frozenRowCount": 1}}},
                       {"properties": {"title": "Log", "gridProperties": {"frozenRowCount": 1}}},
                       {"properties": {"title": "Lists"}}]}
    ss = api("POST", SHEETS, body)
    sid = ss["spreadsheetId"]
    runs_id, _, lists_id = (s["properties"]["sheetId"] for s in ss["sheets"])
    lists = [EXPERIMENTS, stimuli(), STEPPED, FINE, RAMPS, RATES]
    width = max(map(len, lists))
    put_values(sid, "Lists!A1", [[l[i] if i < len(l) else "" for l in lists] for i in range(width)])
    put_values(sid, f"{TAB}!A1", [COLS] + [[str(i), "test-tone", "test_tone_1k_5s.wav", "0.3", "+0.00", "10",
                                            "native", "", False, "", "", ""] for i in range(1, 2)]
               + [[str(i), "", "", "", "+0.00", "10", "native", "", False, "", "", ""] for i in range(2, 21)])
    put_values(sid, "Log!A1", [["Time", "Row", "Experiment", "Stimulus", "Ceiling", "Ramp", "Rate",
                                "Hypothesis", "Outcome", "Result file"]])

    def dropdown(col, list_col, n):
        return {"setDataValidation": {
            "range": {"sheetId": runs_id, "startRowIndex": 1, "endRowIndex": 21,
                      "startColumnIndex": col, "endColumnIndex": col + 1},
            "rule": {"condition": {"type": "ONE_OF_RANGE",
                                   "values": [{"userEnteredValue": f"=Lists!${list_col}$1:${list_col}${n}"}]},
                     "strict": True, "showCustomUi": True}}}
    reqs = [dropdown(1, "A", len(EXPERIMENTS)), dropdown(2, "B", len(stimuli())),
            dropdown(3, "C", len(STEPPED)), dropdown(4, "D", len(FINE)),
            dropdown(5, "E", len(RAMPS)), dropdown(6, "F", len(RATES)),
            {"setDataValidation": {"range": {"sheetId": runs_id, "startRowIndex": 1, "endRowIndex": 21,
                                             "startColumnIndex": 8, "endColumnIndex": 9},
                                   "rule": {"condition": {"type": "BOOLEAN"}}}},
            {"repeatCell": {"range": {"sheetId": runs_id, "startRowIndex": 0, "endRowIndex": 1},
                            "cell": {"userEnteredFormat": {"textFormat": {"bold": True}}},
                            "fields": "userEnteredFormat.textFormat.bold"}},
            {"updateDimensionProperties": {"range": {"sheetId": runs_id, "dimension": "COLUMNS",
                                                     "startIndex": 7, "endIndex": 8},
                                           "properties": {"pixelSize": 320}, "fields": "pixelSize"}},
            {"updateSheetProperties": {"properties": {"sheetId": lists_id, "hidden": True},
                                       "fields": "hidden"}}]
    api("POST", f"{SHEETS}/{sid}:batchUpdate", {"requests": reqs})
    return sid


# ---------- running ----------
def file_rate(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=sample_rate", "-of", "csv=p=0", path],
                         capture_output=True, text=True).stdout.strip()
    return out or "48000"


def run_row(sid, n, r):
    r = (r + [""] * len(COLS))[:len(COLS)]
    _, exp, stim, step, fine, ramp, rate, note = r[:8]
    path = os.path.join(HERE if stim == "test_tone_1k_5s.wav" else STIM_DIR, stim)
    try:
        ceiling = round(float(step) + float(fine or 0), 3)
    except ValueError:
        ceiling = -1
    if not exp or not os.path.isfile(path) or not 0 < ceiling <= MAX_CEILING:
        why = f"BLOCKED: ceiling {ceiling} outside 0-{MAX_CEILING}" if os.path.isfile(path) else "BLOCKED: pick experiment + stimulus"
        put_values(sid, f"{TAB}!I{n}:J{n}", [[False, why]])
        return
    rate = file_rate(path) if rate in ("", "native") else rate
    put_values(sid, f"{TAB}!J{n}:K{n}", [["RUNNING", datetime.now().strftime("%F %T")]])
    log(f"row {n}: {exp} {stim} ceiling={ceiling} ramp={ramp} rate={rate}")
    env = dict(os.environ, NOTE=note.replace(",", ";").replace("\n", " "))
    p = subprocess.run([os.path.join(HERE, "run.sh"), f"{exp}-row{n}", path, str(ceiling), rate, ramp or "10"],
                       capture_output=True, text=True, env=env, timeout=600)
    out = p.stdout + p.stderr
    res = next((l.split("=", 1)[1] for l in out.splitlines() if l.startswith("RESULT_FILE=")), "")
    outcome = "DONE" if p.returncode == 0 and res else "FAILED: " + (out.strip().splitlines() or ["?"])[-1][:120]
    put_values(sid, f"{TAB}!I{n}:L{n}", [[False, outcome, datetime.now().strftime("%F %T"), os.path.basename(res)]])
    append_values(sid, "Log!A1", [[datetime.now().strftime("%F %T"), n, exp, stim, ceiling, ramp, rate, note,
                                   outcome, os.path.basename(res)]])
    log(f"row {n}: {outcome}")


def main():
    if "--create" in sys.argv:
        sid = create()
        os.makedirs(os.path.dirname(STATE), exist_ok=True)
        json.dump({"sheet_id": sid}, open(STATE, "w"))
        print(f"https://docs.google.com/spreadsheets/d/{sid}/edit")
        return
    sid = json.load(open(STATE))["sheet_id"]
    log(f"watching sheet {sid} every {POLL_S}s (cap {MAX_CEILING})")
    last = None
    while True:
        try:
            m = modified_time(sid)
            if m != last:
                rows = get_values(sid, f"{TAB}!A2:L21")
                for i, r in enumerate(rows, start=2):
                    if len(r) > 8 and r[8].upper() == "TRUE" and (len(r) < 10 or r[9] != "RUNNING"):
                        run_row(sid, i, r)
                last = modified_time(sid)   # absorb our own status writes
        except (urllib.error.URLError, RuntimeError, KeyError, ValueError) as e:
            log(f"check failed: {type(e).__name__}: {str(e)[:120]}")
            time.sleep(30)
        time.sleep(POLL_S)


if __name__ == "__main__":
    main()
