# Data Access Notes

## Preferred path

1. Discover production/provisional NISAR products through NASA Earthdata / ASF.
2. Use L2 products first.
3. Store original HDF5 files under `data/raw/` only.
4. Never commit source HDF5 to Git.
5. Record product identifier, dates, processing baseline/version, spatial extent, and access URL in a provenance record.

## Learning path

NASA provides NISAR sample products and the ASF NISAR Cookbook. The cookbook is under active development and currently contains access/visualization recipes for NISAR data, with local-machine Jupyter workflows. It notes that some GUNW workflows are still being developed, so our parser should remain product-path-agnostic and inspect actual HDF5 content rather than hard-code old sample layouts.

## Current public product identifiers

ASF's current user guide lists provisional collection identifiers including:

- `NISAR_L2_GUNW_PROVISIONAL_V1`
- `NISAR_L2_GCOV_PROVISIONAL_V1`

ISRO's July 24, 2026 release notes additionally list S-band L1/L2 products including GUNW and GCOV and provide portal-based search/visualization/download through Bhoonidhi.
