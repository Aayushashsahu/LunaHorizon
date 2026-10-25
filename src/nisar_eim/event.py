"""Independent verification that a granule actually covers a target event.

Acquisition dates bracketing an earthquake prove nothing about spatial coverage.
This module takes independently sourced event coordinates (USGS ComCat), maps
them into the granule's own grid, and reports:

* whether the epicentre falls inside the raster bounds and inside the product's
  own WGS84 footprint;
* how far away the nearest pixel with a valid measurement is;
* how much usable (valid, coherent) data exists in a local window.

The window criteria below are **this application's exploratory screening rules**,
not product specifications and not a statement that deformation was measured.
"""

from __future__ import annotations

import json
import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from importlib import resources
from typing import Any

import numpy as np
from shapely.geometry import Point

from .geospatial import GridGeometry
from .quality import connectivity_summary

#: Local window radii in pixels, used to describe data availability around an event.
WINDOW_RADII_PX = (2, 20, 125)  # ~0.2 km, 1.6 km, 10 km at 80 m posting

#: Exploratory screening rules (documented, not product definitions).
USABLE_MIN_VALID_FRACTION = 0.20
USABLE_MIN_MEDIAN_COHERENCE = 0.30
EXPLORATORY_COHERENCE_THRESHOLD = 0.40

REFERENCE_RESOURCE = "data/venezuela_2026_earthquakes.json"


def load_reference_events() -> dict[str, Any]:
    """Load the bundled, independently sourced event reference file."""
    text = resources.files("nisar_eim").joinpath(REFERENCE_RESOURCE).read_text(encoding="utf-8")
    return json.loads(text)


@dataclass
class EventAssessment:
    """Geographic and data-availability assessment for one reference event."""

    event: dict[str, Any]
    inside_raster_bounds: bool
    inside_product_footprint: bool | None
    row: float | None
    col: float | None
    easting: float | None
    northing: float | None
    nearest_pixel: dict[str, Any] | None
    windows: list[dict[str, Any]] = field(default_factory=list)
    status: str = "unknown"
    notes: list[str] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        return {
            "event": self.event,
            "inside_raster_bounds": self.inside_raster_bounds,
            "inside_product_footprint": self.inside_product_footprint,
            "row_col_fractional": [self.row, self.col],
            "easting_northing": [self.easting, self.northing],
            "nearest_valid_pixel": self.nearest_pixel,
            "windows": self.windows,
            "status": self.status,
            "notes": self.notes,
        }


def assess_events(
    geometry: GridGeometry,
    *,
    phase: np.ndarray,
    coherence: np.ndarray,
    valid: np.ndarray,
    components: np.ndarray | None,
    mask_fields: Any | None,
    events: Iterable[dict[str, Any]],
    footprint: Any | None = None,
    footprint_source: str = "grid_extent",
    max_search_km: float = 50.0,
) -> dict[str, Any]:
    """Assess every reference event against the granule's data.

    ``footprint`` is the authoritative image footprint when the product provides
    one (``identification/boundingPolygon``); otherwise the densified grid extent
    is used and ``footprint_source`` records that weaker basis.
    """
    if footprint is None:
        footprint = geometry.footprint_wgs84()
    assessments: list[EventAssessment] = []
    for event in events:
        assessments.append(
            _assess_one(
                geometry,
                footprint,
                event,
                phase=phase,
                coherence=coherence,
                valid=valid,
                components=components,
                max_search_km=max_search_km,
            )
        )

    any_inside = any(a.inside_raster_bounds for a in assessments)
    any_usable = any(a.status == "inside_usable" for a in assessments)
    return {
        "reference_source": "USGS ComCat (see bundled reference file)",
        "footprint_source": footprint_source,
        "criteria": {
            "window_radii_px": list(WINDOW_RADII_PX),
            "window_radii_km": [round(r * geometry.dx / 1000.0, 2) for r in WINDOW_RADII_PX],
            "usable_min_valid_fraction": USABLE_MIN_VALID_FRACTION,
            "usable_min_median_coherence": USABLE_MIN_MEDIAN_COHERENCE,
            "exploratory_coherence_threshold": EXPLORATORY_COHERENCE_THRESHOLD,
            "statement": (
                "These are exploratory screening rules defined by this application, "
                "not NISAR product requirements. Passing them does not establish that "
                "earthquake deformation was measured."
            ),
        },
        "events": [a.to_json() for a in assessments],
        "summary": {
            "events_inside_raster_bounds": sum(a.inside_raster_bounds for a in assessments),
            "events_with_usable_local_data": sum(
                a.status == "inside_usable" for a in assessments
            ),
            "footprint_overlaps_any_event": any_inside,
            "local_data_usable_for_any_event": any_usable,
            "displacement_interpretation_validated": False,
            "displacement_interpretation_reason": (
                "The application presents unwrapped phase in radians and coherence. "
                "No phase-to-displacement conversion is applied because the product "
                "does not itself document the sign convention, and ionospheric, "
                "tropospheric and solid-Earth-tide corrections are included in the "
                "product but not applied to the phase."
            ),
        },
    }


