# Demo Video V2 — Master Narration Script

**Project:** NISAR // Earth in Motion  
**Target Duration:** 90.000 seconds  
**Total Speech Duration:** 71.70 seconds (18.30 seconds breathing room & transitions)  
**Sample Rate / Channels:** 48,000 Hz Stereo  
**Integrated Loudness:** -15.3 LUFS  

---

## Scene-by-Scene Narration & Subtitle Sync

### Scene 1: Planetary Opening & Mission Orbit [0.0s – 12.0s]
- **Speech Window:** `00:00:00.80 --> 00:00:10.78` (Duration: 9.98s)
- **Subtitle Display:** `00:00:00.80 --> 00:00:11.00`
- **Narration:**
  > "NISAR, the NASA–ISRO Synthetic Aperture Radar mission, operates on a 12-day repeat cycle. Its L-band radar observes Earth's surface through clouds, smoke and darkness."
- **Visual Action:**
  Earth reveal animation scales the globe into view; dual orbital-tracking strokes trace the silhouette; mission HUD indicates ~12-day repeat cycle and 1.239 GHz L-band frequency.

---

### Scene 2: Research Challenge — Northern Venezuela 2026 [12.0s – 26.0s]
- **Speech Window:** `00:00:12.80 --> 00:00:25.52` (Duration: 12.72s)
- **Subtitle Display:** `00:00:12.80 --> 00:00:25.80`
- **Narration:**
  > "In June 2026, two major earthquakes struck northern Venezuela within 32 seconds. We built an explorer using authentic NISAR Level-2 data from Track 162, covering June 13 to June 25."
- **Visual Action:**
  Dashboard view scrolls smoothly to observation cards; northern Venezuela 2026 card highlighted with cyan illumination. HUD details the doublet timeline and 11d 23h 59m acquisition baseline.

---

### Scene 3: Engineering Achievement — HDF5 Dimension Scales [26.0s – 40.0s]
- **Speech Window:** `00:00:26.80 --> 00:00:39.20` (Duration: 12.40s)
- **Subtitle Display:** `00:00:26.80 --> 00:00:39.50`
- **Narration:**
  > "The 2.34-gigabyte HDF5 product posed a key geospatial challenge. Attached dimension scales eliminate a 4× coordinate mismatch, preserving true 80-metre EPSG 32619 georeferencing."
- **Visual Action:**
  Holographic transition into observation explorer; 4,149 x 4,239 pixel unwrapped interferogram rendered on canvas. HUD highlights 80m posting and EPSG:32619 coordinate resolution.

---

### Scene 4: Interactive Scientific Explorer [40.0s – 65.0s]
- **Speech Window:** `00:00:41.00 --> 00:01:00.04` (Duration: 19.04s)
- **Subtitle Display:** `00:00:41.00 --> 00:01:00.50`
- **Narration:**
  > "The explorer displays unwrapped phase in radians and coherence as data quality. The M 7.2 foreshock shows median coherence of 0.406, while the M 7.5 mainshock, 148 kilometers away, drops to 0.077. This reflects measurement reliability, not structural damage."
- **Visual Action:**
  - `40–45s`: Phase map display in Viridis sequential colormap; mouse cursor navigates interferogram.
  - `45–52s`: Active layer switch to Coherence; real CDP mouse drags coherence threshold slider from 0.4 to 0.6 and back, filtering unreliable pixels.
  - `52–58s`: Mouse hovers over M7.2 foreshock epicentre (Yaracuy); inspection tooltip displays 0.406 median coherence (usable phase).
  - `58–65s`: Mouse inspects M7.5 mainshock (coastal Catia La Mar); inspection tooltip displays 0.077 median coherence (severe decorrelation).

---

### Scene 5: Scientific Honesty & Data Export [65.0s – 79.0s]
- **Speech Window:** `00:01:06.00 --> 00:01:17.30` (Duration: 11.30s)
- **Subtitle Display:** `00:01:06.00 --> 00:01:17.50`
- **Narration:**
  > "Scientific honesty is essential. We do not claim phase as surface displacement or coherence loss as damage. The system exports georeferenced GeoTIFFs, metadata, and scientific reports."
- **Visual Action:**
  Page scrolls through scientific guardrails notice (no GPS reference pixel anchor, unverified sign conventions, atmospheric delays present); export panel showcases GeoTIFF, quicklook PNG, JSON metadata, and Markdown report downloads.

---

### Scene 6: Mission Closing & Open-Source Integrity [79.0s – 90.0s]
- **Speech Window:** `00:01:20.50 --> 00:01:26.76` (Duration: 6.26s)
- **Subtitle Display:** `00:01:20.50 --> 00:01:28.00`
- **Narration:**
  > "NISAR // Earth in Motion. Making complex radar science accessible, transparent, and reproducible."
- **Visual Action:**
  Clean, full-screen aerospace closing card displays repository URL, mission credentials, and technical badges at 100% opacity until frame 2700 (90.000s). No black ending frames.
