"""End-to-end pipeline tests on small synthetic GUNW granules."""

from __future__ import annotations

import json
from pathlib import Path

import h5py
import numpy as np
import pytest
from conftest import write_synthetic_gunw

from nisar_eim.errors import EmptyDataError
from nisar_eim.pipeline import ProcessConfig, default_observation_id, process_granule

CONFIG = ProcessConfig(render_dpi=60, map_preview_width=220)


def _process(path: Path, tmp_path: Path, **kwargs):
    return process_granule(
        path,
        observation_id=kwargs.pop("observation_id", "synthetic"),
        output_root=kwargs.pop("output_root", tmp_path / "processed"),
        config=kwargs.pop("config", CONFIG),
        force=kwargs.pop("force", True),
        **kwargs,
    )


def test_process_produces_all_required_outputs(tmp_path):
    granule = write_synthetic_gunw(tmp_path / "gunw.h5", rows=24, cols=30)
    stat_before = granule.stat()
    metadata = _process(granule, tmp_path)
    out_dir = Path(metadata["observation_dir"])

    for name in (
        "phase.png",
        "coherence.png",
        "phase.tif",
        "coherence.tif",
        "metadata.json",
        "report.md",
        "validation.json",
        "preview/map_phase.png",
        "preview/map_coherence.png",
        "preview/map_quality.png",
        "preview/coherence_u8.bin",
    ):
        assert (out_dir / name).exists(), f"missing {name}"
        assert (out_dir / name).stat().st_size > 0

    stat_after = granule.stat()
    assert stat_after.st_size == stat_before.st_size
    assert stat_after.st_mtime_ns == stat_before.st_mtime_ns

    reloaded = json.loads((out_dir / "metadata.json").read_text(encoding="utf-8"))
    assert reloaded["observation_id"] == "synthetic"
    assert reloaded["schema_version"] == "1.0"
    assert reloaded["source"]["granule_id"] == granule.stem
    assert reloaded["layers"]["phase"]["units"] == "radians"
    assert reloaded["layers"]["phase"]["dataset_path"].endswith("unwrappedPhase")
    assert reloaded["georeferencing"]["epsg"] == 32619
    assert reloaded["georeferencing"]["pixel_spacing"]["x"] == pytest.approx(80.0)
    assert reloaded["georeferencing"]["product_polygon_check"]["status"] in {"passed", "failed"}
    assert reloaded["validation"]["overall_status"] == "validated_for_phase_and_coherence_display"
    states = {state["id"]: state["status"] for state in reloaded["validation"]["states"]}
    assert states["georeferencing_validated"] == "passed"
    assert states["scientific_interpretation_validated"] == "not_validated"
    assert reloaded["validation"]["geotiff_readback"]["phase"]["passed"] is True
    assert reloaded["validation"]["geotiff_readback"]["coherence"]["passed"] is True
    assert reloaded["map_view"]["display_grid"]["crs"] == "EPSG:4326"
    assert reloaded["map_view"]["legends"]["phase"]["stops"]
    assert reloaded["output_sizes"]["phase_tif"] > 0