def _assess_one(
    geometry: GridGeometry,
    footprint: Any,
    event: dict[str, Any],
    *,
    phase: np.ndarray,
    coherence: np.ndarray,
    valid: np.ndarray,
    components: np.ndarray | None,
    max_search_km: float,
) -> EventAssessment:
    lat = float(event["latitude"])
    lon = float(event["longitude"])
    easting, northing = geometry.lonlat_to_map(lon, lat)
    row_f, col_f = geometry.map_to_pixel(easting, northing)
    inside_bounds = geometry.contains_map(easting, northing)
    inside_poly = bool(footprint.contains(Point(lon, lat)))

    notes: list[str] = []
    if not inside_bounds:
        notes.append("Epicentre falls outside the raster's map extent.")
    elif not inside_poly:
        notes.append(
            "Epicentre falls inside the raster's bounding box but outside the "
            "densified WGS84 footprint polygon (possible for swath edges)."
        )

    row = round(row_f)
    col = round(col_f)
    nearest = None
    if 0 <= row < geometry.height and 0 <= col < geometry.width:
        nearest = _nearest_valid(
            geometry,
            phase=phase,
            coherence=coherence,
            valid=valid,
            row=row,
            col=col,
            max_search_px=round(max_search_km * 1000.0 / geometry.dx),
        )

    windows = []
    for radius in WINDOW_RADII_PX:
        windows.append(
            _window_stats(
                geometry,
                phase=phase,
                coherence=coherence,
                valid=valid,
                components=components,
                row=row,
                col=col,
                radius=radius,
            )
        )

    status = _classify(inside_bounds, nearest, windows)
    if status == "inside_marginal":
        notes.append(
            "Local window data exist but fall below this application's exploratory "
            "coverage/coherence screening rules."
        )
    elif status == "inside_no_data":
        notes.append(
            "No valid measurement within the search radius; the epicentre may be "
            "offshore, outside the valid swath, or fully decorrelated."
        )

    return EventAssessment(
        event=event,
        inside_raster_bounds=inside_bounds,
        inside_product_footprint=inside_poly if inside_bounds else False,
        row=row_f if inside_bounds else None,
        col=col_f if inside_bounds else None,
        easting=easting if inside_bounds else None,
        northing=northing if inside_bounds else None,
        nearest_pixel=nearest,
        windows=windows,
        status=status,
        notes=notes,
    )


def _classify(inside_bounds: bool, nearest: dict[str, Any] | None, windows: Sequence[dict[str, Any]]) -> str:
    if not inside_bounds:
        return "outside_footprint"
    usable_window = windows[-1] if windows else None
    if nearest is None:
        return "inside_no_data"
    if usable_window:
        valid_fraction = usable_window.get("valid_fraction") or 0.0
        median_coh = usable_window.get("coherence_median")
        if (
            valid_fraction >= USABLE_MIN_VALID_FRACTION
            and median_coh is not None
            and median_coh >= USABLE_MIN_MEDIAN_COHERENCE
        ):
            return "inside_usable"
    return "inside_marginal"


