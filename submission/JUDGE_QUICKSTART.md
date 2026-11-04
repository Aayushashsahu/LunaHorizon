# Judge Quickstart — NISAR // Earth in Motion

**Repository:** <https://github.com/Aayushashsahu/LunaHorizon>  
**Challenge:** NASA Space Apps 2026 — Dancing with the SARs

This guide gets you from a fresh clone to a running application in under 5 minutes.

---

## Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Python | 3.11 or 3.12 | Required |
| Git | Any recent | Required |
| Internet | Optional | Only needed for initial clone and pip install |

---

## Installation (Windows PowerShell)

```powershell
# 1. Clone the repository
git clone https://github.com/Aayushashsahu/LunaHorizon.git
cd LunaHorizon

# 2. Create a virtual environment
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3. Install dependencies (including developer/test dependencies)
pip install -e ".[dev]"

# 4. Verify the installation
python -m nisar_eim list
```

Expected output from step 4:
```
  venezuela        NISAR L2 GUNW  Track 162  2026-06-13 → 2026-06-25  80m
  sample_demo      NISAR L2 GUNW  [sample]   [pre-launch sample]       80m
```

## Installation (macOS / Linux)

```bash
git clone https://github.com/Aayushashsahu/LunaHorizon.git
cd LunaHorizon
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -m nisar_eim list
```

---

## Starting the Application

```powershell
python -m nisar_eim serve --port 8000
```

Open **[http://127.0.0.1:8000/](http://127.0.0.1:8000/)** in Chrome, Firefox, or Edge.

The application is 100% offline after installation. No internet connection is required.

---

## Recommended Demo Flow (5 minutes)

### Step 1: Cinematic Introduction (30 seconds)

- Let the page load fully — a cinematic Earth reveal animation plays automatically.
- Watch the 3D Earth scale up from space, with two luminous green tracking strokes sweeping the globe's silhouette.
- The satellite orbit (Gram–Schmidt orthonormal basis) and illustrative radar sweep begin.
- Look for the mission HUD: **ORBIT REPEAT CYCLE · 12 DAYS** — this is NISAR's actual nominal repeat cycle.

### Step 2: Enter the Observation Explorer (1 minute)

- Click **"Explore Observations"** to trigger the radar wipe transition.
- The observation explorer loads with the **Venezuela 2026** observation pre-selected.
- You will see a 330 × 330 km raster of Northern Venezuela rendered at 80 m resolution.

### Step 3: Explore the Science Layers (2 minutes)

- **Phase layer** (default): Unwrapped interferometric phase values displayed in radians (the native unit of the Level-2 product). The colormap visualizes spatial phase differences across the scene after ellipsoidal and topographic flattening. Not every phase pattern represents ground displacement: phase variations inherently combine potential surface motion with atmospheric path delays, orbital trajectory errors, and noise.
- **Coherence layer**: Toggle using the layer button. This shows measurement quality — 0 = unreliable, 1 = perfect similarity between acquisitions.
- **Coherence slider**: Drag the threshold slider to filter pixels. At threshold 0.4, approximately 16.7% of pixels (2.94 million) remain — the highest-quality measurements.
- **Hover / click** anywhere on the raster to see exact geodetic coordinates, UTM coordinates, phase value, and coherence.

### Step 4: Event Epicentres (1 minute)

- Look for the two earthquake epicentre markers on the map.
- The two epicentres are separated by **148.3 km** along northern Venezuela (from San Felipe in Yaracuy to Catia La Mar near Caracas/La Guaira).
- **M7.2 foreshock** (west): Local 1.6 km median coherence ≈ 0.406 — moderate coherence, usable interferometric measurement.
- **M7.5 mainshock** (east): Local 1.6 km median coherence ≈ 0.077 — heavily decorrelated, low measurement reliability.
- The statistics table shows the event assessment at three spatial windows (0.16 km, 1.6 km, and 10 km).

### Step 5: Export (30 seconds)

- Click **Export GeoTIFF** to download a georeferenced phase raster (EPSG:32619).
- Click **Export Metadata** to download the full JSON provenance report.
- Click **Export Report** to download the Markdown scientific report.

---

## Expected Limitations

| Limitation | Explanation |
|---|---|
| Phase is in radians, not cm | Converting phase to calibrated metric displacement requires resolving four prerequisites: (1) an authoritative phase sign convention (unresolved in product spec D-102272), (2) reference zero-anchoring against ground truth (e.g. continuous GNSS), (3) subtraction of atmospheric delay contributions (tropospheric water vapor and ionospheric variations remain in the phase array), and (4) removal of residual orbital trajectory error ramps. In addition, decomposing 1D line-of-sight motion into vertical and horizontal components requires multiple viewing geometries. |
| No live data | The application serves pre-processed products from `data/processed/` — no live NISAR download |
| Raw HDF5 file not included | The 2.34 GB raw granule is gitignored; the pre-processed observation is committed |
| Browser E2E tests | Require headless Chrome; not run in CI but verified locally |

---

## Running the Test Suite

```powershell
pip install -e ".[dev]"
pytest -v                                    # 106 tests, ~16–20 seconds
python -m ruff check src tests               # Lint — all checks pass
```

---

## Troubleshooting

| Problem | Solution |
|---|---|
| `No module named nisar_eim` | Run `pip install -e .` from the repo root with the venv active |
| Port 8000 in use | Try `--port 8001` or any free port |
| White screen in browser | Ensure the server is running; try hard-refresh (Ctrl+Shift+R) |
| Slow initial load | The first observation load reads several large PNG preview files (~12 MB total) |
