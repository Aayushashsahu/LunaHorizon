"""Geospatial grid interpretation tests.

The central regression: a GUNW file contains a 20 m wrapped grid and an 80 m
unwrapped grid, each with its own coordinate vectors. The coordinate vector of
the wrapped grid is exactly four times longer than the unwrapped raster. A grid
reader must reject that pairing instead of shrinking the coordinates to fit.
"""

from __future__ import annotations

import numpy as np
import pytest
from shapely.geometry import Point

from nisar_eim.errors import GeoreferencingError
from nisar_eim.geospatial import (
    GridGeometry,
    build_geometry,
    spacing_from_axis,
)


def axes(rows: int, cols: int, posting: float = 80.0, x0: float = 500040.0, y0: float = 1_200_000.0):
    x = x0 + posting * np.arange(cols, dtype=float)
    y = y0 - posting * np.arange(rows, dtype=float)
    return x, y


def test_build_geometry_uses_pixel_centres():
    rows, cols = 5, 8
    x, y = axes(rows, cols)
    geometry = build_geometry(x, y, 32619, (rows, cols), spacing_hints=(80.0, -80.0))

    assert geometry.shape == (rows, cols)
    assert geometry.dx == 80.0 and geometry.dy == 80.0
    assert geometry.is_north_up
    # Pixel (0,0) centre equals the first coordinate pair ...
    assert geometry.pixel_centre(0, 0) == (x[0], y[0])
    # ... and the affine transform places the raster corner half a pixel outside.
    corner = geometry.transform @ (0.0, 0.0)
    assert corner == pytest.approx((x[0] - 40.0, y[0] + 40.0))
    # Pixel (1,1) is one posting away from pixel (0,0).
    assert geometry.pixel_centre(1, 1) == pytest.approx((x[0] + 80.0, y[0] - 80.0))
    # Half-pixel offsets land on edges.
    assert geometry.map_to_pixel(x[0] + 40.0, y[0] - 40.0) == pytest.approx((0.5, 0.5))

    bounds = geometry.bounds
    assert bounds.left == pytest.approx(x[0] - 40.0)
    assert bounds.right == pytest.approx(x[-1] + 40.0)
    assert bounds.top == pytest.approx(y[0] + 40.0)
    assert bounds.bottom == pytest.approx(y[-1] - 40.0)


def test_dimension_mismatch_is_rejected_with_diagnostics():
    rows, cols = 6, 7
    x, y = axes(rows, cols)
    with pytest.raises(GeoreferencingError) as excinfo:
        build_geometry(x, y, 32619, (rows + 2, cols))
    details = excinfo.value.details
    assert details["raster_rows"] == rows + 2
    assert details["y_coordinate_count"] == rows
    assert "do not match" in excinfo.value.message.lower()


def test_exact_four_times_wrapped_unwrapped_case_is_rejected():
    """The reported bug: 16956/4239 = 4 and 16596/4149 = 4."""
    rows, cols = 4149, 4239
    x, y = axes(rows, cols, posting=80.0, x0=410440.0, y0=1_365_800.0)
    wrapped_x = 410410.0 + 20.0 * np.arange(cols * 4, dtype=float)
    wrapped_y = 1_365_830.0 - 20.0 * np.arange(rows * 4, dtype=float)

    with pytest.raises(GeoreferencingError) as excinfo:
        build_geometry(wrapped_x, wrapped_y, 32619, (rows, cols))
    details = excinfo.value.details
    assert details["raster_cols"] == cols
    assert details["x_coordinate_count"] == cols * 4
    assert details["x_length_ratio"] == "4x"
    assert details["y_length_ratio"] == "4x"
    assert "different map grid" in details["interpretation"]

    # The correctly paired coordinates still build a valid geometry for the
    # same raster: the fix is to select the right grid, not to subsample.
    geometry = build_geometry(x, y, 32619, (rows, cols), spacing_hints=(80.0, -80.0))
    assert geometry.width == cols and geometry.height == rows
    assert geometry.dx == 80.0


