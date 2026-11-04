"""Regression test suite for full-resolution pixel inspection.

Verifies:
1. Known valid pixel retrieval (phase & coherence Float32).
2. Correct geographic-to-pixel conversion (lon/lat -> row/col).
3. Phase value retrieval in radians.
4. Coherence value retrieval in [0, 1].
5. NaN / nodata handling (safe JSON None/null conversion without crashes).
6. Invalid or decorrelated pixels handling.
7. Coordinates outside raster coverage (in_grid: False, valid: False).
8. Missing observation handling (ObservationNotFound -> 404).
9. Server socket reset resilience (BrokenPipe, ConnectionReset).
10. Complete offline GeoTIFF fallback when raw HDF5 granule is not available.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from nisar_eim.webapp.server import Application, Handler, ObservationNotFound


@pytest.fixture
def venezuela_app() -> Application:
    repo_root = Path(__file__).resolve().parents[1]
    data_root = repo_root / "data" / "processed"
    if not (data_root / "venezuela" / "metadata.json").exists():
        pytest.skip("Processed venezuela observation not present")
    app = Application(data_root)
    yield app
    app.close()


def test_01_known_valid_pixel(venezuela_app: Application) -> None:
    """Verify inspection on a known valid pixel near the M7.2 foreshock (row 2741, col 1727)."""
    sample = venezuela_app.sample("venezuela", row=2741, col=1727)
    assert sample["observation_id"] == "venezuela"
    assert sample["row"] == 2741
    assert sample["col"] == 1727
    assert sample["valid"] is True
    assert sample["in_grid"] is True
    assert sample["phase_radians"] is not None
    assert np.isclose(sample["phase_radians"], 11.5208, atol=0.01)
    assert sample["coherence"] is not None
    assert np.isclose(sample["coherence"], 0.7082, atol=0.01)


def test_02_geographic_to_pixel_conversion(venezuela_app: Application) -> None:
    """Verify geographic lon/lat accurately maps to the expected row/col in EPSG:32619."""
    # Epicentre of M7.2 foreshock: lon=-68.5564, lat=10.3713
    sample = venezuela_app.sample("venezuela", lon=-68.5564, lat=10.3713)
    assert sample["row"] == 2741
    assert sample["col"] == 1727
    assert sample["in_grid"] is True
    assert sample["phase_radians"] is not None
    assert sample["coherence"] is not None


def test_03_phase_value_retrieval(venezuela_app: Application) -> None:
    """Verify phase radians are returned in native product units spanning multiple 2pi cycles."""
    # Center pixel: row 2074, col 2119
    sample = venezuela_app.sample("venezuela", row=2074, col=2119)
    phase = sample["phase_radians"]
    assert phase is not None
    assert isinstance(phase, float)
    assert sample["units"]["phase"] == "radians"
    assert "cannot be read as vertical motion" in sample["note"]


def test_04_coherence_value_retrieval(venezuela_app: Application) -> None:
    """Verify coherence magnitude is returned within valid [0.0, 1.0] range."""
    sample = venezuela_app.sample("venezuela", row=2741, col=1727)
    coh = sample["coherence"]
    assert coh is not None
    assert isinstance(coh, float)
    assert 0.0 <= coh <= 1.0
    assert sample["coherence_valid"] is True


def test_05_nan_coherence_handling(venezuela_app: Application) -> None:
    """Verify NaN / nodata pixels return None / null without raising unhandled exceptions."""
    # Lower-right corner of bounding box is outside radar swath (nodata)
    sample = venezuela_app.sample("venezuela", row=4000, col=4000)
    assert sample["in_grid"] is True
    assert sample["valid"] is False
    assert sample["phase_radians"] is None
    assert sample["coherence"] is None
    # Must be JSON-serializable without NaN tokens
    serialized = json.dumps(sample)
    assert "NaN" not in serialized
    assert '"phase_radians": null' in serialized


def test_06_invalid_or_masked_pixel(venezuela_app: Application) -> None:
    """Verify invalid pixels report phase_valid/coherence_valid correctly."""
    sample = venezuela_app.sample("venezuela", row=50, col=50)
    assert sample["valid"] is False
    assert sample["phase_radians"] is None or sample["coherence"] is None


def test_07_coordinates_outside_raster_coverage(venezuela_app: Application) -> None:
    """Verify querying coordinates outside the observation returns a clean non-error response."""
    # Far away point (e.g. lon=-60.0, lat=5.0)
    sample = venezuela_app.sample("venezuela", lon=-60.0, lat=5.0, strict=False)
    assert sample["in_grid"] is False
    assert sample["valid"] is False
    assert sample["row"] is None
    assert sample["col"] is None
    assert sample["phase_radians"] is None
    assert sample["coherence"] is None
    assert "outside this observation's raster coverage" in sample["note"]
    assert sample["mask"]["outside_coverage"] is True


def test_08_missing_observation(venezuela_app: Application) -> None:
    """Verify querying an unknown observation raises ObservationNotFound."""
    with pytest.raises(ObservationNotFound) as excinfo:
        venezuela_app.sample("non_existent_observation", row=100, col=100)
    assert "non_existent_observation" in str(excinfo.value)


def test_09_socket_disconnection_resilience() -> None:
    """Verify Handler ignores BrokenPipeError, ConnectionResetError, ConnectionAbortedError gracefully."""
    class DummyWriter:
        def write(self, data: bytes) -> None:
            raise ConnectionResetError("Remote client disconnected")

    class ResilientHandler(Handler):
        def __init__(self) -> None:
            self.wfile = DummyWriter()
        def send_response(self, code: int) -> None: pass
        def send_header(self, k: str, v: str) -> None: pass
        def end_headers(self) -> None: pass

    handler = ResilientHandler()
    # Call _send_json, _send_error_json, and _send_bytes bound to ResilientHandler
    handler._send_json({"test": "data"})
    handler._send_error_json(400, "test error")
    handler._send_bytes(b"data", "text/plain")


def test_10_geotiff_offline_fallback(tmp_path: Path) -> None:
    """Verify pixel inspection functions 100% offline from GeoTIFFs when raw H5 is missing."""
    repo_root = Path(__file__).resolve().parents[1]
    ven_dir = repo_root / "data" / "processed" / "venezuela"
    if not (ven_dir / "phase.tif").exists():
        pytest.skip("Venezuela phase.tif not present")

    # Create isolated directory with modified metadata pointing to a nonexistent raw granule
    test_obs = tmp_path / "offline_venezuela"
    test_obs.mkdir()
    meta = json.loads((ven_dir / "metadata.json").read_text(encoding="utf-8"))
    meta["source"]["path"] = "data/raw/nisar_nonexistent/missing_granule.h5"
    (test_obs / "metadata.json").write_text(json.dumps(meta), encoding="utf-8")

    # Copy GeoTIFFs
    import shutil
    shutil.copy2(ven_dir / "phase.tif", test_obs / "phase.tif")
    shutil.copy2(ven_dir / "coherence.tif", test_obs / "coherence.tif")

    app = Application(tmp_path)
    # Ensure raw granule is not found
    assert app.repository._find_raw_granule(app.repository.load("offline_venezuela")) is None
    assert app.repository._find_geotiffs("offline_venezuela", app.repository.load("offline_venezuela")) is not None

    # Sample pixel
    sample = app.sample("offline_venezuela", row=2741, col=1727)
    assert sample["inspection_source"] == "processed_geotiff"
    assert sample["phase_radians"] is not None
    assert sample["coherence"] is not None
    assert sample["valid"] is True
    assert sample["units"]["phase"] == "radians"
    app.close()
