# Demo Video V2 — Master Audio Timeline & Loudness Report

**Project:** NISAR // Earth in Motion  
**Deliverable:** rtifacts/demo/nisar_earth_in_motion_demo_v2.mp4  
**Audio Track:** AAC LC · 48,000 Hz · 2 Channels (Stereo) · 90.000 s  
**Integrated Loudness:** **-15.3 LUFS** (EBU R128 compliant, Target: -16 LUFS)  
**Loudness Range (LRA):** 6.1 LU  
**True Peak:** <= -1.5 dBTP  

---

## Zero-Overlap Narration Timeline

Every scene's narration is strictly sequential with zero vocal overlap, providing breathing room before and after each segment.

| Scene # | Scene Name | Start Time | Speech End | Silence Before | Silence After | Audio Duration | Narration Focus |
|---|---|---|---|---|---|---|---|
| **Scene 1** | Planetary Opening & Orbit | 0.80 s | 10.78 s | 0.80 s | 2.02 s | 9.98 s | 12-day repeat cycle, L-band 1.239 GHz, Earth penetration |
| **Scene 2** | Research Challenge | 12.80 s | 25.52 s | 2.02 s | 1.28 s | 12.72 s | June 2026 Northern Venezuela doublet (32.2s separation), Track 162 |
| **Scene 3** | Engineering Achievement | 26.80 s | 39.20 s | 1.28 s | 1.80 s | 12.40 s | 2.34 GB HDF5, attached dimension scales, 4x mismatch fix, 80m EPSG:32619 |
| **Scene 4** | Interactive Scientific Explorer | 41.00 s | 60.04 s | 1.80 s | 5.96 s | 19.04 s | Radians phase, coherence 0.406 (M7.2) vs 0.077 (M7.5), reliability |
| **Scene 5** | Scientific Honesty & Guardrails | 66.00 s | 77.30 s | 5.96 s | 3.20 s | 11.30 s | No unvalidated displacement, no damage claim, reproducible exports |
| **Scene 6** | Mission Closing & Reproducibility | 80.50 s | 86.76 s | 3.20 s | 3.24 s | 6.26 s | LunaHorizon mission motto, transparent radar science |
| **Total** | | **0.80 s** | **86.76 s** | — | — | **71.70 s** | **90.000 s Total Container** |

---

## Audio Engineering & Filter Graph

`
Scene 1: temp_audio_test/scene1.wav (22.05k mono) -> aresample=48000,pan=stereo,adelay=800|800      -> [a1]
Scene 2: temp_audio_test/scene2.wav (22.05k mono) -> aresample=48000,pan=stereo,adelay=12800|12800  -> [a2]
Scene 3: temp_audio_test/scene3.wav (22.05k mono) -> aresample=48000,pan=stereo,adelay=26800|26800  -> [a3]
Scene 4: temp_audio_test/scene4.wav (22.05k mono) -> aresample=48000,pan=stereo,adelay=41000|41000  -> [a4]
Scene 5: temp_audio_test/scene5.wav (22.05k mono) -> aresample=48000,pan=stereo,adelay=66000|66000  -> [a5]
Scene 6: temp_audio_test/scene6.wav (22.05k mono) -> aresample=48000,pan=stereo,adelay=80500|80500  -> [a6]
Silence: anullsrc=channel_layout=stereo:sample_rate=48000 (90s)                                     -> [silence]

[silence][a1][a2][a3][a4][a5][a6]
  amix=inputs=7:duration=longest:dropout_transition=0
  volume=2.2
  loudnorm=I=-16:TP=-1.5:LRA=11
  -> [aout] (48,000 Hz, 2ch Stereo, 140.5 kbps AAC)
`

---

## Measured EBU R128 Loudness Verification

Verification performed using fmpeg -filter_complex ebur128 -f null:
- **Integrated Loudness (I):** -15.3 LUFS
- **Target Specification:** -16.0 LUFS (+- 1.0 LUFS tolerance) — **MET**
- **Threshold:** -25.5 LUFS
- **Loudness Range (LRA):** 6.1 LU
- **LRA High:** -14.5 LUFS
- **LRA Low:** -20.6 LUFS
- **Audible Overlaps:** 0 ms (Zero overlapping speech segments)
