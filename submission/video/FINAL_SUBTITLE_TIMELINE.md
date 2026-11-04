# Demo Video Final Master — Subtitle Timeline & Layout Specifications

**Project:** NISAR // Earth in Motion  
**Repository:** https://github.com/Aayushashsahu/LunaHorizon  
**Master Subtitle Track:** `submission/video/subtitles_final.ass`  
**Master Video:** `artifacts/demo/nisar_earth_in_motion_FINAL.mp4`

---

## 1. Visual Safe-Zone Layout Specifications

- **Screen Resolution:** 1920 × 1080 (16:9 Full HD)
- **Primary Typeface:** Arial, 26 pt (approx 32 px height; high contrast, clean, universally supported by libass)
- **Top Caption Style (`TopCaption`):**
  - **Font / Size:** Arial, 25 pt (approx 30 px)
  - **Alignment:** 8 (Top-Center, y ≈ 26 px from top)
  - **Margins:** Left 140 px, Right 140 px, Top 26 px
  - **Purpose:** Used exclusively during Scene 4 interactive map inspection. It guarantees that the entire lower 50% of the screen (phase colormap legend at y ≈ 780px, coherence threshold slider at y ≈ 880px, and pixel readout bar at y ≈ 940px) remains **100% visible and completely unobstructed**.
- **Bottom Caption Style (`BottomCaption`):**
  - **Font / Size:** Arial, 26 pt (approx 32 px)
  - **Alignment:** 2 (Bottom-Center, MarginV = 32 px from bottom)
  - **Backing Box:** Translucent dark bounding backing (`&H80050C1C`, BorderStyle 3, 1.5 px outline)
  - **Margins:** Left 140 px, Right 140 px, Bottom 32 px (comfortably within the 10% television title safe zone)
- **Line Wrapping:** Max 2 lines per dialogue block with balanced `\N` linebreaks.

---

## 2. Word-for-Word Captions Schedule (0 ms Collision)

| Scene | Time Interval | Style | Word-for-Word Spoken Subtitle Text | Interface Safety Notes |
|---|---|---|---|---|
| **Scene 1: Orbit & Mission** | `00:00:00.80 --> 00:00:10.78` | `BottomCaption` | NISAR, the NASA–ISRO Synthetic Aperture Radar mission, operates on a 12-day repeat cycle.<br>Its L-band radar observes Earth's surface through clouds, smoke and darkness. | Clear of planetary globe and telemetry HUD badge. |
| **Scene 2: Research Challenge** | `00:00:11.80 --> 00:00:24.52` | `BottomCaption` | In June 2026, two major earthquakes struck northern Venezuela within 32 seconds.<br>We built an explorer using authentic NISAR Level-2 data from Track 162, covering June 13 to June 25. | Clear of research challenge cards and `~12 days` baseline stat. |
| **Scene 3: Granule Engineering** | `00:00:25.80 --> 00:00:38.20` | `BottomCaption` | The 2.34-gigabyte HDF5 product posed a key geospatial challenge.<br>Attached dimension scales eliminate a 4× coordinate mismatch, preserving true 80-metre EPSG:32619 georeferencing. | Clear of metadata DL list and verification checks. |
| **Scene 4A: Phase & Sampling** | `00:00:39.20 --> 00:00:48.50` | `TopCaption` (Top) | The explorer displays unwrapped phase in radians and coherence as data quality.<br>Full-resolution Float32 pixel inspection enables live coordinate and phase readout. | **Top placement:** Zero obstruction of phase colormap legend and live pixel readout. |
| **Scene 4B: Events & Reliability** | `00:00:48.50 --> 00:00:58.24` | `TopCaption` (Top) | M7.2 foreshock median coherence is 0.406; M7.5 mainshock is 0.077 (148 km apart).<br>This reflects measurement reliability, not physical damage. | **Top placement:** Zero obstruction of M7.2/M7.5 epicentres, threshold slider, and coordinates. |
| **Scene 5: Scientific Honesty** | `00:00:59.20 --> 00:01:10.50` | `BottomCaption` | Scientific honesty is essential. We do not claim phase as surface displacement or coherence loss as damage.<br>The system exports georeferenced GeoTIFFs, metadata, and scientific reports. | Clear of limitations checklist; visible during export hover. |
| **Scene 6: Mission Closing** | `00:01:14.50 --> 00:01:20.76` | `BottomCaption` | NISAR // Earth in Motion.<br>Making complex radar science accessible, transparent, and reproducible. | Clear of aerospace badges; finishes cleanly before closing card. |
| **Closing Card** | `00:01:21.50 --> 00:01:26.50` | *None* | *(No subtitles displayed; clean closing project card held for 4.5s)* | Clear, readable project credentials and GitHub URL. |
| **Outro Fade** | `00:01:26.50 --> 00:01:27.00` | *None* | *(0.5s smooth fade to black)* | Broadcast-standard outro. |
