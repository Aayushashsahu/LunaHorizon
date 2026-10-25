"""Statistics for scientific raster layers.

All summaries are computed over a caller-supplied validity mask so that
"invalid pixels", "valid zero-valued measurements" and "filtered pixels" stay
distinct.  Quantiles are exact for the pixels handed in; no resampling or
interpolation is applied to the measurements.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np

from .errors import EmptyDataError


@dataclass(frozen=True)
class ArraySummary:
    """Summary of a raster layer over a validity mask."""

    name: str
    total_pixels: int
    measured_pixels: int
    coverage_fraction: float | None
    minimum: float | None
    maximum: float | None
    mean: float | None
    std: float | None
    median: float | None
    p02: float | None
    p05: float | None
    p25: float | None
    p75: float | None
    p95: float | None
    p98: float | None
    units: str | None = None

    def to_json(self) -> dict[str, Any]:
        data = asdict(self)
        data["coverage_percent"] = (
            None if self.coverage_fraction is None else round(100.0 * self.coverage_fraction, 3)
        )
        data.pop("coverage_fraction")
        return data


def summarize(
    values: np.ndarray,
    valid: np.ndarray | None = None,
    *,
    name: str = "values",
    units: str | None = None,
    allow_empty: bool = False,
) -> ArraySummary:
    """Compute an exact summary over ``valid`` entries of ``values``.

    ``values`` may contain NaN; entries that are not finite are always excluded
    in addition to ``valid``.  A valid measurement whose value is exactly zero is
    retained.
    """
    arr = np.asarray(values)
    if arr.ndim != 2:
        raise ValueError(f"{name} must be a two-dimensional array, got {arr.shape}.")
    mask = np.isfinite(arr)
    if valid is not None:
        vm = np.asarray(valid, dtype=bool)
        if vm.shape != arr.shape:
            raise ValueError(
                f"Validity mask for {name} has shape {vm.shape}, expected {arr.shape}."
            )
        mask &= vm

    total = int(arr.size)
    count = int(mask.sum())
    if count == 0:
        if not allow_empty:
            raise EmptyDataError(
                f"No valid measurements remain for '{name}'.",
                details={
                    "total_pixels": total,
                    "valid_pixels": 0,
                    "hint": "Check the product mask, coherence threshold and component filter.",
                },
            )
        return ArraySummary(
            name=name,
            total_pixels=total,
            measured_pixels=0,
            coverage_fraction=0.0,
            minimum=None,
            maximum=None,
            mean=None,
            std=None,
            median=None,
            p02=None,
            p05=None,
            p25=None,
            p75=None,
            p95=None,
            p98=None,
            units=units,
        )

    data = np.asarray(arr[mask], dtype=np.float64)
    quantiles = np.percentile(data, [2, 5, 25, 50, 75, 95, 98])
    return ArraySummary(
        name=name,
        total_pixels=total,
        measured_pixels=count,
        coverage_fraction=count / total,
        minimum=float(data.min()),
        maximum=float(data.max()),
        mean=float(data.mean()),
        std=float(data.std(ddof=0)),
        median=float(quantiles[3]),
        p02=float(quantiles[0]),
        p05=float(quantiles[1]),
        p25=float(quantiles[2]),
        p75=float(quantiles[4]),
        p95=float(quantiles[5]),
        p98=float(quantiles[6]),
        units=units,
    )


def threshold_table(
    coherence: np.ndarray,
    phase: np.ndarray,
    valid: np.ndarray,
    thresholds: Sequence[float] = (0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8),
) -> list[dict[str, Any]]:
    """Coverage and phase statistics as a function of a coherence threshold.

    The threshold is an *exploratory quality filter*: the product does not define
    a universally correct coherence cut-off.  The unfiltered layer is always
    preserved alongside this table.
    """
    coh = np.asarray(coherence, dtype=np.float64)
    ph = np.asarray(phase, dtype=np.float64)
    vm = np.asarray(valid, dtype=bool)
    if coh.shape != ph.shape or vm.shape != ph.shape:
        raise ValueError(
            f"Shape mismatch: coherence {coh.shape}, phase {ph.shape}, mask {vm.shape}."
        )
    base = vm & np.isfinite(coh) & np.isfinite(ph)
    total = int(base.size)
    rows: list[dict[str, Any]] = []
    for threshold in thresholds:
        t = float(threshold)
        if not 0.0 <= t <= 1.0:
            raise ValueError("Coherence thresholds must lie in [0, 1].")
        selected = base & (coh >= t)
        count = int(selected.sum())
        row: dict[str, Any] = {
            "threshold": t,
            "valid_pixels": count,
            "coverage_percent": round(100.0 * count / total, 3) if total else None,
            "fraction_of_unfiltered": (
                round(count / int(base.sum()), 4) if int(base.sum()) else None
            ),
        }
        if count:
            vals = ph[selected]
            row.update(
                {
                    "phase_median": float(np.median(vals)),
                    "phase_p05": float(np.percentile(vals, 5)),
                    "phase_p95": float(np.percentile(vals, 95)),
                    "coherence_median": float(np.median(coh[selected])),
                }
            )
        else:
            row.update(
                {
                    "phase_median": None,
                    "phase_p05": None,
                    "phase_p95": None,
                    "coherence_median": None,
                }
            )
        rows.append(row)
    return rows


def window_summary(
    phase: np.ndarray,
    coherence: np.ndarray | None,
    valid: np.ndarray,
    *,
    name: str = "window",
) -> dict[str, Any]:
    """Compact summary for a small pixel-inspection window."""
    ph = np.asarray(phase, dtype=np.float64)
    vm = np.asarray(valid, dtype=bool)
    if ph.shape != vm.shape:
        raise ValueError(f"Shape mismatch: phase {ph.shape}, mask {vm.shape}.")
    selected = vm & np.isfinite(ph)
    out: dict[str, Any] = {
        "name": name,
        "pixels": int(ph.size),
        "valid_pixels": int(selected.sum()),
        "valid_fraction": float(selected.mean()) if ph.size else None,
    }
    if selected.any():
        out["phase_median"] = float(np.median(ph[selected]))
        out["phase_min"] = float(ph[selected].min())
        out["phase_max"] = float(ph[selected].max())
    else:
        out["phase_median"] = None
        out["phase_min"] = None
        out["phase_max"] = None
    if coherence is not None:
        coh = np.asarray(coherence, dtype=np.float64)
        if coh.shape != vm.shape:
            raise ValueError(
                f"Shape mismatch: coherence {coh.shape}, mask {vm.shape}."
            )
        csel = selected & np.isfinite(coh)
        out["coherence_median"] = float(np.median(coh[csel])) if csel.any() else None
        out["coherence_p90"] = float(np.percentile(coh[csel], 90)) if csel.any() else None
    return out


def display_limits(
    values: np.ndarray, valid: np.ndarray | None = None, lower: float = 2.0, upper: float = 98.0
) -> dict[str, Any]:
    """Percentile display limits plus how much data is saturated for display.

    The limits are used only for colour mapping; the arrays written to GeoTIFF
    retain the original measurements.
    """
    arr = np.asarray(values, dtype=np.float64)
    if not 0.0 <= lower < upper <= 100.0:
        raise ValueError("Display percentiles must satisfy 0 <= lower < upper <= 100.")
    mask = np.isfinite(arr)
    if valid is not None:
        vm = np.asarray(valid, dtype=bool)
        if vm.shape != arr.shape:
            raise ValueError("Validity mask shape does not match values.")
        mask &= vm
    count = int(mask.sum())
    if count == 0:
        return {
            "vmin": 0.0,
            "vmax": 1.0,
            "lower_percentile": lower,
            "upper_percentile": upper,
            "saturated_low_pixels": 0,
            "saturated_high_pixels": 0,
            "valid_pixels": 0,
            "constant": False,
        }
    data = arr[mask]
    p_low, p_high = (float(v) for v in np.percentile(data, [lower, upper]))
    # Saturation is measured against the percentile limits themselves, before any
    # expansion applied to keep a constant raster renderable.
    saturated_low = int(np.count_nonzero(data < p_low))
    saturated_high = int(np.count_nonzero(data > p_high))
    constant = bool(np.isclose(p_low, p_high))
    vmin, vmax = p_low, p_high
    if constant:
        vmin, vmax = p_low - 1.0, p_high + 1.0
    return {
        "vmin": float(vmin),
        "vmax": float(vmax),
        "lower_percentile": lower,
        "upper_percentile": upper,
        "saturated_low_pixels": saturated_low,
        "saturated_high_pixels": saturated_high,
        "valid_pixels": count,
        "constant": constant,
    }
