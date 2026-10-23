# Experiment Protocols: Inaudible Recording Disruption via Ultrasonic Intermodulation

Goal: a reproducible combination of frequencies that disrupts third-party device audio recording (devices using only internal components) while remaining unintelligible to the human ear — reproducible across devices, environments, and experimenters.

**Track A (Experiments 1–6): the jammer.** Ultrasonic carriers → intermodulation in the target mic → audible disruption only in the recording.
**Track B (Experiment 7): the watermark.** Spread-spectrum payload survival through speaker → air → phone (provenance layer, separate objective).

Run in order. Experiment 1 gates everything: if the transducers can't deliver ultrasound, the rest of Track A is theoretical until the playback chain is fixed.

---

## Experiment 1 — Transducer Reality Check

**Question:** What do your monitors actually reproduce at 24–36 kHz, and what can a phone mic even hear up there?

- A. Generate calibration tones: for each f in {24, 26, 28, 30, 32, 34, 36} kHz, run
  `ffmpeg -f lavfi -i "sine=f=<F>:r=96000:d=5:beep_factor=1" -c:a pcm_f32le tone_<F>k.wav`
- B. Fix monitor gain at your normal working level. Play tones one at a time, 5 s each.
- C. Phone at 1 m on-axis running a spectrum analyzer app (e.g., Spectroid). Screenshot each tone.
- D. For each frequency, note: measured peak level vs. the app's noise floor.
- E. Sanity check: can you hear anything in the room during any tone? (You shouldn't — but a rattling tweeter or IMD in the monitor would show up here.)
- F. Define your **usable ultrasonic band**: frequencies where measured output ≥ 10 dB above the noise floor.

**Pass:** a documented usable band at least 4 kHz wide. Every later experiment places carriers inside it. If no usable band exists, Track A is blocked until the playback chain is upgraded — do not proceed on assumption.

---

## Experiment 2 — Static-Carrier Difference Tone

**Question:** Does the target mic demodulate f2−f1 while the room stays silent?

- A. Pick f1, f2 inside the usable band, ≥ 2 kHz apart (e.g., 28.0 and 31.0 kHz → 3.0 kHz product).
- B. Generate: `ffmpeg -f lavfi -i "sine=f=28000:r=96000:d=10:beep_factor=1" -f lavfi -i "sine=f=31000:r=96000:d=10:beep_factor=1" -filter_complex "[0][1]amix=inputs=2:normalize=0,volume=-6dB" -c:a pcm_f32le carriers.wav`
- C. **Control runs:** play f1 alone 10 s, record with phone. Play f2 alone 10 s, record. (Expect: no difference tone in either.)
- D. **Test run:** play both 10 s, record with phone at 1 m, 2 m, 3 m.
- E. In-room check during playback: silent? Any audible tone, buzz, or click?
- F. Analyze each phone recording (Audacity spectrum or equivalent): is f2−f1 present? Level vs. noise floor?
- G. If an audible tone exists in the room during the test run but not the controls, the difference product is being born in your monitors (speaker IMD) — see Experiment 5.

**Pass:** difference tone ≥ 15 dB above noise floor in the phone recording at 2 m, nothing audible in the room.

---

## Experiment 3 — Transient Chirp Burst

**Question:** Does the FFmpeg burst design produce the intended sweeping disruption in a real capture?

- A. Generate the verified burst (Gaussian dip pre-compensates the 2–4 kHz ear-sensitivity zone; `beep_factor=1` keeps carriers level-matched):
  `ffmpeg -filter_complex "sine=f=28000:r=96000:d=0.015:beep_factor=1[a];aevalsrc='sin(2*PI*(33000*t + ((29000-33000)/(2*0.015))*t*t))':s=96000:d=0.015[b];[a][b]amix=inputs=2:normalize=0[mix];aevalsrc='1-0.6*exp(-pow((t-0.0075)/0.0032,2))':s=96000:d=0.015[g];[mix][g]amultiply[dipped];[dipped]afade=t=out:st=0.002:d=0.013,volume=-6dB" -c:a pcm_f32le transient_chirp_dipped.wav`
- B. Loop the burst with 500 ms gaps for 30 s. Play through monitors.
- C. Record with phone at 2 m.
- D. Analyze: does each burst show the ~5→1 kHz downward difference sweep in the recording? (Verified in simulation; confirm in air.)
- E. In-room check: silent during playback?
- F. A/B against the undipped version: confirm the dip didn't kill the product, only tamed the 3 kHz region.

**Pass:** sweep visible per-burst in the recording, room silent, dip version ≥ 10 dB product above noise floor.

---

## Experiment 4 — 8 ms Gating & Mic Overload

**Question:** Do sub-10 ms bursts evade hearing while overloading phone MEMS mics?

- A. Build the gated sequence: 8 ms bursts of the Experiment 3 burst design, amplitude jumping −6 dB ↔ +12 dB between bursts.
- B. **Blind in-room test:** have someone else start/stop playback while you listen. Can you reliably detect on vs. off? (Expect: no.)
- C. Record with 2–3 different phone models at 1–3 m.
- D. Analyze per model: clipping indicators? AGC pumping (gain breathing after bursts)? Difference-tone level?
- E. Listen to the *recordings* (not the room) for a 125 Hz click train from the hard 8 ms mute edges. If present, layer masking transients timed onto the mute edges (see design notes) and re-test.
- F. Confirm the +12 dB jumps aren't digitally clipping pre-monitor in a way that sprays audible harmonics into the room (spectrum analyzer in-room during the loud bursts).

**Pass:** blind test at chance level in-room; visible mic stress (clipping/AGC artifacts) in recordings across all tested models.

---

## Experiment 5 — Dual-Speaker Carrier Separation

**Question:** Does one-carrier-per-speaker kill in-room speaker IMD without hurting mic demodulation?

- A. Route f1 to the left monitor only, f2 to the right monitor only (hard pan, no mixing).
- B. In-room spectrum check during playback: any audible difference tone? (Expect: none — neither driver sees both tones.)
- C. Phone recording at the equidistant sweet spot, then 1 m off-axis: difference tone present at what level?
- D. A/B against single-speaker mixed playback from Experiment 2 at matched total SPL.
- E. If dual-speaker underperforms, try the pre-delay variant: one carrier dry, the other delayed 20–60 ms, and note the room-dependence of the result.

**Pass:** dual-speaker shows equal or greater mic product than single-speaker, with zero in-room difference tone.

---

## Experiment 6 — Recovery-Window Timing

**Question:** Can burst timing trap the mic preamp in sustained clipping?

- A. From Experiment 4 recordings, estimate each phone's recovery time: after a burst ends, how long until the recording's background gain returns to normal?
- B. Set the burst repetition interval to land *inside* the measured recovery window.
- C. Record 30 s continuous. Analyze: sustained clipping/dropout, or clean recovery gaps between bursts?
- D. Sweep the interval ±50 % around the estimate to map the trap window per device.
- E. Document per-model timing — this becomes part of the reproducible recipe.

**Pass:** recording shows continuous disruption with no clean recovery gaps at the tuned interval.

---

## Experiment 7 — Watermark Survival (audiowmark minimal proof)

**Question:** Does a spread-spectrum watermark survive speaker → air → phone capture and remain detectable? (Provenance layer — separate from disruption.)

- A. Install: `audiowmark`, plus `fftw3`, `libsndfile` per the pipeline spec Phase 1.
- B. `audiowmark gen-key secret.key` (chmod 400).
- C. Take a 10 s music clip. Embed: `audiowmark add --strength 12 clip.wav marked.wav <128-bit hex payload>`.
- D. Play marked.wav through monitors at normal level. Record with phone voice memo at 2 m.
- E. `audiowmark get --key secret.key --detect-speed phone_recording.wav` — payload recovered?
- F. Vary: strength 10 vs 14; WAV vs MP3 source; 1 m vs 4 m capture.
- G. Log: which combinations recover, with what correlation scores.

**Pass:** payload recovered from at least one real room capture. This validates the watermark layer independently of the jammer.

---

## Experiment 8 — Nyquist Mirror Fold Hijack

**Question:** Can aliasing across the Nyquist boundary generate a controllable jamming signal that leaves no trace in standard monitors?

**Principle:** At 44.1 kHz, the digital ceiling (f_Nyquist) is exactly 22,050 Hz. When an unbandlimited oscillator sweeps above Nyquist, the digital system cannot track it — instead it mirrors backward into the passband per the aliasing formula: f_alias = |2·f_Nyquist − f_target|. By forcing a collision between an in-band anchor tone and an out-of-band "ghost" alias, you hijack the folded image to manipulate the phase relationship the MEMS mic demodulates.

- A. **Session setup** (44.1 kHz / 24-bit):
  - Track A (in-band anchor): sine wave fixed at 21,550 Hz, −6 dBFS.
  - Track B (modulating carrier): pure sine sweeping 21,000 → 23,100 Hz (LFO or pitch automation), −6 dBFS.
  - **Mandatory:** turn off all internal oversampling / anti-aliasing filters in the synth plugin. You need the raw mathematical generator to render past Nyquist so the DAW is forced to fold it.
- B. **The fold map** (what the digital image does as Track B sweeps):

  | Track B target pitch | Digital image lands at | Offset from anchor (21,550 Hz) | MEMS beat frequency |
  |---|---|---|---|
  | 21,550 Hz (sub-Nyquist) | 21,550 Hz (direct) | 0 Hz | 0 Hz (static phase lock) |
  | 22,050 Hz (at boundary) | 22,050 Hz | +500 Hz | 500 Hz |
  | 22,550 Hz (over boundary) | 21,550 Hz (folded ghost) | 0 Hz (phase collision) | 0 Hz |
  | 23,100 Hz (over boundary) | 21,000 Hz (folded ghost) | −550 Hz | 550 Hz |

- C. **The zero-crossing null:** at 22,550 Hz the folded ghost lands on the exact frequency of the Track A anchor. Flip polarity (∅) on Track A with a utility trim plugin — the instant Track B sweeps past 22,550 Hz, its aliased reflection perfectly cancels Track A. Ultrasonic output momentarily vanishes into digital silence, then reappears as Track B continues past the boundary.
- D. **MEMS behavior:** the capsule acts as a square-law / non-linear detector tracking the difference between the two tones. While Track B is under Nyquist, the difference tone tracks normally. The moment it crosses Nyquist, the difference tone reverses direction inside the MEMS pre-amp — as DAW automation pitches *up*, the demodulated tone recorded by the phone slides *down*, collides with 0 Hz (DC), then slides back up.
- E. Automate Track B pitch back and forth across 22,050 Hz. Record with phone at 2 m. Analyze: rhythmic sweeping modulation in the recording, direction-reversing at each boundary crossing.
- F. **Inaudibility check:** standard audio monitors (and human hearing) perceive nothing — the entire mechanism lives in the ultrasonic band and the digital fold. Confirm room silence during playback.

**Pass:** phone recording shows direction-reversing sweep synchronized to Track B's boundary crossings, with the zero-crossing null visible as a momentary dropout; room silent throughout.

**Depends on:** Experiment 1 (usable band must include 21–23 kHz region), Experiment 2 (difference-tone demodulation concept).

## Design notes carried forward

- **Level-match carriers.** The `sine` filter's default `beep_factor` attenuates; use `beep_factor=1` or the difference product starves (measured −7 dB deficit before the fix).
- **Gain-riding via time↔frequency mapping.** A downward chirp maps time to difference-frequency deterministically, so a temporal gain dip *is* a spectral dip on the demodulated product. Dip the 2–4 kHz ear-sensitivity zone, restore energy at the sweep edges.
- **`volume` eval is per-frame, not per-sample.** Build gain envelopes as `aevalsrc` streams and `amultiply` them.
- **Two speakers beat time separation.** Spatial carrier separation kills speaker IMD without the room-dependence of pre-delay overlap.
- **Watch digital clipping.** +12 dB jumps must not clip pre-monitor into audible harmonics; verify in-room with a spectrum analyzer.
- **Ultrasonic reality check first.** If Experiment 1 finds no usable band, consider the masked in-band (Cinavia-style) watermark layer as the universal fallback — it works through any transducers.

## Reproducibility checklist (for the final recipe)

- [ ] Carrier frequencies and levels (dBFS), sample rate, bit depth
- [ ] Burst duration, gap/gate timing, amplitude jump values
- [ ] Speaker model(s), placement, distances, room description
- [ ] Target phone models + OS versions
- [ ] In-room inaudibility evidence (blind test result / spectrum screenshots)
- [ ] Recording analysis (spectrograms showing the disruption product)
- [ ] Anyone following this document can reproduce the result
