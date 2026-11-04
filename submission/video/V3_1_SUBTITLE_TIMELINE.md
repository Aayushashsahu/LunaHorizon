# Demo Video V3.1 — Subtitle Timeline & Layout Specifications

**Project:** NISAR // Earth in Motion  
**Repository:** https://github.com/Aayushashsahu/LunaHorizon  
**Master Subtitle File:** `subtitles_v3_1.ass` (mirrored in `submission/video/subtitles_v3_1.ass`)

---

## 1. Visual Safe-Zone Layout Specifications

- **Screen Resolution:** 1920 × 1080 (16:9 Full HD)
- **Primary Typeface:** Arial, 25 pt (Clean, universally readable, high contrast)
- **Top Caption Style (`TopCaption`):** Arial, 24 pt, Alignment 8 (Top-Center, y ≈ 24px)
  - **Purpose:** Used exclusively during Scene 4 map inspection so that the map canvas, earthquake markers, threshold slider (y ≈ 900px), and pixel readout bar (y ≈ 950px) remain **100% visible and completely unobstructed**.
- **Bottom Caption Style (`Default`):** Arial, 25 pt, Alignment 2 (Bottom-Center, MarginV = 24px)
  - **Box Style:** Translucent dark bounding backing (`&H80050C1C`, BorderStyle 3, 1.5 px outline)
  - **Margins:** Left 140 px, Right 140 px, Bottom 24 px (Comfortably within the 10% television title safe zone)

---

## 2. Word-for-Word Captions Schedule (0 ms Collision)

| Scene | Time Interval | Style | Word-for-Word Spoken Subtitle Text | Interface Safety Notes |
|---|---|---|---|---|
| **Scene 1: Orbit** | `00:00:00.80 --> 00:00:10.78` | `Default` (Bottom) | NISAR, the NASA–ISRO Synthetic Aperture Radar mission, operates on a 12-day repeat cycle.<br>Its L-band radar observes Earth's surface through clouds, smoke and darkness. | Clear of planetary globe and HUD badge. |
| **Scene 2: Challenge** | `00:00:11.70 --> 00:00:24.42` | `Default` (Bottom) | In June 2026, two major earthquakes struck northern Venezuela within 32 seconds.<br>We built an explorer using authentic NISAR Level-2 data from Track 162, covering June 13 to June 25. | Clear of research challenge cards and `~12 days` baseline stat. |
| **Scene 3: Grid** | `00:00:25.30 --> 00:00:37.70` | `Default` (Bottom) | The 2.34-gigabyte HDF5 product posed a key geospatial challenge.<br>Attached dimension scales eliminate a 4× coordinate mismatch, preserving true 80-metre EPSG:32619 georeferencing. | Clear of metadata DL list and verification checks. |
| **Scene 4A: Phase** | `00:00:38.60 --> 00:00:48.00` | `TopCaption` (Top) | The explorer displays unwrapped phase in radians and coherence as data quality. | **Top placement:** Zero obstruction of phase colormap legend and live pixel readout. |
| **Scene 4B: Events** | `00:00:48.00 --> 00:00:57.64` | `TopCaption` (Top) | M7.2 foreshock median coherence is 0.406; M7.5 mainshock is 0.077 (148 km apart).<br>This reflects reliability, not damage. | **Top placement:** Zero obstruction of M7.2/M7.5 epicentres, threshold slider, and coordinates. |
| **Scene 5: Honesty** | `00:00:58.60 --> 00:01:09.90` | `Default` (Bottom) | Scientific honesty is essential. We do not claim phase as surface displacement or coherence loss as damage.<br>The system exports georeferenced GeoTIFFs, metadata, and scientific reports. | Clear of limitations checklist; visible during export hover. |
| **Scene 6: Closing** | `00:01:14.00 --> 00:01:20.26` | `Default` (Bottom) | NISAR // Earth in Motion.<br>Making complex radar science accessible, transparent, and reproducible. | Clear of aerospace badges; holds cleanly until card fade. |
