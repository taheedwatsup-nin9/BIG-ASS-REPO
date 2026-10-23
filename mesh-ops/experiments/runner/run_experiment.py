#!/usr/bin/env python3
"""
run_experiment.py — Mac-side stimulus runner for the intermodulation
experiments (Taheed / CR8MOR). Runs on the MacBook under macOS.

What it does:
  - Verifies every stimulus file against SHA256SUMS.txt before playing
    anything (a corrupted transfer never reaches the monitors).
  - Plays an experiment's files in protocol order through the Mac's
    selected audio output using the built-in `afplay` (96 kHz WAVs play
    natively; set the interface to 96 kHz in Audio MIDI Setup first).
  - Appends one row per playback to run_log.csv (timestamp, experiment,
    file, sha256 prefix) so results pair with phone recordings later.

Usage:
  python3 run_experiment.py exp1            # 7 calibration tones, 5 s each
  python3 run_experiment.py exp2            # control f1, control f2, test pair
  python3 run_experiment.py exp3            # 30 s burst loop
  python3 run_experiment.py exp8-premix     # 20 s folded premix render
  python3 run_experiment.py --verify-only   # checksums only, no playback

Playback level discipline: monitor/interface gain is set ONCE in the room
(Experiment 1 fixes it at the normal working level) — this script never
changes system volume.

ENVIRONMENT RULE (Taheed, 2026-10-22 — binding for every run):
  1. The microphone/recording chain goes LIVE before any signal plays.
  2. The fader starts at the BOTTOM (off) for every run.
  3. Level rises GRADUALLY — this script plays a 10-second ramp prelude
     (first stimulus, faded in from silence) before every sequence while
     the operator watches the room mic's return.
  4. The measured output in the real room is ground truth, not the file's
     dBFS. Abort the run on feedback, squeal, or unexpected audible
     content.

Author: MUZI, 2026-10-22.
"""

import csv
import hashlib
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
STIMULI = os.path.join(HERE, "..", "stimuli")
LOG = os.path.join(HERE, "run_log.csv")

SEQUENCES = {
    "exp1": [f"exp1_tone_{f}.wav" for f in
             (24000, 26000, 28000, 30000, 32000, 34000, 36000)],
    "exp2": ["exp2_ctrl_f1_28000.wav", "exp2_ctrl_f2_31000.wav",
             "exp2_test_28000_31000.wav"],
    "exp3": ["exp3_burst_loop_30s.wav"],
    "exp8-premix": ["exp8_premix.wav"],
}
GAP_BETWEEN_FILES_S = 3  # operator repositioning / phone-app screenshot time


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_manifest():
    manifest = {}
    with open(os.path.join(STIMULI, "SHA256SUMS.txt")) as f:
        for line in f:
            line = line.strip()
            if line:
                digest, name = line.split(None, 1)
                manifest[name.lstrip("*")] = digest
    return manifest


def verify(files, manifest):
    ok = True
    for name in files:
        path = os.path.join(STIMULI, name)
        if not os.path.exists(path):
            print(f"MISSING  {name}")
            ok = False
        elif manifest.get(name) != sha256_of(path):
            print(f"BAD SUM  {name}")
            ok = False
        else:
            print(f"ok       {name}")
    return ok


def log_run(exp, name, digest):
    new = not os.path.exists(LOG)
    with open(LOG, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["timestamp_local", "experiment", "file", "sha256_16"])
        w.writerow([time.strftime("%Y-%m-%dT%H:%M:%S%z"), exp, name, digest[:16]])


def play_ramp(first_file):
    """10 s gradual raise of the first stimulus, from silence (rule step 3)."""
    src = os.path.join(STIMULI, first_file)
    ramp = os.path.join(HERE, "_ramp_preview.wav")
    subprocess.run(
        ["ffmpeg", "-v", "error", "-i", src,
         "-af", "atrim=0:10,afade=t=in:st=0:d=10",
         "-c:a", "pcm_f32le", ramp, "-y"],
        check=True)
    print("RAMP: mic live, fader from the bottom — 10 s gradual raise. "
          "Watch the room mic return; abort on feedback.")
    try:
        subprocess.run(["afplay", ramp], check=True)
    finally:
        os.remove(ramp)
    time.sleep(5)  # settle: operator confirms the room is stable


def main():
    args = sys.argv[1:]
    if not args or args[0] not in SEQUENCES and args[0] != "--verify-only":
        print(__doc__)
        return 2
    manifest = load_manifest()
    if args[0] == "--verify-only":
        files = sorted(manifest)
        return 0 if verify(files, manifest) else 1
    exp = args[0]
    files = SEQUENCES[exp]
    if not verify(files, manifest):
        print("Checksum verification FAILED — not playing anything.")
        return 1
    print(f"\n{exp}: {len(files)} file(s). Confirm the mic is LIVE and the "
          f"fader is at the bottom, then the ramp starts in 5 s.")
    time.sleep(5)
    play_ramp(files[0])
    for i, name in enumerate(files):
        path = os.path.join(STIMULI, name)
        print(f"playing {name}")
        log_run(exp, name, manifest[name])
        subprocess.run(["afplay", path], check=True)
        if i < len(files) - 1:
            time.sleep(GAP_BETWEEN_FILES_S)
    print("done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
