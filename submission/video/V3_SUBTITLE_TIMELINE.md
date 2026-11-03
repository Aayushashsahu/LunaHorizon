# Demo Video V3 — Subtitle Timeline & Layout Specification

**Project:** NISAR // Earth in Motion  
**Format:** Advanced SubStation Alpha (.ass)  
**Layout:** 1920 × 1080 Full HD Safe Area  
**Typography:** Arial 26 pt, Bold, White (`&H00FFFFFF`), Black Outline 1.5 pt (`&H00000000`)  
**Backdrop:** Translucent dark aerospace container box (`&H80050C1C`, BorderStyle 3)  
**Placement:** Alignment 2 (Bottom Centre), Margins: Left 120 px, Right 120 px, Bottom 32 px  

---

## Scene Subtitle Schedule

| Scene # | Start Time | End Time | Duration | Captioned Text | Visual Safe-Area Clearance |
|---|---|---|---|---|---|
| **Scene 1** | `00:00:00.80` | `00:00:10.80` | 10.00 s | *NISAR, the NASA–ISRO Synthetic Aperture Radar mission, operates on a 12-day repeat cycle.<br>Its L-band radar observes Earth's surface through clouds, smoke and darkness.* | Clear of Earth globe and HUD badge |
| **Scene 2** | `00:00:12.50` | `00:00:25.20` | 12.70 s | *In June 2026, two major earthquakes struck northern Venezuela within 32 seconds.<br>We built an explorer using authentic NISAR Level-2 data from Track 162, covering June 13 to June 25.* | Clear of observation card details |
| **Scene 3** | `00:00:26.00` | `00:00:38.40` | 12.40 s | *The 2.34-gigabyte HDF5 product posed a key geospatial challenge.<br>Attached dimension scales eliminate a 4× coordinate mismatch, preserving true 80-metre EPSG:32619 georeferencing.* | Clear of canvas map area |
| **Scene 4** | `00:00:40.00` | `00:00:59.00` | 19.00 s | *The explorer displays unwrapped phase in radians and coherence as data quality.<br>M7.2 foreshock median coherence is 0.406; M7.5 mainshock is 0.077 (148 km apart). This reflects reliability, not damage.* | Sits 32 px from bottom; threshold slider (y=920), epicentre markers (y=510-525), and legends are 100% unobstructed |
| **Scene 5** | `00:01:00.50` | `00:01:12.00` | 11.50 s | *Scientific honesty is essential. We do not claim phase as surface displacement or coherence loss as damage.<br>The system exports georeferenced GeoTIFFs, metadata, and scientific reports.* | Clear of scientific disclaimer table and export buttons |
| **Scene 6** | `00:01:19.00` | `00:01:25.30` | 6.30 s | *NISAR // Earth in Motion.<br>Making complex radar science accessible, transparent, and reproducible.* | Sits cleanly beneath closing card badges and repository URL |
