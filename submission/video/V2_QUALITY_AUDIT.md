# Demo Video V2 — Quality Audit Report

**Project:** NISAR // Earth in Motion
**Challenge:** NASA Space Apps 2026 — Dancing with the SARs
**Audit Date:** 2026-11-03

## V1 Baseline Metrics

| Attribute | V1 Measured |
|-----------|-------------|
| File size | 6,539,465 bytes (6.24 MiB) |
| Duration | 90.000 s |
| Resolution | 1920 x 1080 |
| Frame rate | 30/1 FPS |
| Video codec | H.264 High Profile |
| Audio sample rate | **22,050 Hz (DEFECT - target 48,000 Hz)** |
| Audio channels | **1 mono (DEFECT - target stereo)** |

## V1 Defect Register

### D-01 Audio Sample Rate (Critical)
- Observed: 22,050 Hz mono - native SAPI WAV rate propagated into final MP4.
- Target: 48,000 Hz stereo, >=128 kbps.
- Root cause: FFmpeg amix pulled sample rate from first narration WAV (22050 Hz).
- Fix (V2): All WAVs resampled to 48 kHz stereo via aresample filter before mixing.

### D-02 Temporal Baseline Display
- Acquisition timestamps: 2026-06-13T10:06:56Z to 2026-06-25T10:06:55Z.
- Exact elapsed: 11 days 23 hours 59 minutes 59 seconds.
- NISAR nominal repeat cycle: 12 days.
- Fix (V2): All references changed to "~12-day repeat cycle (11d 23h 59m elapsed)".

### D-03 Black Ending (1.5 seconds)
- Observed: 45 frames of blank black after closing title card.
- Fix (V2): Black segment removed; all 360 frames show closing title card.

### D-04 Static vs Interactive Footage
- Observed: Interactions simulated via injected DOM; no real CDP mouse events fired.
- Fix (V2): CDP Input.dispatchMouseEvent for slider drag and canvas hover.

### D-05 Subtitle Contrast
- Observed: 30pt font with semi-transparent background - marginal contrast on bright tiles.
- Fix (V2): 34pt font, opaque box style (BorderStyle 3), 60px bottom margin.

## V2 Target Specification

| Attribute | V2 Target |
|-----------|-----------|
| Path | artifacts/demo/nisar_earth_in_motion_demo_v2.mp4 |
| Duration | 90.000 s |
| Resolution | 1920 x 1080 |
| Frame rate | 30 FPS |
| Video codec | H.264 High Profile Level 4.2 |
| Audio codec | AAC |
| Audio sample rate | **48,000 Hz** |
| Audio channels | **2 (stereo)** |
| Audio bitrate | 192 kbps |
| Black ending | None |
| Temporal baseline | "~12 days (11d 23h 59m elapsed)" |

## V2 Narration Assets

| Scene | File | Duration |
|-------|------|----------|
| Scene 1 | audio_temp/scene1_r2.wav | 10.85 s |
| Scene 2 | audio_temp/scene2_r2.wav | 14.89 s |
| Scene 3 | audio_temp/scene3_r2.wav | 15.48 s |
| Scene 4 | audio_temp/scene4_r2.wav | 25.26 s |
| Scene 5 | audio_temp/scene5_r2.wav | 13.94 s |
| Scene 6 | audio_temp/scene6_r2.wav | 6.49 s |
| Total | | 86.91 s |

## V2 Validation Checklist

- [ ] Duration = 90.000 s (+-0.1 s)
- [ ] Resolution = 1920 x 1080
- [ ] Frame rate = 30/1
- [ ] Audio sample rate = 48,000 Hz
- [ ] Audio channels = 2 stereo
- [ ] No trailing black frames
- [ ] Subtitles visible at t=2s, t=15s, t=28s, t=42s, t=62s, t=82s
- [ ] Temporal baseline shown as "~12 days"
- [ ] pytest passes: 93/93 tests
- [ ] ruff: 0 errors