def test_statistics_match_independent_calculation(tmp_path):
    granule = write_synthetic_gunw(tmp_path / "gunw.h5", rows=24, cols=30)
    metadata = _process(granule, tmp_path)

    with h5py.File(granule, "r") as h5:
        base = "science/LSAR/GUNW/grids/frequencyA/unwrappedInterferogram"
        phase = h5[f"{base}/HH/unwrappedPhase"][()]
        coherence = h5[f"{base}/HH/coherenceMagnitude"][()]
        mask = h5[f"{base}/mask"][()].astype(np.uint32)
    low = mask & 0xFF
    valid = (
        (mask != 255)
        & ((low // 10) % 10 > 0)
        & (low % 10 > 0)
        & np.isfinite(phase)
        & np.isfinite(coherence)
    )
    expected_count = int(valid.sum())
    expected_median = float(np.median(phase[valid]))
    expected_coh_median = float(np.median(coherence[valid]))

    stats = metadata["layers"]["phase"]["statistics"]
    assert stats["measured_pixels"] == expected_count
    assert stats["median"] == pytest.approx(expected_median, rel=1e-9, abs=1e-6)
    assert metadata["layers"]["coherence"]["statistics"]["median"] == pytest.approx(
        expected_coh_median, rel=1e-9, abs=1e-6
    )
    assert stats["coverage_percent"] == pytest.approx(
        100.0 * expected_count / phase.size, abs=1e-3
    )


def test_report_identifies_granule_and_not_a_displacement_map(tmp_path):
    granule = write_synthetic_gunw(
        tmp_path / "gunw.h5",
        rows=20,
        cols=24,
        reference_date="2026-06-13T10:06:56.000000000",
        secondary_date="2026-06-25T10:06:55.000000000",
    )
    metadata = _process(granule, tmp_path)
    report = (Path(metadata["observation_dir"]) / "report.md").read_text(encoding="utf-8")
    assert granule.stem in report
    assert "**not** a displacement map in metres" in report
    assert "Unwrapped phase" in report
    assert "radians" in report
    assert "predates the NISAR launch" not in report
    assert "Scientific interpretation validated | **not_validated**" in report


def test_pre_launch_sample_is_flagged(tmp_path):
    granule = write_synthetic_gunw(
        tmp_path / "sample.h5",
        reference_date="2008-10-12T06:09:11.567105263",
        secondary_date="2008-11-27T06:10:00.442763158",
    )
    metadata = _process(granule, tmp_path)
    assert metadata["source"]["is_pre_launch_sample"] is True
    assert any("predates the NISAR launch" in warning for warning in metadata["warnings"])
    assert any(check["id"] == "sample_product_notice" for check in metadata["checks"])
    report = (Path(metadata["observation_dir"]) / "report.md").read_text(encoding="utf-8")
    assert "predates the NISAR launch" in report


def test_cache_is_used_until_forced(tmp_path):
    granule = write_synthetic_gunw(tmp_path / "gunw.h5")
    first = _process(granule, tmp_path)
    metadata_path = Path(first["observation_dir"]) / "metadata.json"
    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    payload["generated_utc"] = "CACHED-MARKER"
    metadata_path.write_text(json.dumps(payload), encoding="utf-8")

    second = _process(granule, tmp_path, force=False)
    assert second["generated_utc"] == "CACHED-MARKER"

    third = _process(granule, tmp_path, force=True)
    assert third["generated_utc"] != "CACHED-MARKER"


def test_all_invalid_product_fails_loudly(tmp_path):
    granule = write_synthetic_gunw(tmp_path / "gunw.h5", all_invalid=True)
    with pytest.raises(EmptyDataError) as excinfo:
        _process(granule, tmp_path)
    assert "finite values" in excinfo.value.message.lower()


def test_events_outside_synthetic_footprint_are_reported_honestly(tmp_path):
    granule = write_synthetic_gunw(tmp_path / "gunw.h5")
    metadata = _process(granule, tmp_path)
    assessment = metadata["event_assessment"]
    assert assessment["summary"]["footprint_overlaps_any_event"] is False
    assert all(event["status"] == "outside_footprint" for event in assessment["events"])
    assert assessment["summary"]["displacement_interpretation_validated"] is False
    assert any("does not contain any reference event" in warning for warning in metadata["warnings"])


def test_threshold_table_has_expected_structure(tmp_path):
    granule = write_synthetic_gunw(tmp_path / "gunw.h5")
    metadata = _process(granule, tmp_path)
    table = metadata["quality"]["threshold_table"]
    assert [row["threshold"] for row in table] == [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
    counts = [row["valid_pixels"] for row in table]
    assert counts == sorted(counts, reverse=True)


def test_default_observation_id_is_metadata_derived(tmp_path):
    from nisar_eim.product_reader import open_product

    granule = write_synthetic_gunw(tmp_path / "gunw.h5")
    product = open_product(granule)
    observation_id = default_observation_id(product)
    assert observation_id.startswith("nisar_gunw_t162_f7_")
    assert "20260613" in observation_id
    assert "20260625" in observation_id


def test_missing_layer_raises_typed_error(tmp_path):
    granule = write_synthetic_gunw(tmp_path / "gunw.h5", with_connected_components=False)
    metadata = _process(granule, tmp_path)
    assert metadata["layers"]["connected_components"] is None
    assert "connected_components" not in metadata["map_view"]["images"]
