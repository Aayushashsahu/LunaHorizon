# NISAR // Earth in Motion — v0.1.0 Release

Initial release candidate of **NISAR // Earth in Motion** for the **NASA International Space Apps Challenge 2026 (*Dancing with the SARs*)**.

### Key Highlights
* **Authentic NISAR Level-2 Processing:** Reads and georeferences real NASA-ISRO NISAR Level-2 Geocoded UNWRapped Interferogram (GUNW) HDF5 data at 80 m spatial resolution (EPSG:32619).
* **Geospatial Dimension-Scale Resolution:** Solves the 4× coordinate mismatch bug from legacy scripts by reading HDF5 `DIMENSION_LIST` scales attached directly to the unwrapped raster, guaranteeing exact pixel-center registration.
* **100% Offline-Capable Web Experience:** Built on Python's standard library HTTP server and vanilla HTML5/WebGL/SVG. Operates completely without external tile servers, CDNs, or GPUs.
* **Cinematic Mission Experience:** Features a smooth planetary reveal animation with dual silhouette-tracking arcs, an illustrative radar acquisition pass, and continuous Gram–Schmidt orthonormal satellite orbit.
* **Multi-Layer Quality Explorer:** Interactive canvas map with instant switching between unwrapped phase (radians), coherence magnitude (0–1), 32-bit decoded subswath/water masks, and connected phase components.
* **Dynamic Coherence Thresholding:** Live slider (0.0 to 0.8) and threshold table with real-time coverage recalculation.
* **Independent Event Corroboration:** Integrates USGS ComCat records for the June 2026 Venezuela M7.2 / M7.5 earthquake sequence with windowed coherence assessment.
* **Scientific Integrity:** Displays unwrapped phase in radians; deliberately refrains from uncalibrated displacement conversions or unverified causation claims.
* **Testing:** Verified with 93 passing Python tests, 36 browser smoke tests, and responsive viewports from 1440px desktop down to 390px mobile.

### Quickstart
```bash
git clone https://github.com/Aayushashsahu/LunaHorizon.git
cd LunaHorizon
python -m pip install -r requirements.txt
python -m pip install -e .
python -m nisar_eim serve --port 8000
```
Open **http://127.0.0.1:8000/** in your browser.
