# NISAR // Earth in Motion — Demonstration Video Narration Script

**Project:** NISAR // Earth in Motion  
**Challenge:** NASA Space Apps Challenge 2026 — Dancing with the SARs  
**Target Duration:** ~90 seconds (1 minute 30 seconds)  
**Tone:** Authoritative aerospace documentary, scientifically rigorous, precise, accessible  
**Audio Voice:** Local Text-to-Speech (Microsoft David Desktop / System.Speech, normalized stereo, 22.05 kHz / 48 kHz AAC)  

---

## Scene 1: Opening & Planetary Context (00:00 – 00:12 | 12s)

**On-screen Visuals:**
- Full-screen cinematic Earth reveal animation.
- Dual green orbital-tracking strokes sweep along the silhouette and meet at the North apex.
- 3D satellite orbit with real-time Gram–Schmidt telemetry and radar beam ground illumination.
- Title overlay: `NISAR // EARTH IN MOTION` | `Dancing with the SARs | NASA Space Apps 2026`
- Persistent illustrative disclaimer: `[ILLUSTRATIVE MISSION VISUALIZATION — 12-DAY ORBIT REPEAT CYCLE]`

**Narration (10.8s):**
> "NISAR, the NASA–ISRO Synthetic Aperture Radar mission, operates on a 12-day repeat cycle. Its L-band radar enables scientists to observe Earth's surface through clouds, smoke and darkness."

---

## Scene 2: The Research Challenge — Northern Venezuela 2026 (00:12 – 00:25 | 13s)

**On-screen Visuals:**
- Transition from mission view into the web application dashboard.
- Display observation catalog with the authentic NISAR Level-2 GUNW granule card tagged `REAL NISAR`.
- USGS ComCat reference earthquake sequence highlighted: M7.2 foreshock (San Felipe) and M7.5 mainshock (Catia La Mar), separated by 148.33 km within 32.2 seconds.
- Click "Open Explorer" to load the georeferenced raster scene.

**Narration (14.9s):**
> "In June 2026, two major earthquakes struck northern Venezuela within approximately 32 seconds. We built an interactive explorer using authentic NISAR Level-2 interferometric data from Ascending Track 162, covering June 13 to June 25."

---

## Scene 3: The Engineering Achievement — HDF5 Dimension-Scale Resolution (00:25 – 00:38 | 13s)

**On-screen Visuals:**
- Explorer loads the 80-meter resolution georeferenced grid (4,149 × 4,239 pixels, ~330 × 330 km).
- Technical callouts and metadata badges:
  - `NISAR L2 GUNW (2.34 GB HDF5)`
  - `Track 162 | Ascending | EPSG:32619`
  - `80 m posting`
  - `HDF5 DIMENSION_LIST scale resolution (avoiding 4× coordinate mismatch)`
- Graticule and dynamic scale bar updating on the canvas.

**Narration (15.5s):**
> "The original HDF5 product is approximately 2.34 gigabytes. A major engineering challenge was resolving its multiple spatial resolutions. By reading the coordinate scales attached to each raster, our pipeline avoids a four-times coordinate mismatch and preserves correct georeferencing."

---

## Scene 4: Interactive Scientific Explorer (00:38 – 00:58 | 20s)

**On-screen Visuals:**
- Native canvas rendering of the unwrapped interferometric phase layer in radians (Viridis colormap).
- Toggle to the Coherence layer (Cividis colormap, 0.0 to 1.0).
- Drag the coherence threshold slider from 0.0 to 0.4 and 0.6, showing dynamic real-time masking of decorrelated water and vegetation.
- Hover cursor over the USGS M7.2 foreshock marker: tooltip reveals 1.6 km window median coherence of 0.406.
- Hover cursor over the USGS M7.5 mainshock marker: tooltip reveals median coherence of 0.077 (coastal decorrelation).
- On-screen technical highlights:
  - `Phase: radians`
  - `Coherence: 0.0 – 1.0`
  - `M7.2 | Median coherence 0.406`
  - `M7.5 | Median coherence 0.077`
  - `Epicentre separation: 148.33 km`

**Narration (25.3s):**
> "The explorer presents unwrapped interferometric phase in radians and coherence as a measurement-quality indicator. Around the M7.2 event, the 1.6-kilometre median coherence is approximately 0.406. Around the M7.5 event, it is approximately 0.077. The epicentres are about 148 kilometres apart. These differences describe measurement reliability, not proof of earthquake damage."

---

## Scene 5: Scientific Integrity and Data Export (00:58 – 01:18 | 20s)

**On-screen Visuals:**
- Display the Scientific Limitations Panel:
  - Prominent badge: `Scientific interpretation: NOT VALIDATED`
  - Four explicit prerequisites listed: phase sign convention unresolved, no GNSS zero-anchoring, atmospheric delay screen present, residual orbital ramps.
- Navigate to the Data Export Suite.
- Highlight export capabilities: georeferenced GeoTIFFs (EPSG:32619), publication-grade PNG quicklooks with embedded provenance, machine-readable JSON metadata, and comprehensive Markdown scientific reports.
- Demonstrate download action and report preview.

**Narration (13.9s):**
> "Scientific honesty is built into the application. We do not label phase as centimetres of ground movement or claim that coherence loss proves damage. The system exports georeferenced GeoTIFFs, metadata and scientific reports for further investigation."

---

## Scene 6: Closing & Open-Source Reproducibility (01:18 – 01:30 | 12s)

**On-screen Visuals:**
- Return to cinematic planetary view with smooth horizon cruise.
- Aerospace mission presentation title card:
  - `NISAR // EARTH IN MOTION`
  - `NASA Space Apps Challenge 2026 — Dancing with the SARs`
  - `Repository: github.com/Aayushashsahu/LunaHorizon`
  - `Pure Python · HDF5 · Canvas · 100% Offline Capable · Zero Paid APIs`

**Narration (6.5s):**
> "NISAR // Earth in Motion. Making complex radar science more accessible, reproducible and understandable."

---

## Narration Timing & Sync Summary

| Scene | Timestamp Range | Allocated Duration | Spoken Duration (Rate 2) | Natural Pause / Transition |
|---|---|---|---|---|
| **Scene 1** | 00:00 – 00:12 | 12.0 s | 10.85 s | 1.15 s |
| **Scene 2** | 00:12 – 00:25 | 13.0 s | 14.88 s | 0.50 s (overlapping intro/outro) |
| **Scene 3** | 00:25 – 00:38 | 13.0 s | 15.48 s | 0.50 s |
| **Scene 4** | 00:38 – 00:58 | 20.0 s | 25.26 s | 0.50 s |
| **Scene 5** | 00:58 – 01:18 | 20.0 s | 13.94 s | 6.06 s (demonstrating export UI) |
| **Scene 6** | 01:18 – 01:30 | 12.0 s | 6.49 s | 5.51 s (held closing screen) |
| **TOTAL** | **00:00 – 01:30** | **90.0 s** | **86.90 s** | **3.10 s net buffer** |
