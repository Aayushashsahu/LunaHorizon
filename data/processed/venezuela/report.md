# NISAR // Earth in Motion — observation report: venezuela

Generated **2026-10-25T12:40:27Z** by `nisar-earth-in-motion` 0.2.0.

## 1. What this observation is

Source granule `NISAR_L2_PR_GUNW_022_162_A_007_023_4000_SH_20260613T100656_20260613T100731_20260625T100655_20260625T100730_P05023_N_F_J_001` — NISAR GUNW (product version 1.0.11, specification 1.5.0).

Reference acquisition **2026-06-13 10:06:56 UTC** → secondary acquisition **2026-06-25 10:06:55 UTC** (temporal baseline 11 days).

Track 162, frame 7, Ascending pass, Left-looking, band L, frequency A, polarization HH.

Raw file: `data\raw\nisar_venezuela\NISAR_L2_PR_GUNW_022_162_A_007_023_4000_SH_20260613T100656_20260613T100731_20260625T100655_20260625T100730_P05023_N_F_J_001.h5` (2,336,227,328 bytes, unmodified).

## 2. Data layers used

| Layer | HDF5 dataset | Units | Shape | Valid pixels | Coverage |
| --- | --- | --- | --- | --- | --- |
| phase | `science/LSAR/GUNW/grids/frequencyA/unwrappedInterferogram/HH/unwrappedPhase` | radians | [4149, 4239] | 9,175,108 | 52.2% |
| coherence | `science/LSAR/GUNW/grids/frequencyA/unwrappedInterferogram/HH/coherenceMagnitude` | 1 | [4149, 4239] | 9,173,753 | 52.2% |

### 2.1 Unwrapped phase

The unwrapped interferogram is the phase difference between the reference and secondary acquisitions after ellipsoid and topographic flattening. Values are in **radians**, the unit declared by the product dataset. This is **not** a displacement map in metres.

Measured pixels: 9,175,108 of 17,587,611 (52.2%). Range -10.845 to 48.900 radians, median 15.301, p05–p95 4.559 to 30.357.

Colour limits 2.634 … 33.794 (percentiles [2.0, 98.0]); 183,503 low and 183,502 high values are clipped for display only. The GeoTIFF keeps the original measurements.

### 2.2 Coherence magnitude

Coherence magnitude describes how similar the two radar observations are. It is a quality indicator for the phase relationship, not a measurement of ground motion. Values are dimensionless on [0, 1].

Measured pixels: 9,173,753; median 0.177, p05–p95 0.047 to 0.739, maximum 0.998.

### 2.3 Product mask

Mask dataset `science/LSAR/GUNW/grids/frequencyA/unwrappedInterferogram/mask` decoded as `uint32_bitfield_with_anomalies`: water flag and reference/secondary subswath digits in bits 0–7, anomaly flags in bits 8–23, and an ionospheric-fill flag in bit 24.

Valid pixels 9,175,108 (52.2%), water 4,306,798, ionospheric-fill flagged 4,523,307, reference-anomaly flagged 0.

### 2.4 Connected components

2 component labels among valid pixels; largest label 1 covers 50.6% of valid pixels. Separate components can carry different integer phase ambiguities, so phase values between components are not necessarily continuous.

## 3. Georeferencing

Coordinates were resolved from the phase raster's own HDF5 dimension scales, not by searching the file for a dataset with the same name. Each GUNW grid (20 m wrapped, 80 m unwrapped) carries its own coordinate vectors.

- CRS: **WGS 84 / UTM zone 19N** (EPSG:32619)
- Grid: 4239 columns × 4149 rows, posting 80.000 m × 80.000 m
- Axis orientation: x ascending, y descending
- Coordinate convention: pixel_centres (CF-1.7 dimension scales)
- Bounds: {"left": 410400.0, "bottom": 1033920.0, "right": 749520.0, "top": 1365840.0}
- Resolution method: `phase raster + hdf5_dimension_scale`
- Round-trip check: {"checked_pixels": 9, "max_map_error": 0.0, "max_pixel_error": 0.0, "tolerance": 1e-06, "passed": true}

- Product image footprint (WGS84 bounds): [-69.604827, 9.543699, -66.849265, 12.213773] (41 vertices, 5.087 deg²)
- Map-grid extent (WGS84 bounds): [-69.824148, 9.3461, -66.705458, 12.355276] (9.312 deg²); the grid is a rectangle around a rotated swath, so it is larger than the imaged area.

- Comparison with the product's `boundingPolygon`: passed — 100.00% of the product image footprint lies inside the derived UTM grid extent. The grid extent is 1.83x the image footprint area, which is expected because a map grid is a rectangle around a rotated swath.

## 4. Geographic and event verification

- Footprint overlaps any reference event: **True**
- Events with locally usable data: 1

| Event | Magnitude | Inside raster | Nearest valid pixel | 10 km window valid | Median coherence | Status |
| --- | --- | --- | --- | --- | --- | --- |
| M7.2 foreshock (us6000t7zc) | 7.2 | True | 0.00 km | 100.0% | 0.354 | inside_usable |
| M7.5 mainshock (us6000t7zp) | 7.5 | True | 0.00 km | 100.0% | 0.092 | inside_marginal |

