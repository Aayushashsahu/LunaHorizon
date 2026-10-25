"""DEPRECATED - use ``python -m nisar_eim process`` instead.

Superseded by the canonical pipeline; kept so old commands keep working.  The
canonical commands, georeferencing rules and output layout are documented in
``README.md`` and ``docs/ARCHITECTURE.md``.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nisar_eim.cli import legacy_quicklook_main

if __name__ == "__main__":
    raise SystemExit(legacy_quicklook_main(sys.argv[1:]))
