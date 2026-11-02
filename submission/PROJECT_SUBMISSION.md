# Project Submission — NISAR // Earth in Motion

**NASA Space Apps Challenge 2026**  
**Selected Challenge:** Dancing with the SARs  
**Team / Participant:** Aayush Sahu  
**Repository:** <https://github.com/Aayushashsahu/LunaHorizon>  
**Submission Date:** November 2026

---

## Project Title

**NISAR // Earth in Motion** — Interactive NISAR SAR Interferometry Explorer

---

## Short Description

An offline-capable, scientifically rigorous web application that ingests authentic NASA–ISRO NISAR Level-2 GUNW interferometric products, solves documented geospatial challenges from first principles, and presents phase, coherence, masks and earthquake event analysis through a cinematic mission interface.

---

## The Problem

Active microwave SAR data from NISAR is among the most powerful Earth-observation data ever collected. But it presents three steep barriers to accessibility:

1. **Raw complexity:** A single NISAR L-2 GUNW granule is 2.34 GB of multi-resolution HDF5 data with grids at 20 m and 80 m postings sharing the same file path structure.
2. **A documented coordinate bug:** Standard file-wide HDF5 dataset searches return the 20 m wrapped-phase coordinate vectors for the 80 m unwrapped-phase raster — a 4× dimension mismatch that crashes every naive processing attempt.
3. **Scientific overreach:** Many open-source projects convert interferometric phase directly to "centimetres of ground displacement" without verifying sign conventions, wavelength, corrections, or coherence — producing visually compelling but scientifically misleading results.

---

## Our Solution

NISAR // Earth in Motion solves all three problems:

### Engineering: The Dimension-Scale Fix

We read each raster's **own attached HDF5 dimension scales**, not a file-wide dataset search. This correctly produces 4239 × 4149 unwrapped coordinate vectors for the 4239 × 4149 unwrapped phase raster, with mathematically verified pixel-center alignment (round-trip error < 1 × 10⁻⁶ m).

### Science: Honest Presentation

- Unwrapped phase is displayed in **radians**, the unit declared by the product.
- Coherence is presented as a **quality indicator**, not displacement.
- No phase-to-displacement conversion is applied without disclosed sign convention, wavelength, and reference.
- Connected-component labels expose phase unwrapping reliability.
- The UI and reports clearly state that `scientific_interpretation_validated = false`.

### Experience: Accessible and Offline-First

- 100% offline after initial install — no paid APIs, no CDN, no cloud.
- Vanilla HTML5, Canvas, WebGL — no React, no Mapbox, no bundler.
- Cinematic 3D Earth reveal powered by WebGL and SVG.
- Continuous Gram–Schmidt orthonormal satellite orbit.
- Full keyboard accessibility and `prefers-reduced-motion` support.

---

## Innovation

1. **First-principles HDF5 dimension-scale reader** — documented in the existing NISAR GUNW product specification but not widely implemented.
2. **Multi-resolution coordinate grid disambiguation** — resolves the 4× dimension mismatch that makes standard tools fail on NISAR products.
3. **Genuine earthquake event corroboration** — windowed local coherence statistics around M7.2 and M7.5 epicentres using confirmed USGS ComCat coordinates.
4. **Scientific honesty by design** — the application is architecturally designed to prevent misleading displacement claims.
5. **Zero external dependencies** — the full processing pipeline and web application work without internet access on a standard consumer laptop.

---

## How NISAR is Used

The application ingests the authentic NISAR Level-2 Geocoded UNWRapped Interferogram (GUNW) product:

```
NISAR_L2_PR_GUNW_022_162_A_007_023_4000_SH_20260613T100656_
20260613T100731_20260625T100655_20260625T100730_P05023_N_F_J_001.h5
```

- **Track:** 162 (Ascending)
- **Reference acquisition:** 2026-06-13 10:06:56 UTC
- **Secondary acquisition:** 2026-06-25 10:06:55 UTC  
- **Temporal baseline:** 11 days 23:59:59 (~12.000 days; 1 nominal repeat cycle)
- **CRS:** WGS 84 / UTM zone 19N (EPSG:32619)
- **Grid:** 4239 × 4149 pixels at 80 m × 80 m posting
- **Center frequency:** 1,239,000,000.0 Hz ($1.239\text{ GHz}$, derived $\lambda \approx 0.2420\text{ m}$)
- **Flattening applied:** Ellipsoidal flattening and DEM topographic flattening applied to interferogram
- **Geolocation corrections applied:** Ionospheric range/azimuth and tropospheric wet/hydrostatic corrections applied during geocoding to improve pixel geolocation (atmospheric phase delay screens remain un-subtracted from the phase array)

