"""Geospatial grid interpretation for geocoded NISAR products.

A NISAR L2 GUNW file contains *several* map grids inside a single granule:

* ``grids/frequencyA/wrappedInterferogram``  - wrapped interferogram, 20 m posting
* ``grids/frequencyA/unwrappedInterferogram`` - unwrapped phase + coherence, 80 m posting
* ``grids/frequencyA/pixelOffsets``           - sub-pixel offsets, 80 m posting
* ``metadata/radarGrid``                      - geometry lookup tables, decimated

Each of those groups carries **its own** ``xCoordinates``, ``yCoordinates``,
``projection`` and ``mask`` datasets (NISAR L2 GUNW product specification
JPL D-102272, section 5).  The coordinate vectors are therefore never shared
between grids.  Historically ``scripts/quicklook_gunw_georef_v3.py`` resolved
``xCoordinates`` by searching the whole file for a dataset with that basename;
the first hit belonged to the 20 m *wrapped* grid (16956 x 16596) while the
raster being rendered came from the 80 m *unwrapped* grid (4239 x 4149), which
produced the exact 4x shape mismatch reported by the user.

This module works the other way round: the raster is the anchor.  Coordinate
vectors are resolved from the raster's own HDF5 dimension scales (CF-1.7
``DIMENSION_LIST`` / ``REFERENCE_LIST`` links), then from the raster's sibling
and parent groups.  A candidate grid is accepted only when its coordinate
lengths equal the raster shape, its axes are strictly monotonic and regularly
spaced, and a valid EPSG code is present.  Anything else raises
:class:`~nisar_eim.errors.GeoreferencingError` with the full diagnostic trail.

Coordinate convention
---------------------
``xCoordinates`` / ``yCoordinates`` are CF-1.7 dimension-scale coordinates for
the *centre* of each pixel (``CLASS = DIMENSION_SCALE``,
``standard_name = projection_x_coordinate``).  The affine transform used for
GeoTIFF export therefore places pixel edges half a pixel outside the first and
last centres.  This is verified by an explicit round-trip check in
:meth:`GridGeometry.validate_roundtrip`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from affine import Affine
from pyproj import CRS, Transformer
from shapely.geometry import Polygon
from shapely.geometry.base import BaseGeometry

from .errors import GeoreferencingError


@dataclass(frozen=True)
class BoundingBox:
    """Map-coordinate extent of a grid, in the units of its CRS."""

    left: float
    bottom: float
    right: float
    top: float

    def to_json(self) -> dict[str, float]:
        return {
            "left": self.left,
            "bottom": self.bottom,
            "right": self.right,
            "top": self.top,
        }


@dataclass(frozen=True)
class GridGeometry:
    """Validated affine georeferencing for one raster grid.

    Attributes
    ----------
    epsg:
        EPSG code taken from the product's ``projection`` dataset attribute.
    width, height:
        Raster shape as ``(columns, rows)``.
    x0, y0:
        Map coordinates of the *centre* of pixel ``(row=0, col=0)``.
    dx, dy:
        Positive pixel spacing in map units.
    x_descending, y_descending:
        Axis orientation of the stored arrays.  ``y_descending`` (row index
        increases southwards) is the normal north-up case.
    method:
        Human-readable description of how the coordinates were resolved,
        recorded in exported metadata for provenance.
    source_paths:
        HDF5 paths of the coordinate and projection datasets that were used.
    """

    epsg: int
    width: int
    height: int
    x0: float
    y0: float
    dx: float
    dy: float
    x_descending: bool = False
    y_descending: bool = True
    method: str = "unspecified"
    source_paths: dict[str, str] = field(default_factory=dict)
    crs_name: str = ""

    # -- basic properties -------------------------------------------------
    @property
    def crs(self) -> CRS:
        return CRS.from_epsg(self.epsg)

    @property
    def shape(self) -> tuple[int, int]:
        """Raster shape as ``(rows, columns)``."""
        return (self.height, self.width)

    @property
    def transform(self) -> Affine:
        """Affine mapping pixel (col, row) *edges* to map coordinates.

        ``Affine`` uses the convention ``x = a*col + b*row + c`` and
        ``y = d*col + e*row + f``.  ``c``/``f`` are the map coordinates of the
        outer corner of pixel (0, 0), i.e. half a pixel outside the centre.
        """
        a = -self.dx if self.x_descending else self.dx
        e = self.dy if not self.y_descending else -self.dy
        c = self.x0 - a / 2.0
        f = self.y0 - e / 2.0
        return Affine(a, 0.0, c, 0.0, e, f)

    @property
    def bounds(self) -> BoundingBox:
        """Outer extent of the grid, from the four transformed raster corners."""
        t = self.transform
        # ``Affine @ (x, y)`` is the current transform operator; ``*`` is pending
        # deprecation in affine 2.4.
        corners = [
            t @ (0.0, 0.0),
            t @ (float(self.width), 0.0),
            t @ (0.0, float(self.height)),
            t @ (float(self.width), float(self.height)),
        ]
        xs = [pt[0] for pt in corners]
        ys = [pt[1] for pt in corners]
        return BoundingBox(
            left=min(xs), right=max(xs), bottom=min(ys), top=max(ys)
        )

    @property
    def is_north_up(self) -> bool:
        return (not self.x_descending) and self.y_descending

    # -- coordinate conversions ------------------------------------------
    def pixel_centre(self, row: float, col: float) -> tuple[float, float]:
        """Map coordinate of a (possibly fractional) pixel index, centre based."""
        x = self.x0 + (-self.dx if self.x_descending else self.dx) * col
        y = self.y0 + (-self.dy if self.y_descending else self.dy) * row
        return (x, y)

    def map_to_pixel(self, x: float, y: float) -> tuple[float, float]:
        """Fractional pixel ``(row, col)`` for a map coordinate.

        The returned indices are continuous: integer values are pixel centres
        and half-integer values lie on pixel edges.
        """
        dx = -self.dx if self.x_descending else self.dx
        dy = -self.dy if self.y_descending else self.dy
        return ((y - self.y0) / dy, (x - self.x0) / dx)

    def contains_map(self, x: float, y: float) -> bool:
        row, col = self.map_to_pixel(x, y)
        return 0.0 <= row <= self.height - 1 and 0.0 <= col <= self.width - 1

    def contains_lonlat(self, lon: float, lat: float) -> bool:
        x, y = self.lonlat_to_map(lon, lat)
        return self.contains_map(x, y)

    def lonlat_of(self, row: float, col: float) -> tuple[float, float]:
        x, y = self.pixel_centre(row, col)
        return self.map_to_lonlat(x, y)

    def rowcol_of_lonlat(self, lon: float, lat: float) -> tuple[float, float]:
        x, y = self.lonlat_to_map(lon, lat)
        return self.map_to_pixel(x, y)

    def lonlat_to_map(self, lon: float, lat: float) -> tuple[float, float]:
        return _to_map_transformer(self.epsg).transform(lon, lat)

    def map_to_lonlat(self, x: float, y: float) -> tuple[float, float]:
        return _to_lonlat_transformer(self.epsg).transform(x, y)

    # -- footprint --------------------------------------------------------
    def footprint_wgs84(self, step: int = 64) -> BaseGeometry:
        """Polygon footprint in EPSG:4326 derived from the grid edges.

        The edges are densified because a projected rectangle maps to a curved
        quadrilateral (or worse on a wide UTM strip).  This footprint is what
        the application compares against independently sourced event
        coordinates.
        """
        # Footprint of the *coverage*, not of the pixel centres.  ``transform``
        # already places its origin half a pixel outside the centre of pixel
        # (0, 0), so corner coordinates are 0..width and 0..height in transform
        # space.  Sampling pixel centres (row/col 0..n-1 through ``lonlat_of``)
        # would inset the footprint by half a pixel on every side - 31x23 of a
        # 32x24 grid, a 7% area shortfall - and break the comparison with the
        # product's identification/boundingPolygon.
        top = left = 0.0
        bottom = float(self.height)
        right = float(self.width)

        n_cols = max(2, int(min(self.width, max(1, self.width // max(1, step)))) + 1)
        n_rows = max(2, int(min(self.height, max(1, self.height // max(1, step)))) + 1)
        col_positions = [left + (right - left) * i / (n_cols - 1) for i in range(n_cols)]
        row_positions = [top + (bottom - top) * i / (n_rows - 1) for i in range(n_rows)]

        def edge_lonlat(row: float, col: float) -> tuple[float, float]:
            x, y = self.transform @ (col, row)
            return self.map_to_lonlat(x, y)

        points: list[tuple[float, float]] = []
        points.extend(edge_lonlat(top, col) for col in col_positions)
        points.extend(edge_lonlat(row, right) for row in row_positions[1:])
        points.extend(edge_lonlat(bottom, col) for col in reversed(col_positions[:-1]))
        points.extend(edge_lonlat(row, left) for row in reversed(row_positions[:-1]))
        polygon = Polygon(points)
        if not polygon.is_valid:
            polygon = polygon.buffer(0)
        return polygon

    # -- validation -------------------------------------------------------
    def validate_roundtrip(self, samples: Sequence[tuple[int, int]] | None = None) -> dict[str, Any]:
        """Check pixel -> map -> pixel and map -> pixel -> map consistency.

        Raises
        ------
        GeoreferencingError
            If the affine transform and the coordinate vectors disagree beyond
            floating point noise.
        """
        if samples is None:
            rows = {0, self.height // 2, self.height - 1}
            cols = {0, self.width // 2, self.width - 1}
            samples = [(r, c) for r in sorted(rows) for c in sorted(cols)]

        transform = self.transform
        max_pixel_error = 0.0
        max_map_error = 0.0
        for row, col in samples:
            x, y = self.pixel_centre(row, col)
            tx, ty = transform @ (col + 0.5, row + 0.5)
            max_map_error = max(max_map_error, abs(tx - x), abs(ty - y))
            r2, c2 = self.map_to_pixel(x, y)
            max_pixel_error = max(max_pixel_error, abs(r2 - row), abs(c2 - col))

        tolerance = 1e-6
        if max_map_error > tolerance or max_pixel_error > tolerance:
            raise GeoreferencingError(
                "Affine transform is inconsistent with the coordinate vectors.",
                details={
                    "max_map_error": f"{max_map_error:.3e}",
                    "max_pixel_error": f"{max_pixel_error:.3e}",
                    "tolerance": tolerance,
                },
            )
        return {
            "checked_pixels": len(samples),
            "max_map_error": max_map_error,
            "max_pixel_error": max_pixel_error,
            "tolerance": tolerance,
            "passed": True,
        }

    @classmethod
    def from_json(cls, data: Mapping[str, Any]) -> GridGeometry:
        """Rebuild a geometry from the JSON written into observation metadata."""
        spacing = data.get("pixel_spacing", {})
        origin = data.get("origin_centre_row0_col0", {})
        return cls(
            epsg=int(data["epsg"]),
            width=int(data["width"]),
            height=int(data["height"]),
            x0=float(origin["x"]),
            y0=float(origin["y"]),
            dx=float(spacing["x"]),
            dy=float(spacing["y"]),
            x_descending=str(data.get("x_axis", "ascending")) == "descending",
            y_descending=str(data.get("y_axis", "descending")) == "descending",
            method=str(data.get("georeferencing_method", "from_metadata")),
            source_paths=dict(data.get("source_datasets", {})),
            crs_name=str(data.get("crs_name", "")),
        )

    def to_json(self) -> dict[str, Any]:
        b = self.bounds
        return {
            "epsg": self.epsg,
            "crs_name": self.crs_name,
            "width": self.width,
            "height": self.height,
            "shape_rows_cols": [self.height, self.width],
            "pixel_spacing": {"x": self.dx, "y": self.dy},
            "pixel_convention": "pixel_centres",
            "x_axis": "descending" if self.x_descending else "ascending",
            "y_axis": "descending" if self.y_descending else "ascending",
            "origin_centre_row0_col0": {"x": self.x0, "y": self.y0},
            "bounds": b.to_json(),
            "transform": list(self.transform)[:6],
            "georeferencing_method": self.method,
            "source_datasets": dict(self.source_paths),
        }


_TRANSFORMER_CACHE: dict[tuple[int, str], Transformer] = {}


def _to_map_transformer(epsg: int) -> Transformer:
    key = (epsg, "to_map")
    if key not in _TRANSFORMER_CACHE:
        _TRANSFORMER_CACHE[key] = Transformer.from_crs(
            "EPSG:4326", CRS.from_epsg(epsg), always_xy=True
        )
    return _TRANSFORMER_CACHE[key]


def _to_lonlat_transformer(epsg: int) -> Transformer:
    key = (epsg, "to_lonlat")
    if key not in _TRANSFORMER_CACHE:
        _TRANSFORMER_CACHE[key] = Transformer.from_crs(
            CRS.from_epsg(epsg), "EPSG:4326", always_xy=True
        )
    return _TRANSFORMER_CACHE[key]


def spacing_from_axis(axis: np.ndarray, name: str) -> float:
    """Return the (positive) spacing of a regularly spaced coordinate axis."""
    diffs = np.diff(axis)
    spacing = float(np.median(np.abs(diffs)))
    if not np.isfinite(spacing) or spacing <= 0:
        raise GeoreferencingError(
            f"{name} does not contain a usable pixel spacing.",
            details={"first_values": np.asarray(axis[:5]).tolist(), "spacing": spacing},
        )
    tolerance = max(1e-6, spacing * 1e-4)
    if not np.allclose(diffs, np.sign(diffs[0]) * spacing, rtol=0, atol=tolerance):
        irregular = int(np.count_nonzero(np.abs(np.abs(diffs) - spacing) > tolerance))
        raise GeoreferencingError(
            f"{name} is not regularly spaced; a simple affine GeoTIFF cannot "
            "represent this grid without inventing coordinates.",
            details={
                "n_samples": int(axis.size),
                "median_spacing": spacing,
                "irregular_steps": irregular,
                "max_deviation": float(np.max(np.abs(np.abs(diffs) - spacing))),
            },
        )
    return spacing


def build_geometry(
    x_coords: np.ndarray,
    y_coords: np.ndarray,
    epsg: int,
    raster_shape: tuple[int, int],
    *,
    spacing_hints: tuple[float | None, float | None] = (None, None),
    method: str = "unspecified",
    source_paths: dict[str, str] | None = None,
) -> GridGeometry:
    """Build and validate a :class:`GridGeometry` from coordinate vectors.

    Parameters
    ----------
    x_coords, y_coords:
        1D coordinate vectors for the columns (x) and rows (y).
    epsg:
        EPSG code read from the product's ``projection`` dataset.
    raster_shape:
        ``(rows, columns)`` of the raster the coordinates must describe.
    spacing_hints:
        Optional ``(xCoordinateSpacing, yCoordinateSpacing)`` values from the
        product.  When present they are cross-checked against the vectors.
    """
    x = np.asarray(x_coords, dtype=np.float64).ravel()
    y = np.asarray(y_coords, dtype=np.float64).ravel()
    rows, cols = raster_shape

    if x.ndim != 1 or y.ndim != 1:  # defensive: ravel above should prevent this
        raise GeoreferencingError("Coordinate datasets must be one-dimensional.")
    if x.size != cols or y.size != rows:
        ratio_x = _describe_ratio(cols, x.size)
        ratio_y = _describe_ratio(rows, y.size)
        raise GeoreferencingError(
            "Coordinate lengths do not match the raster shape.",
            details={
                "raster_rows": rows,
                "raster_cols": cols,
                "y_coordinate_count": int(y.size),
                "x_coordinate_count": int(x.size),
                "x_length_ratio": ratio_x,
                "y_length_ratio": ratio_y,
                "interpretation": (
                    "The coordinates belong to a different map grid than the "
                    "raster. GUNW stores 20 m (wrapped) and 80 m (unwrapped) "
                    "grids with independent coordinate vectors."
                ),
            },
        )
    if x.size < 2 or y.size < 2:
        raise GeoreferencingError(
            "At least two coordinates are required on each axis.",
            details={"x_count": int(x.size), "y_count": int(y.size)},
        )

    # Monotonicity (strict, so duplicate coordinates cannot silently collapse).
    if not (np.all(np.diff(x) > 0) or np.all(np.diff(x) < 0)):
        raise GeoreferencingError(
            "xCoordinates are not strictly monotonic.",
            details={"first_values": x[:5].tolist(), "last_values": x[-5:].tolist()},
        )
    if not (np.all(np.diff(y) > 0) or np.all(np.diff(y) < 0)):
        raise GeoreferencingError(
            "yCoordinates are not strictly monotonic.",
            details={"first_values": y[:5].tolist(), "last_values": y[-5:].tolist()},
        )

    dx = spacing_from_axis(x, "xCoordinates")
    dy = spacing_from_axis(y, "yCoordinates")

    if not isinstance(epsg, (int, np.integer)) or epsg <= 0:
        raise GeoreferencingError(
            "A valid EPSG code is required to georeference the raster.",
            details={"epsg": repr(epsg)},
        )
    try:
        crs = CRS.from_epsg(int(epsg))
    except Exception as exc:  # pragma: no cover - pyproj raises several types
        raise GeoreferencingError(
            "The EPSG code stored in the product is not recognised by PROJ.",
            details={"epsg": int(epsg), "pyproj_error": str(exc)},
        ) from exc

    hint_x, hint_y = spacing_hints
    for name, hint, actual in (("xCoordinateSpacing", hint_x, dx), ("yCoordinateSpacing", hint_y, dy)):
        if hint is None:
            continue
        hint_abs = abs(float(hint))
        tolerance = max(1e-6, hint_abs * 1e-3)
        if abs(hint_abs - actual) > tolerance:
            raise GeoreferencingError(
                f"{name} disagrees with the coordinate vector spacing.",
                details={
                    "declared_spacing": hint_abs,
                    "derived_spacing": actual,
                    "tolerance": tolerance,
                },
            )

    geometry = GridGeometry(
        epsg=int(epsg),
        width=int(cols),
        height=int(rows),
        x0=float(x[0]),
        y0=float(y[0]),
        dx=dx,
        dy=dy,
        x_descending=bool(np.diff(x)[0] < 0),
        y_descending=bool(np.diff(y)[0] < 0),
        method=method,
        source_paths=source_paths or {},
        crs_name=crs.name,
    )
    geometry.validate_roundtrip()
    return geometry


def _describe_ratio(raster: int, coords: int) -> str:
    if raster <= 0 or coords <= 0:
        return "unavailable"
    ratio = coords / raster
    if abs(ratio - round(ratio)) < 1e-9:
        return f"{round(ratio)}x"
    return f"{ratio:.4f}x"
