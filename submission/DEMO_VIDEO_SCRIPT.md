# Demo Video Script — NISAR // Earth in Motion

**Project:** NISAR // Earth in Motion  
**Challenge:** NASA Space Apps Challenge 2026 — Dancing with the SARs  
**Target Duration:** 90 seconds  
**Created:** 2026-11-01

---

## Production Notes

- Record at 1920×1080, 60 fps
- Use screen capture + separate audio track
- Chrome browser, zoom 100%, full screen
- App running locally: `python -m nisar_eim serve --port 8000`
- Narration in a clear, confident tone — not rushed

---

## Script

### [0:00–0:12] — Opening: The Satellite Pass

**On-screen action:** App loads. Cinematic Earth reveal animation plays — Earth scales up from space, two green orbital-tracking strokes sweep the globe's silhouette.

**Narration:**
> "NISAR — the NASA-ISRO Synthetic Aperture Radar satellite — orbits Earth every 12 days, transmitting L-band microwaves that pierce clouds, smoke, and darkness to measure millimeter-scale changes in the ground beneath us."

**Shot:** Full-screen hero with Earth reveal, satellite cruise visible, dual arc strokes converging at the north pole.

---

### [0:12–0:20] — The Mission

**On-screen action:** Earth completes its reveal, orbital cruise continues. The mission HUD displays ORBIT REPEAT CYCLE · 12 DAYS.

**Narration:**
> "On 24 June 2026, two major earthquakes — magnitude 7.2 and 7.5 — struck northern Venezuela within 32 seconds of each other. NISAR had already captured radar images of that exact region just days before."

**Shot:** Steady mission orbit view, radar sweep arc over northern Venezuela region.

---

### [0:20–0:35] — Transition to Science

**On-screen action:** Click "Explore Observations" button. Holographic radar wipe animation plays, transitioning from the globe to the observation explorer.

**Narration:**
> "We processed an authentic NISAR Level-2 interferogram — a 2.34-gigabyte product covering Northern Venezuela, Track 162. Ingesting it required solving a significant geospatial challenge: the HDF5 file stores coordinate grids at four times the wrong resolution unless you read the attached dimension scales directly."

**Shot:** Radar wipe animation, then the observation explorer loads with the Venezuela product selected.

---

### [0:35–0:55] — The Observation Explorer

**On-screen action:** Phase layer displayed. Toggle to Coherence. Move the coherence slider from 0.4 to 0.0 and back. Hover near the M7.2 foreshock epicentre marker.

**Narration:**
> "This is the unwrapped interferometric phase — the raw measurement in radians over an 80-metre resolution, 330 by 330-kilometre grid. The coherence layer tells us where measurements are reliable. The M7.2 foreshock site shows moderate coherence — 0.406 median at 1.6 kilometres — meaning the radar backscatter was stable and the phase relationship is preserved. The M7.5 mainshock, approximately 148 kilometres to the east-northeast near the coast, shows local median coherence of 0.077 — indicating severe decorrelation where the interferometric phase is noisy and unreliable."

**Shot:** Phase map → coherence map → coherence slider moving → epicentre hover tooltip.

---

### [0:55–1:10] — The Scientific Assessment

**On-screen action:** Scroll to the event assessment panel. Show the two earthquake epicentre markers and their local statistics table.

**Narration:**
> "The foreshock region maintains usable interferometric correlation, while the coastal mainshock region decorrelates. This demonstrates why quality masking is essential in radar science: before attempting any geophysical interpretation, scientists must examine where interferometric phase is physically trustworthy rather than treating all pixels equally."

**Shot:** Epicentre markers on map, local statistics table visible — foreshock coherence ~0.41, mainshock coherence ~0.077.

---

### [1:10–1:25] — Honesty and Impact

**On-screen action:** Show the export panel, then the scientific guardrails notice visible in the UI. Optional: show a GeoTIFF download being initiated.

**Narration:**
> "We present the phase in radians, not as centimetres of ground sinking or rising — because without verifying the sign convention and reference pixel against ground truth, that translation would be misleading. The data is available for export as georeferenced GeoTIFFs, JSON metadata, and Markdown reports — all offline, no cloud required."

**Shot:** Export buttons, data disclaimer notice, one-click JSON metadata download.

---

### [1:25–1:30] — Closing

**On-screen action:** Return to mission orbit hero view.

**Narration:**
> "NISAR // Earth in Motion — making complex radar science accessible, reproducible, and honest."

**Shot:** Mission orbit with the LunaHorizon / NISAR branding.

---

## Recording Instructions

```bash
# 1. Start the application
python -m nisar_eim serve --port 8000

# 2. Open Chrome
#    Navigate to http://127.0.0.1:8000/
#    Set zoom to 100%, fullscreen

# 3. Recommended tools
#    Windows: OBS Studio (free) — record window + desktop audio
#    macOS: QuickTime Player + Soundflower or OBS
#    Resolution: 1920×1080

# 4. Post-production
#    Trim to 90s
#    Add optional light background music (use NASA public domain tracks)
#    Upload to YouTube (unlisted) and paste URL in submission form
```

## Suggested Screenshots for Submission

1. Cinematic Earth reveal (approach/scale-up phase)
2. Mission orbit with dual green tracking strokes
3. Observation explorer — phase layer, Venezuela
4. Observation explorer — coherence layer, threshold slider
5. Event epicentre overlay with statistics panel
