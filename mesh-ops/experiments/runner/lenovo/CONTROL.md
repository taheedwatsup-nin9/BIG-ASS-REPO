# Lenovo-side experiment control kit (saved 2026-10-22)

Proven in the Exp 8 run #2 session. Results: ../../results/. Run log: ../run_log_lenovo.csv.

## One-line run
    NOTE="hypothesis / what to watch" ./run.sh exp8-premix ../../stimuli/exp8_premix.wav 0.6 44100
This starts the phone (verified by file growth) and logs a row. It then ramps the fader 0 -> ceiling over 10 s, plays the file, re-mutes, stops the phone and pulls the WAV into results/raw/.

## Settings snapshot (the known-good state)
| Stage | Setting | Value | Who/what controls it |
|---|---|---|---|
| Lenovo output | jack | **Headphone** (not Mic). Check: `pactl list sinks \| grep 'Active Port'` = analog-output-headphones | physical; autofader.sh aborts otherwise |
| Lenovo output | sample rate | 48 kHz default; forced to stimulus rate (44100) during the run, then 0 | autofader.sh arg 4 (`pw-metadata clock.force-rate`) |
| Lenovo output | volume | 0 -> ceiling (0.6 used) over 10 s, muted at rest | autofader.sh (wpctl) |
| Cable | Lenovo HP jack -> 3.5 mm-to-RCA (TIP=L, RING=R) | Monitor Station rear AUX In | physical |
| Monitor Station v2 | Main Source | **AUX lit** (ST1/ST2 may also be lit) | physical, set once |
| Monitor Station v2 | AUX/SPDIF button | **AUX** (was SPDIF, which gives silence) | physical, set once |
| Monitor Station v2 | AUX Input level | ~12 o'clock | physical, set once |
| Monitor Station v2 | Speaker select | A | physical |
| BX5 D2 | rear volume | max | physical |
| Saffire Pro 14 (Mac FW800) | sample rate | 96 kHz | Mac CoreAudio script (scratch sr.py) |
| Saffire Pro 14 | ch2 preamp | 9 (turn down to ~3 for line sources) | physical |
| S10 recorder | app/profile | ASR, EXP8_WAV48_RAW: WAV mono 48 kHz, Unprocessed mic, NC off | s10.sh (adb) |
| S10 recorder | placement | ~2 m from the monitors, mic edge toward them, screen on (`svc power stayon usb`) | physical / adb |

## Control methods (AI-operable)
- **Phone:** `s10.sh start|stop|state|pull|tap "<text>"`. State comes from file growth, never from counting taps; taps toggle and drift.
- **Fader:** `autofader.sh file ceiling ramp rate`. The exit trap always re-mutes and resets the rate, even on abort or Ctrl-C.
- **Mac route (alternative, same as Logic):** `scp file mac:CR8_EXP/` then `ssh mac 'afplay -v 0.3 -t 3 ~/CR8_EXP/file'`. The Mac has no python3/sox/ffmpeg.
- **Analysis:** ASR WAVs have a header scipy can't read, and the header is STALE while recording. Read raw PCM from the 'data' chunk to EOF (see results/), or decode with ffmpeg after stop.

## Environment rules (binding, Taheed)
1. Recording live BEFORE any signal. 2. Fader starts at 0. 3. Gradual ramp. 4. Abort on squeal or feedback; the room is ground truth.
