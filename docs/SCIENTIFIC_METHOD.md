# Scientific method — NISAR // Earth in Motion

This document records what the application actually does to the data, which
statements are supported by the product, and which are explicitly **not**
supported.  Everything here can be re-derived from the granule metadata and the
code in `src/nisar_eim/`.

---

## 1. The product

**Product**: NASA-ISRO NISAR Level-2 Geocoded UNWRapped Interferogram (GUNW),
HDF5, product version `1.0.11`, product specification `1.5.0`.

**Granule used for the first case study**:

```text
NISAR_L2_PR_GUNW_022_162_A_007_023_4000_SH_20260613T100656_20260613T100731_20260625T100655_20260625T100730_P05023_N_F_J_001.h5
size: 2,336,227,328 bytes
SHA-256 (computed locally during validation): ae5fbc528b99ba263f2040e56c225762c740eeb8476a75e598e888eb0b838f65
```

Filename tokens: track 162, ascending pass, frame 7, reference acquisition
`20260613T100656` (2026-06-13 10:06:56 UTC), secondary acquisition
`20260625T100655` (2026-06-25 10:06:55 UTC).

### Layers the application uses

| Layer | HDF5 path (frequency A, HH) | Shape | dtype | Units |
| --- | --- | --- | --- | --- |
| Unwrapped phase | `science/LSAR/GUNW/grids/frequencyA/unwrappedInterferogram/HH/unwrappedPhase` | 4149 x 4239 | float32 | radians |
| Coherence magnitude | `.../HH/coherenceMagnitude` | 4149 x 4239 | float32 | dimensionless (0-1) |
| Connected components | `.../HH/connectedComponents` | 4149 x 4239 | uint16 | label, fill 65535 |
| Product mask | `.../unwrappedInterferogram/mask` | 4149 x 4239 | uint32 | encoded bitfield |

The paths are **discovered**, not hard-coded: the reader walks the HDF5 tree,
groups datasets by grid, and refuses to build a product when a required layer is
absent.  If a future granule has a different layout the failure message names the
missing dataset instead of silently producing a wrong picture.

### Geometry information present in the product

* `science/LSAR/GUNW/grids/frequencyA/centerFrequency` (Hz) — used only to
  *derive* an indicative wavelength with `c / f`; this is recorded as
  "derived here; not a product field".
* `.../projection` (uint32 EPSG code) plus CF grid-mapping attributes.
* `xCoordinates` / `yCoordinates` per grid, with `xCoordinateSpacing` /
  `yCoordinateSpacing` and CF `standard_name` attributes.
* `science/LSAR/identification/boundingPolygon` (WKT, EPSG:4326) — the imaged
  footprint.
* `science/LSAR/GUNW/metadata/radarGrid/*` — decimated geometry lookup tables
  (incidence angle, LOS unit vectors, baselines, phase screens, …) on a 676 x 690
  grid with 20 decimation levels.  These are **not** map coordinates and are not
  used for georeferencing.

---

## 2. Root cause of the four-times coordinate mismatch

The failing command was:

```text
python scripts\quicklook_gunw_georef_v3.py <granule> phase
ValueError: Raster shape (4149, 4239) does not match coordinate lengths (y=16596, x=16956)
```

### What the numbers are

A single GUNW granule contains **several independent map grids**:

| Grid | Raster shape | Coordinate vectors | Posting |
| --- | --- | --- | --- |
| `grids/frequencyA/wrappedInterferogram` | 16596 x 16956 (complex64) | x 16956, y 16596 | 20 m |
| `grids/frequencyA/unwrappedInterferogram` | 4149 x 4239 (float32) | x 4239, y 4149 | 80 m |
| `grids/frequencyA/pixelOffsets` | 4149 x 4239 | (unwrapped grid) | 80 m |
| `metadata/radarGrid` lookup tables | 676 x 690, decimated | none (geometry LUTs) | n/a |

`16596 = 4 x 4149` and `16956 = 4 x 4239` because the two grids are the *same
footprint at different postings*: the wrapped interferogram is kept at 20 m and
the unwrapped product is generated at 80 m, a factor of four on each axis.

### The bug

`scripts/quicklook_gunw_georef_v3.py` resolved the coordinate datasets with a
**global basename search** over the whole file.  HDF5 visits groups in
alphabetical order, so `.../wrappedInterferogram/xCoordinates` (16956 values)
was found first and paired with the 4149 x 4239 unwrapped phase raster.  The
script therefore mixed a 20 m coordinate vector with an 80 m raster — hence
"coordinate lengths are four times the raster shape".

The script's other assumptions were also unsafe: it inferred the affine transform
from `median(diff(x))`, assumed `y` was descending, and accepted whatever CRS
Rasterio was handed.

### The fix

