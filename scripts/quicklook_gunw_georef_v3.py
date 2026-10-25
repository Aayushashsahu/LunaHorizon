"""DEPRECATED - use ``python -m nisar_eim process`` instead.

This script used to read ``metadata/radarGrid`` coordinate arrays by basename,
which mixed the 20 m wrapped grid (16956 x 16596 coordinates) with the 80 m
unwrapped grid (4239 x 4149 pixels) and raised::

    ValueError: Raster shape (4149, 4239) does not match coordinate lengths
    (y=16596, x=16956)

The root cause, the product structure behind it and the fix are documented in
``docs/SCIENTIFIC_METHOD.md``.  Georeferencing now lives in
``nisar_eim.product_reader`` / ``nisar_eim.geospatial`` and is derived from the
HDF5 dimension scales that belong to each raster, so this file is only a thin
compatibility shim.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nisar_eim.cli import legacy_quicklook_main

if __name__ == "__main__":
    raise SystemExit(legacy_quicklook_main(sys.argv[1:]))
