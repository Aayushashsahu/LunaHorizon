# Architecture

```text
data/raw/**                immutable inputs (read-only, never rewritten)
data/demo/                 small public sample product (pipeline smoke test)
data/processed/<id>/       all derived artefacts, one directory per observation
src/nisar_eim/             the package (Python 3.11, no web framework)
  errors.py                typed, actionable error hierarchy (NisarError)
  product_reader.py        HDF5 structure, identification, layer discovery
  geospatial.py            grid resolution, affine model, footprints, round-trips
  quality.py               mask decoding, coherence/connectivity filtering
  statistics.py            robust summaries, threshold tables
  rendering.py             PNG quicklooks, WGS84 display previews, GeoTIFFs
  reporting.py             metadata.json / report.md writers
  event.py                 USGS reference events, footprint and window analysis
  metrics.py               documented helpers (LOS formula is NOT wired in)
  pipeline.py              orchestration, caching, validation checks
  cli.py                   `python -m nisar_eim inspect|validate|process|list|serve`
  webapp/server.py         stdlib HTTP server: static shell + JSON API
  webapp/static/           index.html, styles.css, app.js (no frameworks, offline)
scripts/                   thin/deprecated wrappers and research utilities
tests/                     pytest suite incl. the 4x regression case
docs/                      scientific method, validation record, this file
```

## Data flow

```text
granule.h5
   └─ product_reader.open_product()      structure + identification only (no raster bodies)
        └─ geospatial.build_geometry()   coordinates come from the raster's own
            │                            HDF5 dimension scales; validated, never invented
            ├─ pipeline.load_layers()    chunked reads (row windows), one valid mask
            ├─ statistics.summarise()    robust stats over valid pixels
            ├─ rendering.render_*        PNG + WGS84 display preview + GeoTIFF
            ├─ event.assess_events()     USGS epicentres vs footprint and local coherence
            └─ reporting.write_*         metadata.json + report.md (provenance, limits)
```

### Rules that keep the science honest

* Georeferencing is resolved **per raster** from its dimension scales, with the
  grid group's `projection` dataset as the CRS source.  A file-wide basename
  search is forbidden (that was the 4x bug).
* Masks are decoded from the product's encoded bitfield, not assumed boolean.
* Phase statistics keep invalid/valid pixels distinct; display limits never
  modify stored values.
* Every failure raises a `NisarError` subtype with input, expectation, actual
  values and next step; the CLI renders these as messages instead of tracebacks,
  and always states that the raw file was untouched.

## Caching and memory

* `process_granule` computes a fingerprint over the granule (size + mtime),
  configuration and pipeline version.  If the outputs are current it returns the
  cached metadata unless `--force` is given, so switching views in the UI never
  re-reads a 2.34 GB file.
* Rasters are read through h5py in chunked windows and the granule is never
  loaded as a byte blob.  Measured on the target laptop with a forced full
  reprocess of the real granule: **16 s wall time, peak RSS ~2.1 GiB** (sampled
  with `psutil` at 10 Hz) — the four resident rasters are ~70 MB each in
  float32; the remainder is matplotlib/GDAL/proj working memory.  This leaves
  ample headroom on a 16 GB machine; a cached run touches only the small
  preview files.
* The web application reads only `data/processed/**` and opens the HDF5 file
  again solely for the pixel-sampling endpoint (windowed reads).

## CLI

```powershell
python -m nisar_eim inspect  <granule>            # metadata + grid resolution report
python -m nisar_eim validate <granule> --out dir  # checks, events, integrity record
python -m nisar_eim process  <granule> --id name  # quicklooks, GeoTIFFs, metadata, report
python -m nisar_eim list                          # processed observations
python -m nisar_eim serve --port 8000             # local application
```

`scripts/quicklook_gunw*.py` are compatibility shims that delegate to
`nisar_eim.cli.legacy_quicklook_main`; there is exactly one rendering path.

## Web application

* `webapp/server.py` is a stdlib `ThreadingHTTPServer` — no Flask/Django, no
  build step, no CDN.
  * `GET /` — the SPA shell; `GET /static/*` — assets.
  * `GET /api/index` — observations, validation states, event summary, layer
    descriptions, limitations.
  * `GET /api/observations/<id>` — full payload (metadata, assets, map images,
    display-grid geometry, threshold table).
  * `GET /api/observations/<id>/artifact/<name>` — whitelisted downloads.
  * `GET /api/observations/<id>/sample?lon=&lat=` (or `row`/`col`) — windowed
    pixel read from the granule; returns `NisarError` JSON when the raw file is
    unavailable (offline browsing of derived outputs still works).
  * `GET /api/observations/<id>/preview/coherence.bin` — uint8 coherence preview
    for the interactive threshold overlay.
  * `GET /api/observations/<id>/threshold?value=0.5` — interpolated threshold
    statistics without reprocessing.
* `static/app.js` draws the explorer on a `<canvas>` from the pre-rendered
  WGS84 display images: layer tabs, coherence-threshold overlay, footprint
  outline, graticule, scale bar, epicentre markers, zoom/pan, hover/pinned pixel
  readout, export links.  No basemap tiles are required; the graticule, footprint
  and scale bar provide the geographic context offline.
* Validation states are shown individually (`dataset_found` … `footprint_validated`,
  `scientific_interpretation_validated`) — a green badge only appears when the
  corresponding check actually passed.

## Extending to more observations

Process another granule with `python -m nisar_eim process <granule> --id <name>`;
the observation appears in the dashboard automatically.  No code changes are
needed as long as the granule is an L2 GUNW product with the expected layers;
otherwise the reader raises a compatibility error naming the missing dataset.
