# NISAR // Earth in Motion — 90-Second Demonstration Video Storyboard

**Challenge:** NASA Space Apps Challenge 2026 — Dancing with the SARs  
**Repository:** <https://github.com/Aayushashsahu/LunaHorizon>  
**Target Video File:** `artifacts/demo/nisar_earth_in_motion_demo.mp4`  
**Output Specs:** 1920 × 1080 | 30 FPS | H.264 / AAC | Subtitles burned-in  

---

## Storyboard Timeline

```
00:00        00:12        00:25        00:38                  00:58                  01:18        01:30
|-- Scene 1 ---|-- Scene 2 ---|-- Scene 3 ---|------ Scene 4 -------|------ Scene 5 -------|-- Scene 6 --|
  Planetary      Research      Engineering       Interactive            Scientific           Mission
  Reveal         Challenge     Achievement       Explorer               Honesty & Export     Closing
```

---

### Scene 1: Planetary Opening (00:00 – 00:12)
- **Time Window:** 0.0 s – 12.0 s (Frames 0 – 359)
- **View:** Hero Section (`#view-dashboard`)
- **Key Visual Elements:**
  - Dynamic 3D Earth reveal animation: Earth scaling up from space.
  - Two non-overlapping green orbital-tracking strokes ($R = 272.5\text{ px}$) sweeping up opposing limbs and meeting at the north apex.
  - Orbit path, satellite spacecraft marker, moving radar ground beam illumination.
  - HUD telemetry readouts (inclination $97.9^\circ$, altitude $747\text{ km}$, repeat cycle $12\text{ days}$).
  - Mission Title: `NISAR // EARTH IN MOTION`
  - Subtitle: `Dancing with the SARs | NASA Space Apps 2026`
  - Disclaimer banner: `[ILLUSTRATIVE MISSION VISUALIZATION — 12-DAY ORBIT REPEAT CYCLE]`
- **Camera/Action:** Hold wide on hero, tracking strokes sweep across 2.4s, satellite maintains continuous orbit.

---

### Scene 2: Research Challenge — Northern Venezuela 2026 (00:12 – 00:25)
- **Time Window:** 12.0 s – 25.0 s (Frames 360 – 749)
- **View:** Dashboard View (`#view-dashboard`)
- **Key Visual Elements:**
  - Smooth scroll down from Hero to Observation Cards.
  - Card 1: `Venezuela — June 2026 Earthquake Sequence` with `REAL NISAR` badge.
  - Temporal Baseline: `2026-06-13 -> 2026-06-25` (12-day repeat cycle).
  - USGS Reference Events panel:
    - Foreshock: M7.2, 20 km E of San Felipe, 22:04:31 UTC.
    - Mainshock: M7.5, 20 km W of Catia La Mar, 22:05:04 UTC (32.2 s separation).
    - Separation distance: 148.33 km.
- **Camera/Action:** Mouse moves smoothly to the "Open Explorer" button and clicks.

---

### Scene 3: The Engineering Achievement — HDF5 Dimension Scales (00:25 – 00:38)
- **Time Window:** 25.0 s – 38.0 s (Frames 750 – 1139)
- **View:** Observation Explorer (`#view-explorer`)
- **Key Visual Elements:**
  - Header: `Venezuela Earthquake Sequence (June 2026)`
  - Subtitle: `Track 162 · Ascending · EPSG:32619 · 80 m posting`
  - The 80-meter raster canvas paints pixel-aligned radar data (4,149 × 4,239 grid).
  - Technical Callout Box / Highlight:
    - `Raw HDF5 Granule: ~2.34 GB`
    - `Dimension Scales: Attached DIMENSION_LIST vectors resolved`
    - `Bug Avoided: 4× wrapped/unwrapped coordinate mismatch eliminated`
- **Camera/Action:** Map loads, scale bar and UTM coordinate graticule render cleanly.

---

### Scene 4: Interactive Scientific Explorer (00:38 – 00:58)
- **Time Window:** 38.0 s – 58.0 s (Frames 1140 – 1739)
- **View:** Observation Explorer Canvas & Layer Controls
- **Key Visual Elements:**
  - Phase layer active: Viridis sequential colormap showing unwrapped phase in radians.
  - Switch layer to Coherence (Cividis colormap, 0.0 to 1.0).
  - Coherence threshold slider smoothly moves from 0.0 to 0.4, updating masked areas in real time.
  - Hover on M7.2 Foreshock marker: Tooltip displays local window median coherence of 0.406.
  - Hover on M7.5 Mainshock marker: Tooltip displays local window median coherence of 0.077 (severe coastal decorrelation).
  - Technical Overlays:
    - `Phase: radians (native Level-2 unit)`
    - `Coherence: 0.0 – 1.0 (measurement quality)`
    - `M7.2 Median Coherence: 0.406`
    - `M7.5 Median Coherence: 0.077`
    - `Epicentre Separation: 148.33 km`
- **Camera/Action:** Demonstrate real-time reactivity, pan slightly, show interactive tooltip responses.

---

### Scene 5: Scientific Integrity and Data Export (00:58 – 01:18)
- **Time Window:** 58.0 s – 78.0 s (Frames 1740 – 2339)
- **View:** Scientific Limitations & Data Export Sections
- **Key Visual Elements:**
  - Scientific Limitations Panel prominently framed:
    - Badge: `Scientific interpretation: NOT VALIDATED`
    - Explicit guardrails:
      1. Phase in radians (no metric displacement without sign convention & GNSS anchor).
      2. Atmospheric delay screen remains in unwrapped phase.
      3. Residual orbital ramps uncorrected in single pass.
      4. Single line-of-sight geometry cannot separate vertical from horizontal motion.
  - Data Export Suite:
    - GeoTIFF Export button (`EPSG:32619`)
    - PNG Quicklook with audit footer
    - JSON Provenance Metadata
    - Markdown Scientific Report
  - Click on "View Report" or download trigger demonstrating reproducible data packaging.
- **Camera/Action:** Scroll to limitations panel, pause for readability, then showcase export controls.

---

### Scene 6: Mission Closing (01:18 – 01:30)
- **Time Window:** 78.0 s – 90.0 s (Frames 2340 – 2699)
- **View:** Global Cinematic View / Aerospace Mission Card
- **Key Visual Elements:**
  - Return to the orbital mission visualization.
  - High-contrast closing title card:
    - `NISAR // EARTH IN MOTION`
    - `NASA International Space Apps Challenge 2026`
    - `Challenge: Dancing with the SARs`
    - `Repository: github.com/Aayushashsahu/LunaHorizon`
    - `Built with Pure Python · HDF5 · Canvas · 100% Offline Capable`
- **Camera/Action:** Held steady for full readability through second 90. Fade to black at 01:30.0.
