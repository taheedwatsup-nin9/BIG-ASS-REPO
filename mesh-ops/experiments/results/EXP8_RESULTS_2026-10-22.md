# Experiment 8 (Nyquist mirror fold): results, 2026-10-22

Operator: Claude (Lenovo session) with Taheed in the room. Protocol: experiment-protocols.md §8. Log rows: runner/run_log_lenovo.csv.

## Chain (run #2, valid)
Lenovo C40 headphone out (PipeWire forced to 44.1 kHz, no resampling) -> 3.5 mm-to-RCA -> PreSonus Monitor Station v2 AUX In (Main Source AUX, AUX/SPDIF = AUX) -> M-Audio BX5 D2 (volume maxed).
Recorder: Samsung S10, ASR Voice Recorder, WAV mono 48 kHz, Unprocessed mic, noise cancellation off, about 2 m from the monitors.
Level: software auto-fader 0 -> 0.6 over 10 s, on top of the file's own 10 s fade-in. Stimulus: exp8_premix.wav (SHA256 OK) with a 10 s ramp prelude.
Chain check before the run: a 1 kHz tone at -20 dBFS through the same path. Heard by Taheed; on the phone it sat 40 dB above the floor.

## Run #1 (22:30): INVALID
The cable was in the Lenovo's MIC jack, so audio played from the Lenovo's internal speaker. Disregard.

## Run #2 (22:54:43): result
| Check | Result | Hypothesis / thoughts / questions |
|---|---|---|
| 21-23 kHz content reaches the phone via the monitors | YES: +30 to +48 dB over the band floor | The BX5 D2 tweeter still radiates at 21-22 kHz despite its 22 kHz rating. Q: how far above 22 kHz before it drops into the noise? (Exp 1 answers this.) |
| Fold trajectory | YES: 21.0 -> 22.1 kHz, then folds back down to 21.04 kHz, matching MUZI's offline STFT | The fold is baked into the file, so the phone records what was played. It proves fidelity, not a mic effect. |
| 21,550 Hz anchor | Present, +22 to +36 dB | Anchor and sweep are both in the air at once, so the conditions for intermodulation were met. |
| Audible demodulated beat (20-1200 Hz) tracking abs(fB - 21550) | NO: low band stayed at the pre-playback level (+8 to +13 dB, random frequencies) | H1: the level is too low for the MEMS square-law term to rise above the noise (it scales +2 dB per +1 dB). H2: the "Unprocessed mic" path's own high-pass hides sub-100 Hz products. H3: the S10's MEMS stays linear at these levels. Q: does a louder run, or a different phone, change it? |
| Zero-crossing null (dropout) | NOT seen: at t=31.5 s the folded image and the anchor coincide and the level ADDS (+36.5 dB) | H: the premix lacks the Track A polarity flip, so the two add instead of cancelling. Q (MUZI): re-render with the flip at 14.8 s? |
| Room silence | Taheed did not report audible content | Q: did any audible subharmonic or rattle occur? Ask the operator to note it on every run. |

**Verdict: FAIL on the pass criterion. The chain and capture are VALID.** The S10's MEMS mic records 21-22 kHz linearly but shows no nonlinear demodulation at this level.

## Open, for MUZI
1. The premix needs the Track A polarity flip baked in at 14.8 s, or the null can't appear.
2. A louder run? The square law gives +2 dB of difference product per +1 dB, but BX5 D2 tweeters are rated to 22 kHz, so watch tweeter safety.
3. Per the gate order, the Exp 8 read depends on Exp 1 and 2. Exp 1 (24-36 kHz) needs a measurement mic rated to 40 kHz or above. The TLM 102 and the S10 at 48 kHz can't cover it.
