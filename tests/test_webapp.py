"""Web application tests: application layer and real HTTP responses."""

from __future__ import annotations

import json
import shutil
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest
from conftest import write_synthetic_gunw

from nisar_eim.errors import NisarError
from nisar_eim.geospatial import GridGeometry
from nisar_eim.pipeline import ProcessConfig, process_granule
from nisar_eim.webapp.server import Application, ObservationNotFound, create_server


@pytest.fixture(scope="module")
def data_root(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("webapp")
    granule = write_synthetic_gunw(root / "gunw.h5", rows=40, cols=50)
    process_granule(
        granule,
        observation_id="fixture",
        output_root=root / "processed",
        config=ProcessConfig(render_dpi=60, map_preview_width=220),
        force=True,
    )
    return root / "processed"


def test_index_lists_observations_and_events(data_root):
    app = Application(data_root)
    index = app.index()
    assert [o["observation_id"] for o in index["observations"]] == ["fixture"]
    assert index["app"]["offline"] is True
    assert "no phase-to-displacement conversion" in index["app"]["disclaimer"].lower()
    assert index["reference_events"][0]["id"] == "us6000t7zc"
    assert index["layer_descriptions"]["coherence"]["units"].startswith("dimensionless")
    observation = index["observations"][0]
    assert observation["phase"]["units"] == "radians"
    assert observation["validation_states"]


def test_observation_payload_exposes_assets_and_map(data_root):
    app = Application(data_root)
    payload = app.observation("fixture")
    assert payload["assets"]["phase_png"]["path"] == "phase.png"
    assert payload["assets"]["phase_tif"]["url"].endswith("/artifact/phase.tif")
    assert set(payload["map"]["images"]) >= {"phase", "coherence", "quality"}
    assert payload["map"]["display_grid"]["crs"] == "EPSG:4326"
    assert payload["metadata"]["layers"]["phase"]["units"] == "radians"
    assert payload["threshold"]["threshold"] == pytest.approx(0.4)


def test_threshold_interpolation(data_root):
    app = Application(data_root)
    result = app.threshold("fixture", 0.55)
    assert result["threshold"] == pytest.approx(0.55)
    assert result["interpolated"] is True
    assert 0 <= result["coverage_percent"] <= 100
    exact = app.threshold("fixture", 0.5)
    assert exact["interpolated"] is False


def test_pixel_sampling_roundtrips_through_the_grid(data_root):
    app = Application(data_root)
    metadata = app.repository.load("fixture")
    geometry = GridGeometry.from_json(metadata["map_view"]["geometry"])
    lon, lat = geometry.lonlat_of(12, 15)

    sample = app.sample("fixture", lon=lon, lat=lat)
    assert sample["row"] == 12 and sample["col"] == 15
    assert sample["lon"] == pytest.approx(lon, abs=1e-9)
    assert sample["units"]["phase"] == "radians"
    assert sample["window"]["valid_pixels"] >= 1

    by_index = app.sample("fixture", row=12, col=15)
    assert by_index["phase_radians"] == pytest.approx(sample["phase_radians"])
    assert by_index["connected_component"] == sample["connected_component"]
    assert by_index["mask"]["available"] is True


def test_sample_outside_grid_is_rejected(data_root):
    app = Application(data_root)
    metadata = app.repository.load("fixture")
    geometry = GridGeometry.from_json(metadata["map_view"]["geometry"])
    lon, lat = geometry.lonlat_of(0, 0)
    with pytest.raises(NisarError):
        app.sample("fixture", lon=lon + 30.0, lat=lat)
    with pytest.raises(NisarError):
        app.sample("fixture")


def test_artifacts_are_whitelisted(data_root):
    app = Application(data_root)
    path = app.artifact("fixture", "phase.png")
    assert path.exists()
    with pytest.raises(ObservationNotFound):
        app.artifact("fixture", "../metadata.json")
    with pytest.raises(ObservationNotFound):
        app.artifact("fixture", "does_not_exist.txt")


def test_unknown_observation(data_root):
    app = Application(data_root)
    with pytest.raises(ObservationNotFound):
        app.observation("nope")


def test_offline_browsing_without_raw_granule(data_root, tmp_path):
    offline_root = tmp_path / "processed"
    shutil.copytree(data_root / "fixture", offline_root / "fixture")
    metadata_path = offline_root / "fixture" / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["source"]["path"] = str(tmp_path / "missing_granule.h5")
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    app = Application(offline_root)
    payload = app.observation("fixture")  # derived products still load
    assert payload["assets"]["phase_png"]["url"]
    with pytest.raises(NisarError) as excinfo:
        app.sample("fixture", row=12, col=15)
    assert "raw granule is not available" in excinfo.value.message.lower()


def test_http_endpoints(data_root):
    server = create_server("127.0.0.1", 0, data_root)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        def get(path: str):
            with urllib.request.urlopen(base + path, timeout=20) as response:
                return response.status, response.headers.get("Content-Type", ""), response.read()

        status, content_type, body = get("/")
        assert status == 200 and "text/html" in content_type
        assert b"NISAR // Earth in Motion" in body

        status, _, body = get("/static/app.js")
        assert status == 200 and b'"use strict"' in body
        # navigation is wired in the served bundle (regression: missing binding)
        assert b"bindNavigation" in body and b"loadIndex" in body

        status, content_type, body = get("/static/styles.css")
        assert status == 200 and "text/css" in content_type

        status, content_type, body = get("/api/health")
        assert status == 200 and "application/json" in content_type
        assert json.loads(body)["status"] == "ok"

        status, content_type, body = get("/api/index")
        assert status == 200 and "application/json" in content_type
        assert json.loads(body)["observations"][0]["observation_id"] == "fixture"

        status, _, body = get("/api/observations/fixture")
        assert status == 200
        assert json.loads(body)["assets"]["phase_png"]["path"] == "phase.png"

        status, content_type, body = get("/api/observations/fixture/artifact/phase.png")
        assert status == 200 and content_type == "image/png" and body[:8] == b"\x89PNG\r\n\x1a\n"

        status, content_type, body = get("/api/observations/fixture/preview/coherence.bin")
        assert status == 200 and "application/octet-stream" in content_type

        status, _, body = get("/api/observations/fixture/threshold?value=0.6")
        assert status == 200 and json.loads(body)["threshold"] == pytest.approx(0.6)

        with pytest.raises(urllib.error.HTTPError) as excinfo:
            get("/api/observations/fixture/artifact/secret.txt")
        assert excinfo.value.code == 404
        with pytest.raises(urllib.error.HTTPError) as excinfo:
            get("/api/observations/missing")
        assert excinfo.value.code == 404
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