Georeferencing is now resolved **from the raster itself**:

1. Open the target dataset (`unwrappedPhase`, …).
2. Read its HDF5 `DIMENSION_LIST` / dimension scales and take *those* coordinate
   vectors (the ones attached to this raster).
3. Fall back, in order, to coordinate datasets in the raster's own grid group, to
   the polarization sub-group, and to an explicit grid/shape match — never to a
   file-wide basename search.
4. Cross-check spacing against the `*CoordinateSpacing` datasets and the CRS
   against the `projection` dataset in the same group.
5. Reject non-regular axes, non-monotonic axes, and shape mismatches with an
   error that names the raster shape, both coordinate paths, both lengths, the
   measured ratio and the violated invariant.

No part of the fix divides by four, subsamples coordinates, invents a bounding
box, or reuses the demo sample's EPSG code.  If a product genuinely lacks enough
georeferencing, the pipeline raises `GeoreferencingError` with diagnostics
instead of writing a mislabelled file.  The regression tests pin the exact
reported case (`tests/test_geospatial.py`,
`tests/test_product_reader.py`).

---

## 3. Georeferencing model

* CRS: `EPSG:32619` — WGS 84 / UTM zone 19N — read from the product's own
  `projection` dataset, not assumed.
* Grid: regular, 80 m x 80 m posting; x ascending, y descending.
* Convention: HDF5 coordinate vectors are **pixel centres**; the affine transform
  places its origin half a pixel outside the centre of pixel (0, 0), i.e.
  `c = x0 - dx/2`, `f = y0 - dy/2`.
* Validation: pixel -> map -> pixel round-trip is executed on nine pixels during
  processing (max map error `0.00e+00` for this granule) and the written GeoTIFF
  is reopened and compared against the HDF5-derived transform.
* Footprints: the *grid extent* is densified along the raster edges in transform
  space and transformed to EPSG:4326 with pyproj.  The *image footprint* is the
  product's `identification/boundingPolygon`.  The check reports how much of the
  image footprint lies inside the derived grid extent (100.00% for this granule;
  the grid is 1.83x the image area because a UTM rectangle wraps a rotated swath).

---

## 4. Masks, coherence and validity

The product mask is **encoded, not boolean**.  The description in the granule
reads: *"Combination of a water mask, a mask of subswaths of valid samples, and
data anomalies … Each pixel value is encoded as a 32-bit unsigned integer. Bits
0-7 represent subswath …"*.  The low byte carries a three-digit decimal number
(water digit, reference subswath, secondary subswath); bits 8-15 and 16-23 are
anomaly flags; bit 24 is the ionospheric-fill flag.  `nisar_eim.quality.decode_mask`
reads the digits from `value & 0xFF` — the old script divided the full 32-bit
integer by 10 and therefore read the wrong digit for any pixel with an anomaly
bit set.

Displayed validity for phase and coherence is:

```text
valid = finite(value) AND mask.valid (fill excluded, both subswath digits > 0)
```

* A coherent threshold (default 0.4) is an **exploratory user-facing filter** for
  the map overlay.  The threshold, the resulting coverage and a full threshold
  table are shown in the interface; the exported GeoTIFF always keeps every valid
  measurement.
* Connected-component labels are reported, never silently used to delete pixels.
* Statistics are computed over valid pixels only, and the count of valid/invalid
  pixels is reported for every layer.

For this granule: 9,175,108 of 17,587,611 pixels carry a valid phase
measurement (52.2%); coherence median over valid pixels is 0.177 (p05-p95
0.047-0.739).

---

## 5. What phase does and does not tell us

`unwrappedPhase` is the interferometric phase difference between the 2026-06-13
and 2026-06-25 acquisitions after ellipsoid and topographic flattening, in
**radians**, as declared by the dataset's own `units` attribute.

Interferometric phase can be changed by surface displacement, topographic
residuals, atmosphere (ionosphere, troposphere), solid-Earth tides, orbital
errors and decorrelation.  A colourful phase ramp is therefore **not** evidence
of ground motion.

### Displacement conversion gate

The application deliberately performs **no** phase-to-displacement conversion.
Before such a conversion could be implemented, authoritative documentation of
all of the following would be required:

1. the phase sign convention (toward/away from the radar) for this product,
2. the exact phase quantity (flattened, unwrapped, corrected or raw),
3. the acquisition geometry per pixel (incidence angle, LOS vectors),
4. which corrections are already applied versus still required,
5. a validation strategy against an independent reference.

The product ships with ionospheric, tropospheric and tidal quantities in
`metadata/radarGrid`, but the granule does not document the sign convention
required for a defensible conversion, and this project does not have an
independent reference measurement for the event.  Consequently:

