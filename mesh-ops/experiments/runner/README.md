# Experiment runner — tandem runbook (MUZI + Claude)

Taheed's order (2026-10-22): run the intermodulation experiments, MUZI and
Claude in tandem, on the MacBook while he's not using it, Logic Pro as the
session host, scripts sent over to the OS.

## Split of duties
- **MUZI (builds + verifies):** all stimulus files (../stimuli/, generated
  with the protocol's exact ffmpeg recipes, SHA256SUMS.txt manifest),
  these runner scripts, run-order discipline, and spectrogram analysis of
  the phone recordings when they come back.
- **Claude (machine side, Lenovo lane):** scout + operate the MacBook —
  confirm reachability from the Lenovo, macOS + Logic versions, whether
  the machine is free; receive the package (GitHub BIG-ASS-REPO →
  mesh-ops/experiments/); set the interface to 96 kHz in Audio MIDI Setup;
  build the Experiment 8 Logic template once from the recipe below; run
  playbacks only when the room setup matches the protocol.
- **Human/in-room (whoever is at the bench):** monitor gain fixed at the
  normal working level (Exp 1 sets it), phone on a stand at the marked
  distances running a spectrum app / voice recorder, in-room silence
  checks. Playback can be scripted; ears and phone placement can't.

## Room rig (set by Taheed in the room, 2026-10-22 17:19)
- Room mic directly in front of the monitors, on interface **input 2**,
  facing **perpendicular** to the monitors (his feedback mitigation).
  This mic is the team's ears in the room — experiments that need
  in-room listening/analysis record through it, and stimuli play out of
  the monitors on the same interface.
- Monitor level: set by Taheed to "a decent level" — do not change it;
  Experiment 1's band is defined at whatever level he set.
- **S10 USB-tethered to the Lenovo**: fully charged, unlocked, display
  set to never time out. Its microphone is a sanctioned target-device
  recorder — drive it from the Lenovo (adb) so recordings start/stop in
  sync with playback and files pull straight back for analysis.
- Optional direct feed: PreSonus Monitor Station V2 headphone out can be
  cabled to the S10's mic input if an experiment needs line-level input
  instead of air capture (Taheed's offer — ask before rewiring).
- Remote desktop: **Remmina** on the Lenovo connects straight to the
  MacBook's screen sharing at **192.168.1.236** (Taheed, 2026-10-22) —
  the sanctioned visual route into the Mac. Frequency analysis =
  ffmpeg/scipy spectrograms on MUZI's side. (Local runbook updated;
  repo copy syncs on the next push.)

## Environment + ramp rule (Taheed, 2026-10-22 — binding, every run)
The monitors play into a REAL room at real volume, with a live mic in
front of them. Therefore, no exceptions:
1. **Mic live first.** The recording/listening chain (interface input 2 +
   the S10 recorder) is rolling before any signal plays.
2. **Fader starts at the bottom** (off) for every run.
3. **Raise gradually.** The runner plays a 10-second ramp prelude (first
   stimulus faded in from silence) while the operator rides the fader up
   and watches the room mic's return.
4. **The room is ground truth.** Measured output at the mic — not the
   file's dBFS — decides levels. Abort on feedback, squeal, clipping on
   input 2, or anything audible that shouldn't be.

## Gate order (protocols file governs)
1. **Exp 1** — transducer reality check: 7 tones 24–36 kHz → usable band.
   NOTHING else in Track A proceeds on assumption without the band.
2. **Exp 2** — static carriers (28k/31k defaults; re-cut if Exp 1's band
   says otherwise), controls first, then the pair at 1/2/3 m.
3. **Exp 3** — burst loop, per-burst sweep check in the recording.
4. **Exp 8** can be BUILT in parallel (44.1 kHz session, below) but its
   pass/fail read still depends on Exp 1 + 2.

## Experiment 8 Logic template (build once, save as exp8_template.logicx)
- Session 44.1 kHz / 24-bit. Oversampling/anti-aliasing OFF in the synth.
- Track A: exp8_trackA_anchor_21550.wav (21,550 Hz, −6 dBFS), plus a
  utility/gain plugin whose polarity (∅) flip is automated at the moment
  Track B's sweep crosses 22,550 Hz (≈ 14.8 s into the 20 s render; the
  sweep crosses Nyquist 22,050 Hz at exactly 10.0 s). VERIFIED offline
  by MUZI 2026-10-22: STFT of exp8_premix.wav tracks the moving
  component 21,210 → 22,050 (t=10 s) then folded back down 21,835 →
  21,103 — the fold renders exactly as the protocol predicts.
- Track B: exp8_trackB_sweep_21000_23100.wav (21,000 → 23,100 Hz sweep).
- Reference render for comparison: exp8_premix.wav (what MUZI rendered
  offline — the fold null should appear in both).
- Record: phone at 2 m; expect the direction-reversing difference sweep
  with a dropout at each boundary crossing; room silent.

## Transfer + identity
Everything travels via BIG-ASS-REPO (mesh-ops/experiments/). Before any
playback, run `python3 run_experiment.py --verify-only` — it refuses to
play a file whose sha256 doesn't match the manifest.

Status 2026-10-22 (MUZI): stimuli for Exp 1/2/3/8 generated + verified;
runner written; MacBook scout assigned to Claude. No playback has run yet.
