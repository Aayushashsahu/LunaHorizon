# NISAR // Earth in Motion

**See how Earth changes. Understand what the radar reveals.**

A local, offline-capable application that turns NASA-ISRO NISAR Level-2
Geocoded UNWRapped Interferogram (GUNW) products into an interpretable,
scientifically honest exploration experience: georeferenced phase and coherence
quicklooks, quality masks, statistics, event verification against independent
USGS locations, and a plain-language account of what the data does **not**
prove.

Built for the NASA Space Apps Challenge (event: 14-15 November 2026) on a
student laptop: CPU only, ₹0 budget, no paid APIs, no GPU, no cloud, no
required internet connection after processing.

## Status

| Area | State |
| --- | --- |
| Real granule processed end to end | **yes** — L2 GUNW, track 162, frame 7, 2026-06-13 -> 2026-06-25 |
| Georeferencing | validated from the product's own dimension scales (EPSG:32619, 80 m posting, round-trip 0.00e+00) |
| Footprint vs. event | both June 24, 2026 USGS epicentres fall inside the raster; nearest valid pixel 0.0 km with coherence 0.708 |
| Phase -> displacement conversion | **deliberately not implemented** (see `docs/SCIENTIFIC_METHOD.md` §5) |
| Earthquake-causation claim | **not made** — the output is presented as an exploratory observation |
| Test suite | 77 tests passing, including the exact 4x georeferencing regression case |

## The bug this project started from

```text
python scripts\quicklook_gunw_georef_v3.py <granule> phase
ValueError: Raster shape (4149, 4239) does not match coordinate lengths (y=16596, x=16956)
```

`16596 = 4 x 4149` and `16956 = 4 x 4239`: a single GUNW granule contains a
20 m wrapped grid (16596 x 16956) *and* an 80 m unwrapped grid (4149 x 4239),
each with its own coordinate vectors.  The old script resolved coordinates by a
file-wide basename search, so HDF5's alphabetical ordering handed it the **wrapped
grid's coordinates** for the **unwrapped raster** — a four-times mismatch.

Fixed properly (no division by four, no subsampling, no invented bounding box):
coordinates now come from the HDF5 dimension scales attached to the raster
itself, with cross-checks against the grid's own `projection` and spacing
datasets.  Full explanation: `docs/SCIENTIFIC_METHOD.md` §2.
Regression tests: `tests/test_geospatial.py`, `tests/test_product_reader.py`.

## Quick start (Windows PowerShell)

```powershell
cd "D:\Nasa hackton"
py -3.11 -m venv .venv          # only if .venv does not exist yet
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt

pytest                          # full suite, no network, no 2.34 GB file needed
```

## Working with the data

```powershell
$g = "data\raw\nisar_venezuela\NISAR_L2_PR_GUNW_022_162_A_007_023_4000_SH_20260613T100656_20260613T100731_20260625T100655_20260625T100730_P05023_N_F_J_001.h5"

# 1. metadata + georeferencing report (fast, reads no raster bodies)
python -m nisar_eim inspect $g

# 2. validation record: checks, event overlap, raw-file integrity
python -m nisar_eim validate $g --out data\processed\venezuela

# 3. quicklooks, GeoTIFFs, metadata.json, report.md
python -m nisar_eim process $g --id venezuela          # add --force to reprocess

# 4. list processed observations
python -m nisar_eim list

# 5. launch the application
python -m nisar_eim serve --port 8000
#    then open http://127.0.0.1:8000/
```

Outputs land in:

```text
data/processed/venezuela/
    phase.png  coherence.png          quicklooks with title, dates, units, legend, provenance footer
    phase.tif  coherence.tif          GeoTIFFs: EPSG:32619, 4149 x 4239, NaN nodata, band descriptions
    metadata.json                     machine-readable provenance, statistics, checks, event assessment
    report.md                         human-readable scientific report
    validation.json  validation.md    validation record (also written by `validate`)
    preview/                          WGS84 display images and the coherence preview used by the UI
```

The pre-launch sample product is processed the same way:

```powershell
python -m nisar_eim process data\demo\sample_gunw.h5 --id sample_demo
```

It appears in the interface tagged **sample** (2008 dates, predates the NISAR
launch) and is never mixed with the real observation.

### Legacy scripts

`scripts/quicklook_gunw.py`, `scripts/quicklook_gunw_georef.py` and
`scripts/quicklook_gunw_georef_v3.py` are deprecated compatibility shims that
print a notice and delegate to the canonical pipeline.  `scripts/inspect_gunw.py`,
`audit_gunw_structure.py`, `probe_gunw_metadata.py`, `report_gunw_metadata.py`
are research/inspection utilities; the download scripts only fetch data when
explicitly asked.

