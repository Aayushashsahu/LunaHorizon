"""DEPRECATED - use ``python -m nisar_eim process`` instead.

The original un-georeferenced quicklook.  It is kept only so that existing
demonstration commands still run; all rendering now goes through the canonical
pipeline, which validates georeferencing before writing a map.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nisar_eim.cli import legacy_quicklook_main

if __name__ == "__main__":
    raise SystemExit(legacy_quicklook_main(sys.argv[1:]))
