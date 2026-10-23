#!/usr/bin/env python3
"""
analyze_recording.py — spectral reads for the intermodulation experiments.

Takes a capture (phone recording, interface capture — any format ffmpeg
reads), converts to mono float at its native sample rate, and measures
targeted frequencies against the capture's own noise floor.

Modes:
  exp1   REC            The 7 calibration tones (24–36 kHz). Reports each
                        tone's peak level, the noise floor, SNR per tone,
                        and calls the usable band per the protocol:
                        tones >= 10 dB over floor; PASS needs a contiguous
                        span >= 4 kHz wide.
  tones  REC F1 F2 ...  Peak level + SNR for arbitrary frequencies (Hz).
  diff   REC F1 F2      For an f1/f2 carrier pair: level at |f2-f1| (the
                        difference product), at f1, at f2, each with SNR
                        vs the local floor. Exp 2's core read.

SNR method: STFT (4096-pt Hann, 50% hop). Per target: signal = 95th
percentile of band power (±120 Hz) across frames; floor = median band
power in a guard band ±(600–1200) Hz around the target. Honest about
what it is: a screening read on real captures, not a lab measurement.

Author: MUZI, 2026-10-22.
"""

import subprocess
import sys
import numpy as np
from scipy import signal as sig

WIN = 4096


def load_mono(path):
    info = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=sample_rate",
         "-of", "csv=p=0", path], capture_output=True, text=True)
    out = info.stdout.strip()
    if not out:
        raise SystemExit(f"cannot read {path} (ffprobe found no audio stream)")
    sr = int(out.split(",")[0])
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", path, "-f", "f32le", "-ac", "1",
         "-ar", str(sr), "-"], capture_output=True)
    return np.frombuffer(raw.stdout, dtype=np.float32), sr


def stft_mag(x, sr):
    f, t, Z = sig.stft(x, fs=sr, window="hann", nperseg=WIN,
                       noverlap=WIN // 2, detrend=False)
    return f, np.abs(Z)


def band_level_db(freqs, mag, center, half_width):
    m = (freqs >= center - half_width) & (freqs <= center + half_width)
    if not m.any():
        return None, None
    band = mag[m, :]
    peak = 20 * np.log10(np.percentile(band, 95) + 1e-12)
    guard = ((freqs >= center - 1200) & (freqs <= center - 600)) | \
            ((freqs >= center + 600) & (freqs <= center + 1200))
    floor = 20 * np.log10(np.median(mag[guard, :]) + 1e-12) if guard.any() else float("nan")
    return peak, floor


def report(freqs, mag, targets, label):
    rows = []
    print(f"\n== {label} ==")
    print(f"{'freq Hz':>9} {'peak dBFS':>10} {'floor dBFS':>11} {'SNR dB':>8}")
    for c in targets:
        peak, floor = band_level_db(freqs, mag, c, 120)
        if peak is None:
            print(f"{c:>9}  above Nyquist for this capture — not measurable")
            rows.append((c, None, None, None))
            continue
        snr = peak - floor
        if peak < -80:
            # Digital-silence territory: the tone is ABSENT. A huge "SNR"
            # against a -190 dB numerical floor would be a lie.
            rows.append((c, peak, floor, None))
            print(f"{c:>9} {peak:>10.1f} {floor:>11.1f}   absent")
        else:
            rows.append((c, peak, floor, snr))
            print(f"{c:>9} {peak:>10.1f} {floor:>11.1f} {snr:>8.1f}")
    return rows


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    mode, path = sys.argv[1], sys.argv[2]
    x, sr = load_mono(path)
    print(f"capture: {path}  sr={sr}  dur={len(x)/sr:.1f}s  nyquist={sr//2} Hz")
    freqs, mag = stft_mag(x, sr)

    if mode == "exp1":
        targets = [24000, 26000, 28000, 30000, 32000, 34000, 36000]
        rows = report(freqs, mag, targets, "Experiment 1 — calibration tones")
        ok = [c for c, p, fl, s in rows if s is not None and s >= 10]
        # widest contiguous run of passing tones (2 kHz spacing)
        best = cur = 0
        prev = None
        for c in targets:
            if c in ok and (prev is None or c - prev == 2000):
                cur += 1
            elif c in ok:
                cur = 1
            else:
                cur = 0
            prev = c if c in ok else None
            best = max(best, cur)
        span = (best - 1) * 2 if best else 0
        print(f"\ntones >= 10 dB over floor: {ok}")
        print(f"widest contiguous span: {span} kHz -> "
              f"{'PASS (>= 4 kHz usable band)' if span >= 4 else 'NO PASS — playback chain cannot deliver a usable band yet'}")
    elif mode == "tones":
        report(freqs, mag, [float(v) for v in sys.argv[3:]], "targeted tones")
    elif mode == "diff":
        f1, f2 = float(sys.argv[3]), float(sys.argv[4])
        report(freqs, mag, [f1, f2, abs(f2 - f1)],
               f"carrier pair {f1:.0f}/{f2:.0f} — difference product {abs(f2-f1):.0f} Hz")
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