The granule covers the same orbital pass (Ascending Track 162) and same nominal date pair (June 13 and June 25, 2026) that NASA/JPL analyzed as one of three InSAR tracks in their Earth Observatory study.

---

## Scientific Methodology

### What we measure

- **Unwrapped interferometric phase (radians):** The differential microwave phase between the two acquisitions after topographic and ellipsoidal flattening. Reported strictly in radians.
- **Coherence magnitude [0–1]:** The interferometric correlation between the two observations. High coherence = reliable phase; low coherence = noisy or decorrelated measurement.
- **Product validity mask:** Decoded 32-bit bitfield separating valid land, water, and masked pixels (9,175,108 valid pixels).
- **Connected components:** Phase unwrapping island labels revealing unwrapping continuity.
- **Valid pixel counts:** 9,175,108 pixels have valid phase and product mask (52.2% of the raster); 9,173,753 pixels have valid coherence. The 1,355 pixel difference reflects native `NaN` entries in the product's coherence raster along swath margins where phase is finite.

### What we do not do (and why)

| Claim | Why we avoid it |
|---|---|
| Phase = displacement in cm | Requires verified sign convention (unresolved in D-102272), reference pixel calibration against ground truth, and atmospheric screen subtraction |
| Low coherence = earthquake damage | Coherence loss has multiple physical causes (vegetation, steep terrain, wet ground, phase aliasing); it indicates measurement quality, not damage |
| Pattern = earthquake deformation | Atmospheric turbulence and orbital ramps are not independently removed |

### Reference comparison

NASA's published displacement study (July 2026) combined three tracks (A162, D54, and A61) with specialized deformation modeling. For this granule's center frequency ($1.239\text{ GHz}$, $\lambda \approx 0.2420\text{ m}$), one full $2\pi$ phase cycle corresponds to $\lambda / 2 \approx 12.10\text{ cm}$ of line-of-sight range change ($\approx 1.93\text{ cm/radian}$). NASA reported peak ground shifts up to ~60 cm in the coastal zone using multi-track InSAR analysis.

---

## Data Sources

| Data | Source | License |
|---|---|---|
| NISAR L-2 GUNW granule | NASA Earthdata / ASF | NASA Open Data Policy (Public Domain) |
| USGS earthquake events (us6000t7zc, us6000t7zp) | USGS ComCat | Public Domain |
| NASA Visible Earth textures | NASA Visible Earth | Public Domain / NASA Image Use Policy |
| Product specification | NASA JPL D-102272 | NASA Open Government Policy |

---

## Technical Implementation

- **Language:** Python 3.11+ (no heavyweight scientific stack required at runtime)
- **Core libraries:** h5py, numpy, rasterio, pyproj, shapely, pandas
- **Web stack:** Vanilla HTML5, CSS3, WebGL 1.0, ES Modules — zero bundlers or frameworks
- **Testing:** 93 automated pytest tests + Ruff lint; all passing on Python 3.11 and 3.12
- **CI:** GitHub Actions matrix CI (Python 3.11 and 3.12, mandatory Ruff)
- **License:** MIT

---

## Impact

- Makes authentic NISAR L-band InSAR analysis accessible on a standard laptop with no internet dependency.
- Demonstrates the dimension-scale solution to a documented bug in naive NISAR HDF5 access.
- Provides a reproducible, open-source starting point for community NISAR data exploration.
- Models scientific integrity in the display of SAR interferometric products.

---

## Accessibility

- `@media (prefers-reduced-motion: reduce)` — instant static fallback, no animation
- Keyboard navigable throughout
- HTML semantic structure maintained
- Scale bar and coordinate display in the observation explorer

---

## Reproducibility

```powershell
git clone https://github.com/Aayushashsahu/LunaHorizon.git
cd LunaHorizon
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest -v          # 93 tests pass
python -m nisar_eim serve --port 8000
# Open http://127.0.0.1:8000/
```

The Venezuela processed observation (`data/processed/venezuela/`) is committed to the repository and the application loads immediately without the raw 2.34 GB HDF5 file.

---

## Limitations

- The raw NISAR granule (2.34 GB) is gitignored and must be separately downloaded for re-processing.
- LOS displacement is not displayed because an absolute reference pixel has not been independently validated against GPS ground truth.
- The application covers a single interferometric pair; multi-track decomposition into vertical and horizontal components requires additional acquisitions.
- Browser end-to-end tests require headless Chrome and are not run in CI; they have been locally verified.
- `scientific_interpretation_validated` is deliberately kept `false` throughout.

---

## Team / Participant

Aayush Sahu — independent student participant.

*This is an independent open-source project created for the NASA Space Apps Challenge 2026. It is not an official NASA or ISRO product and has not been endorsed by NASA, ISRO, or USGS.*