> Unwrapped phase is shown in radians, with coherence and masks. No
> phase-to-displacement conversion is applied and no earthquake causation is
> claimed. The interface calls the output an **exploratory observation**.

`nisar_eim.metrics.phase_to_los_displacement()` exists in the code base as a
documented, tested formula helper (`d = phi * lambda / (4*pi)`), but it is **not**
called anywhere in the pipeline, and its docstring states that the caller must
establish the conventions first.

---

## 6. Event verification (independent of the granule)

Event locations come from a bundled copy of the USGS ComCat records, retrieved
2026-10-25, with public source URLs recorded in `metadata.json`:

| Event | ID | Time (UTC) | Location | Depth |
| --- | --- | --- | --- | --- |
| M7.2 foreshock | `us6000t7zc` | 2026-06-24 22:04:31.806 | 10.3713 N, 68.5564 W (20 km E of San Felipe, Yaracuy) | 10.0 km |
| M7.5 mainshock | `us6000t7zp` | 2026-06-24 22:05:04.053 | 10.5955 N, 67.2205 W (20 km W of Catia La Mar, La Guaira) | 10.0 km |

The two reviewed events are ~32 s apart (a doublet).  Both records, their
review status, horizontal errors and the source URLs live in
`src/nisar_eim/data/venezuela_2026_earthquakes.json`.

Machine-readable endpoints:

```text
https://earthquake.usgs.gov/fdsnws/event/1/query?eventid=us6000t7zc&format=csv
https://earthquake.usgs.gov/fdsnws/event/1/query?eventid=us6000t7zp&format=csv
```

Verification performed by `nisar_eim.event`:

1. Transform the epicentre into the raster CRS and get fractional row/column.
2. Test `inside_raster_bounds` and `inside_product_footprint`.
3. Find the nearest valid pixel (searched up to 50 km).
4. Summarise phase and coherence in three windows (0.16 km, 1.6 km, 10 km
   radius): valid fraction, median coherence, fraction above the exploratory
   threshold, connected-component dominance.
5. Classify the event as `inside_usable`, `inside_marginal` or `outside`, using
   screening rules that are **stated in the metadata as application-defined
   exploratory criteria, not NISAR product requirements**.

Result for this granule (2026-10-25 run):

* Both epicentres are inside the raster bounds, and the M7.2 foreshock is inside
  the product's image footprint.
* Nearest valid pixel to the M7.2 epicentre: row 2741, col 1727, distance
  0.0 km, coherence 0.708.
* 1.6 km window: 100% valid, median coherence 0.406.
* 1 of the 2 events is classified `inside_usable`; `footprint_overlaps_any_event
  = true`, `local_data_usable_for_any_event = true`.
* `displacement_interpretation_validated = false` — and this is shown in the UI
  exactly as it is.

Acquisition dates bracketing the event are **never** treated as evidence by
themselves.

---

## 7. Sources

* NISAR L2 GUNW product specification (PDF, linked from the ASF docs):
  <https://nisar.asf.earthdatacloud.nasa.gov/NISAR-SAMPLE-DATA/DOCS/NISAR_D-102272_RevE_NASA_SDS_Product_Specification_L2_GUNW_Nov8_2024_w-sigs.pdf>
* ASF NISAR documentation (GUNW, RUNW, known issues, products overview):
  <https://nisar-docs.asf.alaska.edu/>
* NASA NISAR mission / data pages:
  <https://science.nasa.gov/mission/nisar/data/> and
  <https://science.nasa.gov/mission/nisar/sample-data/>
* NASA Earth Observatory background on the June 2026 Venezuela sequence:
  <https://science.nasa.gov/earth/earth-observatory/where-venezuelas-earthquakes-shifted-the-ground/>
* USGS event pages: <https://earthquake.usgs.gov/earthquakes/eventpage/us6000t7zc>,
  <https://earthquake.usgs.gov/earthquakes/eventpage/us6000t7zp>
* HDF5 dimension scales: <https://support.hdfgroup.org/HDF5/Tutor/dimscale.html>
* CF conventions for grid mapping: <https://cfconventions.org/cf-conventions/cf-conventions.html#grid-mapping>

Local extracts used during the audit are stored in `research/references/`; the
structure dump of the granule is `data/processed/audit/venezuela_structure.txt`.

## 8. Provenance rules

1. The raw granule is opened read-only and never rewritten; validation hashes it
   before and after and records `unchanged_during_validation`.
2. All derived files are written under `data/processed/<observation-id>/`.
3. No Earthdata credentials appear in source, logs, metadata or exports.
4. Every derived artefact embeds the source granule, dataset paths, dates, units,
   validity rule and the "not a displacement map" statement (PNG footer, GeoTIFF
   `NISAR_*` tags, `metadata.json`, `report.md`).
5. Unavailable information is recorded as unavailable, never guessed.