def test_ascending_y_axis_is_supported_without_flipping_data():
    rows, cols = 4, 4
    x = 500000.0 + 10.0 * np.arange(cols)
    y = 1_000_000.0 + 10.0 * np.arange(rows)  # south-up
    geometry = build_geometry(x, y, 32619, (rows, cols))
    assert geometry.y_descending is False
    assert geometry.transform.e == pytest.approx(10.0)
    assert geometry.pixel_centre(0, 0) == (x[0], y[0])
    assert geometry.pixel_centre(rows - 1, 0) == pytest.approx((x[0], y[0] + 10.0 * (rows - 1)))
    assert geometry.bounds.bottom == pytest.approx(y[0] - 5.0)
    assert geometry.bounds.top == pytest.approx(y[-1] + 5.0)
    geometry.validate_roundtrip()


def test_descending_x_axis_is_supported():
    rows, cols = 3, 5
    x = 500000.0 - 10.0 * np.arange(cols)
    y = 1_000_000.0 - 10.0 * np.arange(rows)
    geometry = build_geometry(x, y, 32619, (rows, cols))
    assert geometry.x_descending is True
    assert geometry.transform.a == pytest.approx(-10.0)
    geometry.validate_roundtrip()


def test_irregular_spacing_is_rejected():
    rows, cols = 4, 6
    x, y = axes(rows, cols)
    x[3] += 3.0
    with pytest.raises(GeoreferencingError) as excinfo:
        build_geometry(x, y, 32619, (rows, cols))
    assert "not regularly spaced" in excinfo.value.message
    assert excinfo.value.details["irregular_steps"] >= 1


def test_spacing_hint_mismatch_is_rejected():
    rows, cols = 4, 6
    x, y = axes(rows, cols)
    with pytest.raises(GeoreferencingError) as excinfo:
        build_geometry(x, y, 32619, (rows, cols), spacing_hints=(20.0, -20.0))
    assert "disagrees" in excinfo.value.message


def test_invalid_epsg_is_rejected():
    rows, cols = 3, 3
    x, y = axes(rows, cols)
    with pytest.raises(GeoreferencingError):
        build_geometry(x, y, 0, (rows, cols))


def test_non_monotonic_axis_is_rejected():
    x = np.array([0.0, 10.0, 5.0, 20.0])
    y = np.array([100.0, 90.0, 80.0, 70.0])
    with pytest.raises(GeoreferencingError):
        build_geometry(x, y, 32619, (4, 4))


def test_duplicate_coordinates_are_rejected():
    x = np.array([0.0, 10.0, 10.0, 30.0])
    y = np.array([100.0, 90.0, 80.0, 70.0])
    with pytest.raises(GeoreferencingError):
        build_geometry(x, y, 32619, (4, 4))


def test_spacing_from_axis():
    assert spacing_from_axis(np.array([0.0, 10.0, 20.0]), "x") == 10.0
    assert spacing_from_axis(np.array([20.0, 10.0, 0.0]), "y") == 10.0


def test_footprint_and_lonlat_roundtrip():
    rows, cols = 40, 50
    x, y = axes(rows, cols)
    geometry = build_geometry(x, y, 32619, (rows, cols))
    lon, lat = geometry.lonlat_of(rows / 2, cols / 2)
    assert -180 < lon < 180 and -90 < lat < 90
    polygon = geometry.footprint_wgs84(step=16)
    assert polygon.contains(Point(lon, lat))
    row, col = geometry.rowcol_of_lonlat(lon, lat)
    assert row == pytest.approx(rows / 2, abs=1e-6)
    assert col == pytest.approx(cols / 2, abs=1e-6)
    assert geometry.contains_lonlat(lon, lat)


def test_geometry_json_roundtrip():
    rows, cols = 12, 18
    x, y = axes(rows, cols)
    geometry = build_geometry(x, y, 32619, (rows, cols), method="test")
    restored = GridGeometry.from_json(geometry.to_json())
    assert restored.epsg == geometry.epsg
    assert restored.shape == geometry.shape
    transform = geometry.transform
    assert list(restored.transform)[:6] == pytest.approx(list(transform)[:6])
    assert restored.pixel_centre(3, 4) == geometry.pixel_centre(3, 4)