def _nearest_valid(
    geometry: GridGeometry,
    *,
    phase: np.ndarray,
    coherence: np.ndarray,
    valid: np.ndarray,
    row: int,
    col: int,
    max_search_px: int,
) -> dict[str, Any] | None:
    r0 = max(0, row - max_search_px)
    r1 = min(geometry.height, row + max_search_px + 1)
    c0 = max(0, col - max_search_px)
    c1 = min(geometry.width, col + max_search_px + 1)
    sub = valid[r0:r1, c0:c1]
    if not sub.any():
        return None
    rr, cc = np.nonzero(sub)
    dr = (rr + r0 - row).astype(np.float64)
    dc = (cc + c0 - col).astype(np.float64)
    dist_px = np.hypot(dr, dc)
    idx = int(np.argmin(dist_px))
    nearest_row = int(rr[idx] + r0)
    nearest_col = int(cc[idx] + c0)
    distance_km = float(dist_px[idx] * geometry.dx / 1000.0)
    lon, lat = geometry.lonlat_of(nearest_row, nearest_col)
    return {
        "row": nearest_row,
        "col": nearest_col,
        "distance_km": round(distance_km, 4),
        "lon": round(float(lon), 6),
        "lat": round(float(lat), 6),
        "phase_radians": _clean_float(phase[nearest_row, nearest_col]),
        "coherence": _clean_float(coherence[nearest_row, nearest_col]),
        "searched_radius_km": round(max_search_px * geometry.dx / 1000.0, 2),
    }


def _window_stats(
    geometry: GridGeometry,
    *,
    phase: np.ndarray,
    coherence: np.ndarray,
    valid: np.ndarray,
    components: np.ndarray | None,
    row: int,
    col: int,
    radius: int,
) -> dict[str, Any]:
    r0 = max(0, row - radius)
    r1 = min(geometry.height, row + radius + 1)
    c0 = max(0, col - radius)
    c1 = min(geometry.width, col + radius + 1)
    ph = phase[r0:r1, c0:c1]
    coh = coherence[r0:r1, c0:c1]
    vm = valid[r0:r1, c0:c1]
    selected = vm & np.isfinite(ph) & np.isfinite(coh)
    n = int(ph.size)
    out: dict[str, Any] = {
        "radius_px": radius,
        "radius_km": round(radius * geometry.dx / 1000.0, 3),
        "window_rows": [r0, r1],
        "window_cols": [c0, c1],
        "pixels": n,
        "valid_pixels": int(selected.sum()),
        "valid_fraction": float(selected.sum() / n) if n else None,
        "coherence_median": None,
        "coherence_p90": None,
        "fraction_coherence_at_or_above_exploratory_threshold": None,
        "phase_median": None,
        "phase_p05": None,
        "phase_p95": None,
    }
    if selected.any():
        coh_sel = coh[selected]
        ph_sel = ph[selected]
        out.update(
            {
                "coherence_median": float(np.median(coh_sel)),
                "coherence_p90": float(np.percentile(coh_sel, 90)),
                "fraction_coherence_at_or_above_exploratory_threshold": float(
                    np.count_nonzero(coh_sel >= EXPLORATORY_COHERENCE_THRESHOLD) / coh_sel.size
                ),
                "phase_median": float(np.median(ph_sel)),
                "phase_p05": float(np.percentile(ph_sel, 5)),
                "phase_p95": float(np.percentile(ph_sel, 95)),
            }
        )
    if components is not None:
        comp_summary = connectivity_summary(components[r0:r1, c0:c1], selected, top_n=3)
        out["components"] = {
            "component_count": comp_summary["component_count"],
            "largest_component": comp_summary["largest_component"],
            "largest_component_fraction": comp_summary["largest_component_fraction"],
        }
    return out


def _clean_float(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None
