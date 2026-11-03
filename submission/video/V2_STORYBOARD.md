# Demo Video V2 — Storyboard

**Version:** V2 | **Duration:** 90 s | **Resolution:** 1920 x 1080 | **FPS:** 30

## Scene 1: Planetary Opening (0–12 s | 360 frames)

**Visual:** Earth reveal animation on dark navy background. NISAR // EARTH IN MOTION title.
**HUD:** Mission badge: "NISAR // EARTH IN MOTION | ~12-DAY REPEAT CYCLE"
**Callout:** L-Band 1.239 GHz, ~12-day repeat cycle (11d 23h 59m elapsed between acquisitions)
**Subtitle:** "NISAR, the NASA-ISRO Synthetic Aperture Radar mission, operates on a ~12-day repeat cycle."
**Capture:** 45 snapshot iterations × 8 duplicates = 360 frames

## Scene 2: Research Challenge (12–25 s | 390 frames)

**Visual:** Dashboard scrolled to observation cards. Venezuela card highlighted with cyan outline.
**HUD:** "RESEARCH CHALLENGE | NORTHERN VENEZUELA 2026 | ~12-DAY BASELINE"
**Callout:** Event sequence: 24 June 2026 doublet, M7.2 foreshock + M7.5 mainshock, 148.33 km separation
**Subtitle:** "In June 2026, two major earthquakes struck northern Venezuela within ~32 seconds."
**Capture:** 39 iterations × 10 duplicates = 390 frames

## Scene 3: Engineering Achievement (25–38 s | 390 frames)

**Visual:** Explorer view loaded with phase raster (Venezuela). Phase colormap visible.
**HUD:** "ENGINEERING ACHIEVEMENT | HDF5 DIMENSION-SCALE RESOLUTION"
**Callout:** 2.34 GB HDF5, 80m grid, 4149x4239 pixels, EPSG:32619, 4x coordinate mismatch eliminated
**Subtitle:** "A major engineering challenge was resolving multiple spatial resolutions."
**Capture:** 39 iterations × 10 duplicates = 390 frames
**Pre-warm:** Venezuela observation pre-loaded before capture begins

## Scene 4: Interactive Scientific Explorer (38–58 s | 600 frames)

### 4A: Phase Layer (38–43 s | 150 frames)
**Visual:** Phase raster with viridis colormap. Real CDP mouse cursor moving across raster.
**Subtitle:** "The explorer shows unwrapped phase (radians, multi-cycle) and coherence as measurement quality."

### 4B: Coherence + Slider (43–48 s | 150 frames)
**Visual:** Coherence layer activated. Real CDP slider drag interaction.
**Callout:** Threshold 0.4 → ~16.7% reliable pixels

### 4C: M7.2 Foreshock Hover (48–53 s | 150 frames)
**Visual:** Real CDP mouse hover over canvas near M7.2 epicentre. Event tooltip visible.
**Callout:** Median coherence 0.406 (1.6 km window) — usable phase

### 4D: M7.5 Mainshock (53–58 s | 150 frames)
**Visual:** Event tooltip updated to M7.5. Red border styling.
**Callout:** Median coherence 0.077 — severe coastal decorrelation

## Scene 5: Scientific Honesty & Export (58–78 s | 600 frames)

### 5A: Scientific Limitations (58–68 s | 300 frames)
**Visual:** Limitations section scrolled into view.
**HUD:** "SCIENTIFIC HONESTY & GUARDRAILS | INTERPRETATION: NOT VALIDATED"
**Callout:** No displacement labelling, no GPS anchor, atmospheric delays remain, residual ramps

### 5B: Data Export (68–78 s | 300 frames)
**Visual:** Export section visible with GeoTIFF, quicklook, scientific report buttons.
**HUD:** "REPRODUCIBLE DATA EXPORT | GEOTIFF · QUICKLOOK · JSON · MARKDOWN"
**Subtitle:** "Exports: georeferenced GeoTIFF, scientific report, and quicklook PNG with embedded provenance."

## Scene 6: Mission Closing (78–90 s | 360 frames)

**Visual:** Full-screen closing title card. Radial gradient dark background. NO black ending.
- "NASA Space Apps Challenge 2026 · Dancing with the SARs" (cyan, caps, letter-spaced)
- "NISAR // EARTH IN MOTION" (54px, gradient white-to-teal title)
- "Transforming raw NASA-ISRO Synthetic Aperture Radar products into transparent, rigorous, and accessible Earth science."
- Badge pills: "EPSG:32619 · 80 m Grid", "HDF5 Dimension Scales", "~12-Day Repeat · 86.91 s Narration"
- GitHub link: github.com/Aayushashsahu/LunaHorizon
**Capture:** Single snapshot × 360 duplicates (all 12 s on closing card)

## V2 vs V1 Improvements

| Defect | V1 | V2 |
|--------|----|----|
| Audio sample rate | 22,050 Hz mono | 48,000 Hz stereo |
| Audio bitrate | 74,747 bps | 192,000 bps target |
| Temporal baseline | "12-DAY REPEAT" (generic) | "~12 days (11d 23h 59m elapsed)" |
| Black ending | 45 frames (1.5 s) | None — closing card runs to t=90 |
| Mouse interaction | DOM injection only | Real CDP dispatchMouseEvent |
| Subtitle style | 30 pt, semi-transparent box | 34 pt, opaque box, 60 px margin |
| Pre-warm | None | Venezuela observation loaded before capture |
