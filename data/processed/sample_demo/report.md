# NISAR // Earth in Motion — observation report: sample_demo

Generated **2026-10-25T12:15:45Z** by `nisar-earth-in-motion` 0.2.0.

## 1. What this observation is

Source granule `NISAR_L2_PR_GUNW_001_030_A_019_002_2000_SH_20081012T060911_20081012T060925_20081127T061000_20081127T061014_D00404_N_F_J_001` — NISAR GUNW (product version 0.0.4, specification 1.2.1).

Reference acquisition **2008-10-12 06:09:11 UTC** → secondary acquisition **2008-11-27 06:10:00 UTC** (temporal baseline 46 days).

Track 30, frame 19, Ascending pass, Right-looking, band L, frequency A, polarization HH.

Raw file: `data\demo\sample_gunw.h5` (264,241,152 bytes, unmodified).

## 2. Data layers used

| Layer | HDF5 dataset | Units | Shape | Valid pixels | Coverage |
| --- | --- | --- | --- | --- | --- |
| phase | `science/LSAR/GUNW/grids/frequencyA/unwrappedInterferogram/HH/unwrappedPhase` | radians | [1555, 1136] | 1,045,629 | 59.2% |
| coherence | `science/LSAR/GUNW/grids/frequencyA/unwrappedInterferogram/HH/coherenceMagnitude` | 1 | [1555, 1136] | 1,045,629 | 59.2% |

### 2.1 Unwrapped phase

The unwrapped interferogram is the phase difference between the reference and secondary acquisitions after ellipsoid and topographic flattening. Values are in **radians**, the unit declared by the product dataset. This is **not** a displacement map in metres.

Measured pixels: 1,045,629 of 1,766,480 (59.2%). Range -7.093 to 11.625 radians, median 2.354, p05–p95 1.023 to 3.206.

Colour limits 0.407 … 3.494 (percentiles [2.0, 98.0]); 20,913 low and 20,913 high values are clipped for display only. The GeoTIFF keeps the original measurements.

### 2.2 Coherence magnitude

Coherence magnitude describes how similar the two radar observations are. It is a quality indicator for the phase relationship, not a measurement of ground motion. Values are dimensionless on [0, 1].

Measured pixels: 1,045,629; median 0.415, p05–p95 0.176 to 0.645, maximum 0.977.

### 2.3 Product mask

Mask dataset `science/LSAR/GUNW/grids/frequencyA/unwrappedInterferogram/mask` decoded as `uint8_three_digit`: water flag and reference/secondary subswath digits in bits 0–7, anomaly flags in bits 8–23, and an ionospheric-fill flag in bit 24.

Valid pixels 1,045,629 (59.2%), water 1,844, ionospheric-fill flagged 0, reference-anomaly flagged 0.

### 2.4 Connected components

2 component labels among valid pixels; largest label 1 covers 93.4% of valid pixels. Separate components can carry different integer phase ambiguities, so phase values between components are not necessarily continuous.

## 3. Georeferencing

Coordinates were resolved from the phase raster's own HDF5 dimension scales, not by searching the file for a dataset with the same name. Each GUNW grid (20 m wrapped, 80 m unwrapped) carries its own coordinate vectors.

- CRS: **WGS 84 / UTM zone 11N** (EPSG:32611)
- Grid: 1136 columns × 1555 rows, posting 80.000 m × 80.000 m
- Axis orientation: x ascending, y descending
- Coordinate convention: pixel_centres (CF-1.7 dimension scales)
- Bounds: {"left": 365480.0, "bottom": 3789220.0, "right": 456360.0, "top": 3913620.0}
- Resolution method: `phase raster + hdf5_dimension_scale`
- Round-trip check: {"checked_pixels": 9, "max_map_error": 0.0, "max_pixel_error": 0.0, "tolerance": 1e-06, "passed": true}

- Product image footprint (WGS84 bounds): [-118.446686, 34.320626, -117.48269, 35.299073] (41 vertices, 0.669 deg²)
- Map-grid extent (WGS84 bounds): [-118.480566, 34.235382, -117.473914, 35.364934] (1.114 deg²); the grid is a rectangle around a rotated swath, so it is larger than the imaged area.

- Comparison with the product's `boundingPolygon`: passed — 100.00% of the product image footprint lies inside the derived UTM grid extent. The grid extent is 1.67x the image footprint area, which is expected because a map grid is a rectangle around a rotated swath.

## 4. Geographic and event verification

- Footprint overlaps any reference event: **False**
- Events with locally usable data: 0

| Event | Magnitude | Inside raster | Nearest valid pixel | 10 km window valid | Median coherence | Status |
| --- | --- | --- | --- | --- | --- | --- |
| M7.2 foreshock (us6000t7zc) | 7.2 | False | not available km | 0% | not available | outside_footprint |
| M7.5 mainshock (us6000t7zp) | 7.5 | False | not available km | 0% | not available | outside_footprint |

Event coordinates come from the USGS ComCat reference file bundled with the application; the screening rules are exploratory rules of this application.

