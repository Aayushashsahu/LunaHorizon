# Validation record — NISAR_L2_PR_GUNW_022_162_A_007_023_4000_SH_20260613T100656_20260613T100731_20260625T100655_20260625T100730_P05023_N_F_J_001

Generated 2026-10-25T14:54:12Z by nisar-earth-in-motion 0.2.0.

## Checks

| Check | Status | Detail |
| --- | --- | --- |
| dataset_found | **passed** | 2,336,227,328 bytes |
| metadata_inspected | **passed** | NISAR_L2_PR_GUNW_022_162_A_007_023_4000_SH_20260613T100656_20260613T100731_20260625T100655_20260625T100730_P05023_N_F_J_001 |
| raster_readable | **passed** | phase: [4149, 4239], coherence: [4149, 4239], connected_components: [4149, 4239], mask: [4149, 4239] |
| georeferencing_validated | **passed** | EPSG:32619; round-trip checked 9 pixels; max map error 0.00e+00 |
| footprint_validated | **passed** | 100.00% of the product image footprint lies inside the derived UTM grid extent. The grid extent is 1.83x the image footprint area, which is expected because a map grid is a rectangle around a rotated swath. |
| scientific_interpretation_validated | **not_validated** | No displacement conversion or event-causation claim is validated. |

## Georeferencing

- CRS: WGS 84 / UTM zone 19N (EPSG:32619)
- Shape: 4149 rows × 4239 columns
- Posting: {'x': 80.0, 'y': 80.0}
- Coordinate convention: pixel_centres
- Method: phase raster + hdf5_dimension_scale
- Round trip: {"checked_pixels": 9, "max_map_error": 0.0, "max_pixel_error": 0.0, "tolerance": 1e-06, "passed": true}
- Product polygon check: {"status": "passed", "product_inside_grid_fraction": 1.0000000000000002, "grid_inside_product_fraction": 0.5463602873692023, "grid_extent_area_deg2": 9.311514161777504, "product_area_deg2": 5.087441553271153, "detail": "100.00% of the product image footprint lies inside the derived UTM grid extent. The grid extent is 1.83x the image footprint area, which is expected because a map grid is a rectangle around a rotated swath."}

## Raw file integrity

```json
{
  "size_bytes": 2336227328,
  "mtime_ns": 1792914874000000000,
  "unchanged_during_validation": true,
  "sha256": "ae5fbc528b99ba263f2040e56c225762c740eeb8476a75e598e888eb0b838f65"
}
```

## Reference events

| Event | Magnitude | Inside raster bounds | Row/col |
| --- | --- | --- | --- |
| M7.2 foreshock (us6000t7zc) | 7.2 | True | [2741.262096525688, 1726.5102227088457] |
| M7.5 mainshock (us6000t7zp) | 7.5 | True | [2424.8710837515537, 3553.1129123997407] |