## The application

```powershell
python -m nisar_eim serve --port 8000
```

* **Dashboard** — project purpose, plain-language NISAR/InSAR primer, available
  observations, acquisition dates, per-check validation states (dataset found,
  metadata inspected, raster readable, georeferencing validated, footprint
  validated, scientific interpretation validated), coverage, reference events,
  persistent limitations.
* **Observation explorer** — canvas map of the georeferenced raster with layer
  tabs (phase, coherence, quality, connected components), footprint outline,
  graticule, scale bar, USGS epicentre markers, zoom/pan, hover and pinned pixel
  readout (values, coordinates, units), coherence-threshold slider with live
  coverage statistics, threshold table, statistics panel, metadata panel, export
  links for every artefact, and a persistent scientific-limitations panel.
* Works fully offline once processed; no basemap tiles, no CDN, no framework.
* Badges are earned: `scientific_interpretation_validated` shows
  **not validated** for this dataset, because no displacement conversion or
  causation claim has been validated.

## Project structure

```text
data/demo/            public sample GUNW (pipeline smoke test)
data/raw/             downloaded NISAR files (never rewritten, gitignored)
data/processed/       derived artefacts (gitignored)
docs/                 SCIENTIFIC_METHOD.md, DATA_VALIDATION.md, ARCHITECTURE.md
notebooks/            exploratory analysis
research/             scientific notes, decisions, extracted reference documents
scripts/              CLI utilities and deprecated shims
src/nisar_eim/        the package
tests/                pytest suite (synthetic HDF5 fixtures, no big downloads)
```

## Testing

```powershell
pytest                 # 77 tests: georeferencing regression, mask decoding,
                       # statistics, rendering, pipeline, web API + HTTP smoke
pytest tests/test_geospatial.py -k four_times    # just the reported bug case
```

The suite builds small synthetic GUNW HDF5 files (including one with the exact
four-times coordinate condition), so it runs in seconds without the 2.34 GB
granule and without network access.

## Scientific guardrails

* Unwrapped phase is displayed in **radians**, the unit declared by the product.
  It is labelled "NOT a displacement map" in the PNG footer, the GeoTIFF tags,
  `metadata.json`, `report.md` and the UI.
* Coherence is a **quality indicator**, never a displacement measurement; the
  threshold is user-controlled and always visible, and exported GeoTIFFs keep
  all valid pixels.
* The June 24, 2026 epicentres are verified against the raster footprint and
  local coherence from an independent USGS record; date bracketing alone is
  never treated as evidence.
* No phase-to-displacement conversion is applied: the product does not document
  the sign convention, and the required atmospheric/tidal corrections are only
  partially described.  The conditions for enabling one are listed in
  `docs/SCIENTIFIC_METHOD.md` §5.
* The raw granule is opened read-only; validation records its SHA-256
  (`ae5fbc528b99ba263f2040e56c225762c740eeb8476a75e598e888eb0b838f65`) and
  confirms it is unchanged after every run.

## Authoritative references

- NASA NISAR data overview: https://science.nasa.gov/mission/nisar/data/
- NASA NISAR sample data: https://science.nasa.gov/mission/nisar/sample-data/
- ASF NISAR Data User Guide: https://nisar-docs.asf.alaska.edu/
- NISAR L2 GUNW product specification (D-102272): https://nisar.asf.earthdatacloud.nasa.gov/NISAR-SAMPLE-DATA/DOCS/NISAR_D-102272_RevE_NASA_SDS_Product_Specification_L2_GUNW_Nov8_2024_w-sigs.pdf
- ASF data search / Vertex: https://search.asf.alaska.edu/
- USGS event pages: https://earthquake.usgs.gov/earthquakes/eventpage/us6000t7zc · https://earthquake.usgs.gov/earthquakes/eventpage/us6000t7zp
- NASA Earth Observatory: https://science.nasa.gov/earth/earth-observatory/where-venezuelas-earthquakes-shifted-the-ground/

## Known limitations

- Only one production granule subtype (L2 GUNW, frequency A, HH) has been
  exercised end to end; other product types fail with a compatibility error
  naming the missing dataset.
- No displacement, uplift or subsidence product; no causal attribution.
- No online basemap (by design).  Context comes from the graticule, footprint
  and scale bar.
- The recorded SHA-256 is a local integrity fingerprint; no authoritative
  upstream checksum was available for this granule.
- No Earthdata credentials are stored anywhere in this repository; re-downloading
  data requires your own `earthaccess` login and is not performed automatically.