## 5. Interpretation and limitations

- Unwrapped phase is reported in radians, the unit declared by the product. No phase-to-displacement conversion is applied: the GUNW product does not document a sign convention that this project could verify, and metric displacement requires assumptions that are not validated here.
- The product includes an ionospheric phase screen and geocoded tropospheric and solid-Earth-tide correction layers but does not apply them to the interferometric phase. Long-wavelength phase patterns therefore mix atmospheric and orbital effects with any surface signal.
- Coherence magnitude is a similarity/quality indicator. A coherence threshold is an exploratory filter chosen in the interface; no product-defined universal threshold exists.
- Pixels in different connected components can carry different integer phase ambiguities, so phase is not necessarily continuous across component boundaries.
- Geolocation is validated only for internal consistency (coordinate vectors, affine transform, EPSG code, footprint). Absolute product geolocation accuracy is not independently assessed.
- Geographic overlap with the 24 June 2026 Venezuela earthquake sequence does not establish that earthquake-induced deformation was measured. Any such statement would require a verified phase-to-displacement conversion, corrections and independent validation.

### Warnings

- This granule predates the NISAR launch (2025-07-30). Treat it as a format/pipeline sample, not a real-world observation.
- The raster footprint does not contain any reference event location; the interface must not label this observation as covering the earthquake.

## 6. Quality filtering

The default exploratory coherence threshold shown in the application is 0.4. It is a display/quality filter chosen by this application, not a product-defined threshold.

| Coherence ≥ | Valid pixels | Coverage of valid | Median phase (rad) | Median coherence |
| --- | --- | --- | --- | --- |
| 0.0 | 1,045,629 | 59.2% | 2.354 | 0.415 |
| 0.1 | 1,029,201 | 58.3% | 2.353 | 0.417 |
| 0.2 | 978,498 | 55.4% | 2.351 | 0.425 |
| 0.3 | 846,560 | 47.9% | 2.340 | 0.444 |
| 0.4 | 571,309 | 32.3% | 2.323 | 0.490 |
| 0.5 | 259,357 | 14.7% | 2.306 | 0.566 |
| 0.6 | 89,052 | 5.0% | 2.215 | 0.658 |
| 0.7 | 25,516 | 1.4% | 2.075 | 0.744 |
| 0.8 | 4,453 | 0.3% | 2.084 | 0.829 |

## 7. Validation

| Check | Status | Detail |
| --- | --- | --- |
| Granule present on disk | **passed** | 264,241,152 bytes at data\demo\sample_gunw.h5 |
| Product metadata inspected | **passed** | GUNW v0.0.4 (spec 1.2.1); 5 layers; frequency A, polarization HH |
| Phase and coherence rasters readable | **passed** | phase [1555, 1136] float32; coherence [1555, 1136] float32; valid pixels 1,045,629/1,766,480 |
| Grid georeferencing validated | **passed** | EPSG:32611 (WGS 84 / UTM zone 11N); 80×80 m posting; method phase raster + hdf5_dimension_scale; round-trip max error 0.00e+00; GeoTIFF read-back passed |
| Geographic footprint validated | **passed** | 100.00% of the product image footprint lies inside the derived UTM grid extent. The grid extent is 1.67x the image footprint area, which is expected because a map grid is a rectangle around a rotated swath. |
| Scientific interpretation validated | **not_validated** | Phase is delivered in radians with coherence and masks. No phase-to-displacement conversion is applied, so no deformation interpretation is claimed. |

## 8. Outputs

- `phase_png`: `phase.png`
- `coherence_png`: `coherence.png`
- `phase_tif`: `phase.tif`
- `coherence_tif`: `coherence.tif`
- `metadata_json`: `metadata.json`
- `report_md`: `report.md`
- `map_phase_png`: `preview/map_phase.png`
- `map_coherence_png`: `preview/map_coherence.png`
- `map_quality_png`: `preview/map_quality.png`
- `coherence_preview_bin`: `preview/coherence_u8.bin`
- `map_components_png`: `preview/map_components.png`

## 9. Reproduce

```powershell
python -m nisar_eim process "data\demo\sample_gunw.h5" --id sample_demo
python -m nisar_eim validate "data\demo\sample_gunw.h5"
```

## 10. Provenance

- Product DOI: 10.5067/NIL2GUNW-B1
- Processing date/time (product): 2025-01-29T05:41:57
- Processing type: Nominal
- Composite release: D00404
- Static layers: not available
- Software versions: {"python": "3.11.15", "platform": "Windows-10-10.0.26200-SP0", "pipeline": "0.2.0", "numpy": "2.4.6", "scipy": "1.17.1", "h5py": "3.16.0", "rasterio": "1.4.4", "pyproj": "3.7.2", "matplotlib": "3.11.2", "shapely": "2.2.0", "PIL": "13.0.0", "gdal": "3.10.3"}

Scientific method and source documentation: `docs/SCIENTIFIC_METHOD.md`. Data validation record: `docs/DATA_VALIDATION.md`.
