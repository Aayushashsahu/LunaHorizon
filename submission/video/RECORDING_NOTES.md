# NISAR // Earth in Motion — Video Recording & Production Notes

**Challenge:** NASA Space Apps Challenge 2026 — Dancing with the SARs  
**Deliverable:** `artifacts/demo/nisar_earth_in_motion_demo.mp4`  

---

## Technical Pipeline & Environment

The demonstration video is produced through a 100% reproducible, local automated capture and rendering pipeline:

1. **Web Application Backend:**
   - Command: `python -m nisar_eim serve --port 8000`
   - Serves local HDF5-derived assets and APIs from `data/processed/` without internet dependencies.
   - Verified offline: no remote CDNs, telemetry, or external API calls.

2. **Browser Automation & Screen Capture:**
   - Chrome Executable: `C:\Program Files\Google\Chrome\Application\chrome.exe`
   - Protocol: Chrome DevTools Protocol (CDP) over WebSocket.
   - Flags: `--headless=new`, `--window-size=1920,1080`, `--disable-gpu`, `--no-first-run`.
   - Viewport: Exact 1920 × 1080 at 1.0 device scale factor.
   - Script: `scripts/record_demo.mjs` orchestrates real user actions (scrolling, clicking tabs, adjusting sliders, triggering tooltips) and captures high-resolution application frames.

3. **Narration Audio Synthesis:**
   - Engine: Windows Speech Synthesis API (`System.Speech.Synthesis.SpeechSynthesizer`).
   - Voice: `Microsoft David Desktop` (clear documentary delivery).
   - Rate: +2 for crisp pacing matching the 90-second duration.
   - Script: `scripts/generate_narration.ps1` synthesizes scene WAV files.
   - Assembly: Audio tracks concatenated and padded to match scene boundaries with normalized volume.

4. **Subtitles & Captions:**
   - Burned directly into the MP4 stream using FFmpeg `subtitles` / `drawtext` filters with high-contrast styling (white text, semi-transparent dark pill background, centered at bottom of 1080p frame).
   - Perfectly synchronized with audio timestamps.

5. **Video Encoding (FFmpeg):**
   - Video Codec: `libx264` (H.264), High profile, Level 4.2.
   - Pixel Format: `yuv420p` (universal playback compatibility).
   - Audio Codec: `aac`, 48000 Hz, stereo, 192 kbps.
   - Container: MP4 (FastStart enabled for instant streaming).
   - Output Path: `artifacts/demo/nisar_earth_in_motion_demo.mp4`.

---

## Scene Duration & Sync Verification

| Scene Index | Scene Title | Start (s) | End (s) | Frame Range (30 FPS) | Audio Duration |
|---|---|---|---|---|---|
| **Scene 1** | Planetary Opening & Orbit | 0.0 | 12.0 | 0 – 359 | 10.85 s |
| **Scene 2** | Research Challenge (Venezuela) | 12.0 | 25.0 | 360 – 749 | 14.89 s |
| **Scene 3** | Engineering Achievement (HDF5) | 25.0 | 38.0 | 750 – 1139 | 15.48 s |
| **Scene 4** | Interactive Scientific Explorer | 38.0 | 58.0 | 1140 – 1739 | 25.26 s |
| **Scene 5** | Scientific Integrity & Export | 58.0 | 78.0 | 1740 – 2339 | 13.94 s |
| **Scene 6** | Mission Closing & Reproducibility | 78.0 | 90.0 | 2340 – 2699 | 6.49 s |
| **TOTAL** | | **0.0** | **90.0** | **2700 frames** | **86.91 s narration** |

---

## Quality & Scientific Integrity Checklist

- [x] Unwrapped phase displayed strictly in radians.
- [x] Coherence labeled as measurement quality, not damage.
- [x] Both USGS earthquake markers displayed at actual geodetic coordinates.
- [x] Epicentre separation verified at 148.33 km.
- [x] Illustrative disclaimer visible during global mission orbit view.
- [x] Scientific Limitations badge ("NOT VALIDATED") clearly visible in Scene 5.
- [x] Zero console errors or broken network requests in footage.
- [x] No copyrighted music or synthetic claims of NASA endorsement.