Event coordinates come from the USGS ComCat reference file bundled with the application; the screening rules are exploratory rules of this application.

## 5. Interpretation and limitations

- Unwrapped phase is reported in radians, the unit declared by the product. No phase-to-displacement conversion is applied: the GUNW product does not document a sign convention that this project could verify, and metric displacement requires assumptions that are not validated here.
- The product includes an ionospheric phase screen and geocoded tropospheric and solid-Earth-tide correction layers but does not apply them to the interferometric phase. Long-wavelength phase patterns therefore mix atmospheric and orbital effects with any surface signal.
- Coherence magnitude is a similarity/quality indicator. A coherence threshold is an exploratory filter chosen in the interface; no product-defined universal threshold exists.
- Pixels in different connected components can carry different integer phase ambiguities, so phase is not necessarily continuous across component boundaries.
- Geolocation is validated only for internal consistency (coordinate vectors, affine transform, EPSG code, footprint). Absolute product geolocation accuracy is not independently assessed.
- Geographic overlap with the 24 June 2026 Venezuela earthquake sequence does not establish that earthquake-induced deformation was measured. Any such statement would require a verified phase-to-displacement conversion, corrections and independent validation.

### Warnings

- More than 5% of pixels are flagged as filled by the ionospheric filter; phase in those areas is interpolated during product generation.

## 6. Quality filtering

The default exploratory coherence threshold shown in the application is 0.4. It is a display/quality filter chosen by this application, not a product-defined threshold.

| Coherence ≥ | Valid pixels | Coverage of valid | Median phase (rad) | Median coherence |
| --- | --- | --- | --- | --- |
| 0.0 | 9,173,753 | 52.2% | 15.301 | 0.177 |
| 0.1 | 5,768,763 | 32.8% | 12.810 | 0.406 |
| 0.2 | 4,464,029 | 25.4% | 11.926 | 0.479 |
| 0.3 | 3,799,510 | 21.6% | 12.250 | 0.518 |
| 0.4 | 2,941,617 | 16.7% | 12.767 | 0.572 |
| 0.5 | 2,047,410 | 11.6% | 13.671 | 0.637 |
| 0.6 | 1,272,277 | 7.2% | 15.065 | 0.704 |
| 0.7 | 657,309 | 3.7% | 15.672 | 0.769 |
| 0.8 | 214,399 | 1.2% | 12.634 | 0.841 |

## 7. Validation

| Check | Status | Detail |
| --- | --- | --- |
| Granule present on disk | **passed** | 2,336,227,328 bytes at data\raw\nisar_venezuela\NISAR_L2_PR_GUNW_022_162_A_007_023_4000_SH_20260613T100656_20260613T100731_20260625T100655_20260625T100730_P05023_N_F_J_001.h5 |
| Product metadata inspected | **passed** | GUNW v1.0.11 (spec 1.5.0); 5 layers; frequency A, polarization HH |
| Phase and coherence rasters readable | **passed** | phase [4149, 4239] float32; coherence [4149, 4239] float32; valid pixels 9,175,108/17,587,611 |
| Grid georeferencing validated | **passed** | EPSG:32619 (WGS 84 / UTM zone 19N); 80×80 m posting; method phase raster + hdf5_dimension_scale; round-trip max error 0.00e+00; GeoTIFF read-back passed |
| Geographic footprint validated | **passed** | 100.00% of the product image footprint lies inside the derived UTM grid extent. The grid extent is 1.83x the image footprint area, which is expected because a map grid is a rectangle around a rotated swath. |
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
python -m nisar_eim process "data\raw\nisar_venezuela\NISAR_L2_PR_GUNW_022_162_A_007_023_4000_SH_20260613T100656_20260613T100731_20260625T100655_20260625T100730_P05023_N_F_J_001.h5" --id venezuela
python -m nisar_eim validate "data\raw\nisar_venezuela\NISAR_L2_PR_GUNW_022_162_A_007_023_4000_SH_20260613T100656_20260613T100731_20260625T100655_20260625T100730_P05023_N_F_J_001.h5"
```

## 10. Provenance

- Product DOI: 10.5067/NIL2GUNW-P1
- Processing date/time (product): 2026-08-11T11:07:23
- Processing type: Nominal
- Composite release: P05023
- Static layers: https://nisar-services.earthdata.nasa.gov/redirect/NISAR_L2_STATIC/NISAR_L2_PR_GUNW_022_162_A_007_023_4000_SH_20260613T100656_20260613T100731_20260625T100655_20260625T100730_P05023_N_F_J_001.h5
- Software versions: {"python": "3.11.15", "platform": "Windows-10-10.0.26200-SP0", "pipeline": "0.2.0", "numpy": "2.4.6", "scipy": "1.17.1", "h5py": "3.16.0", "rasterio": "1.4.4", "pyproj": "3.7.2", "matplotlib": "3.11.2", "shapely": "2.2.0", "PIL": "13.0.0", "gdal": "3.10.3"}

Scientific method and source documentation: `docs/SCIENTIFIC_METHOD.md`. Data validation record: `docs/DATA_VALIDATION.md`.
