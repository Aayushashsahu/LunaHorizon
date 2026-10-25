"""Rendering and export tests: PNG, RGBA previews, GeoTIFF read-back."""

from __future__ import annotations

import math

import numpy as np
import pytest
import rasterio
from PIL import Image

from nisar_eim.geospatial import build_geometry
from nisar_eim.rendering import (
    RenderingError,
    colormap_stops,
    layer_rgba,
    render_quicklook,
    resolve_style,
    save_map_image,
    validate_geotiff,
    write_coherence_preview,
    write_geotiff,
)


def geometry(rows: int = 10, cols: int = 12):
    x = 500040.0 + 80.0 * np.arange(cols)
    y = 1_200_000.0 - 80.0 * np.arange(rows)
    return build_geometry(x, y, 32619, (rows, cols))


def test_write_and_reopen_geotiff(tmp_path):
    geo = geometry()
    data = np.arange(geo.height * geo.width, dtype=np.float32).reshape(geo.shape)
    data[0, 0] = np.nan
    path = tmp_path / "phase.tif"
    write_geotiff(
        out_tif=path,
        data=data,
        geometry=geo,
        band_description="unwrapped interferometric phase (radians)",
        tags={"NISAR_GRANULE_ID": "TEST_GRANULE", "NISAR_INT_LIST": [1, 2, 3]},
    )
    check = validate_geotiff(
        path,
        expected_shape=geo.shape,
        expected_epsg=32619,
        expected_transform=geo.transform,
    )
    assert check["passed"], check["errors"]
    assert check["epsg"] == 32619
    assert check["shape"] == [geo.height, geo.width]
    assert math.isnan(check["nodata"])
    assert "radians" in check["band_descriptions"][0]
    assert check["tags"]["NISAR_GRANULE_ID"] == "TEST_GRANULE"
    assert check["tags"]["NISAR_INT_LIST"] == "[1, 2, 3]"

    with rasterio.open(path) as src:
        assert src.crs.to_epsg() == 32619
        assert src.transform.almost_equals(geo.transform)
        reopened = src.read(1)
    assert np.isnan(reopened[0, 0])
    assert reopened[1, 1] == pytest.approx(data[1, 1])


def test_validate_geotiff_detects_wrong_crs(tmp_path):
    geo = geometry()
    path = tmp_path / "coherence.tif"
    write_geotiff(
        out_tif=path,
        data=np.ones(geo.shape, dtype=np.float32),
        geometry=geo,
        band_description="coherence",
        tags={},
    )
    check = validate_geotiff(
        path,
        expected_shape=geo.shape,
        expected_epsg=4326,
        expected_transform=geo.transform,
    )
    assert check["passed"] is False
    assert any("CRS" in error for error in check["errors"])


def test_write_geotiff_rejects_shape_mismatch(tmp_path):
    geo = geometry()
    with pytest.raises(RenderingError):
        write_geotiff(
            out_tif=tmp_path / "bad.tif",
            data=np.zeros((3, 3), dtype=np.float32),
            geometry=geo,
            band_description="bad",
            tags={},
        )


def test_map_image_has_transparent_invalid_pixels(tmp_path):
    rows, cols = 8, 8
    data = np.linspace(0, 10, rows * cols, dtype=np.float32).reshape(rows, cols)
    valid = np.ones((rows, cols), dtype=bool)
    valid[:2, :] = False
    style = resolve_style("phase", data, valid, units="radians")
    out = tmp_path / "map.png"
    info = save_map_image(style, data, valid, out, downsample=1)
    assert info["width"] == cols and info["height"] == rows
    image = Image.open(out).convert("RGBA")
    pixels = np.asarray(image)
    assert pixels[:2, :, 3].max() == 0
    assert pixels[4:, :, 3].min() == 255


def test_coherence_preview_encoding_keeps_invalid_distinct(tmp_path):
    coherence = np.array([[0.0, 0.5], [1.0, np.nan]], dtype=np.float32)
    valid = np.array([[True, True], [True, False]])
    out_bin = tmp_path / "coherence_u8.bin"
    meta = write_coherence_preview(
        coherence=coherence,
        valid=valid,
        out_bin=out_bin,
        out_meta=tmp_path / "coherence_u8.json",
        downsample=1,
    )
    encoded = np.frombuffer(out_bin.read_bytes(), dtype=np.uint8).reshape(2, 2)
    assert encoded[0, 0] == 0
    assert encoded[0, 1] == 100
    assert encoded[1, 0] == 200
    assert encoded[1, 1] == 255  # invalid, not the same as zero coherence
    assert meta["encoding"].startswith("uint8")


def test_quicklook_png_is_written(tmp_path):
    geo = geometry(rows=20, cols=24)
    data = np.linspace(-5, 5, geo.height * geo.width, dtype=np.float32).reshape(geo.shape)
    valid = np.ones(geo.shape, dtype=bool)
    valid[:, :2] = False
    style = resolve_style("phase", data, valid, units="radians")
    out = tmp_path / "quicklook.png"
    info = render_quicklook(
        style=style,
        data=data,
        valid=valid,
        geometry=geo,
        out_png=out,
        subtitle="reference -> secondary",
        source_line="Dataset: test",
        warning="Not a displacement map.",
        dpi=60,
        figure_size=(6, 5),
    )
    assert out.exists() and out.stat().st_size > 5000
    assert info["display_limits"]["vmin"] < info["display_limits"]["vmax"]


def test_quicklook_survives_all_invalid(tmp_path):
    geo = geometry(rows=12, cols=12)
    data = np.full(geo.shape, np.nan, dtype=np.float32)
    valid = np.zeros(geo.shape, dtype=bool)
    style = resolve_style("coherence", data, valid, units="1")
    out = tmp_path / "empty.png"
    render_quicklook(
        style=style,
        data=data,
        valid=valid,
        geometry=geo,
        out_png=out,
        subtitle="all invalid",
        source_line="Dataset: test",
        warning="No valid data.",
        dpi=60,
        figure_size=(4, 4),
    )
    assert out.exists()


def test_layer_rgba_shape_mismatch():
    style = resolve_style("phase", np.zeros((2, 2)), np.ones((2, 2), dtype=bool), units="rad")
    with pytest.raises(RenderingError):
        layer_rgba(style, np.zeros((3, 3)), np.ones((2, 2), dtype=bool))


def test_colormap_stops():
    stops = colormap_stops("viridis", 5)
    assert len(stops) == 5
    assert stops[0]["t"] == 0.0 and stops[-1]["t"] == 1.0
    assert all(stop["hex"].startswith("#") and len(stop["hex"]) == 7 for stop in stops)
