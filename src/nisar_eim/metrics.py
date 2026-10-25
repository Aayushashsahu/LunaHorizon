from __future__ import annotations

import numpy as np


def valid_coherence_mask(coherence: np.ndarray, threshold: float = 0.4) -> np.ndarray:
    """Return a conservative validity mask for coherence values in [0, 1]."""
    arr = np.asarray(coherence, dtype=float)
    if not 0.0 <= threshold <= 1.0:
        raise ValueError("threshold must be between 0 and 1")
    return np.isfinite(arr) & (arr >= threshold) & (arr <= 1.0)


def phase_to_los_displacement(
    phase_radians: np.ndarray,
    wavelength_m: float,
) -> np.ndarray:
    """Convert interferometric phase (radians) to LOS displacement (meters).

    For a conventional two-way interferometric phase relationship:
        d_los = phase * wavelength / (4*pi)

    This is a LOS measurement, not a vertical or full 3D displacement.
    Product-specific processing/corrections and sign conventions must be
    documented by the caller before presentation to users.
    """
    if not np.isfinite(wavelength_m) or wavelength_m <= 0:
        raise ValueError("wavelength_m must be a positive finite value")
    phase = np.asarray(phase_radians, dtype=float)
    return phase * wavelength_m / (4.0 * np.pi)


def robust_summary(values: np.ndarray, valid_mask: np.ndarray | None = None) -> dict[str, float | int]:
    """Compute a compact, NaN-safe summary for a scientific quicklook."""
    arr = np.asarray(values, dtype=float)
    if valid_mask is not None:
        mask = np.asarray(valid_mask, dtype=bool)
        if mask.shape != arr.shape:
            raise ValueError("valid_mask must have the same shape as values")
        arr = arr[mask]
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        raise ValueError("No finite values available for summary")
    return {
        "count": int(arr.size),
        "min": float(np.min(arr)),
        "max": float(np.max(arr)),
        "median": float(np.median(arr)),
        "p05": float(np.percentile(arr, 5)),
        "p95": float(np.percentile(arr, 95)),
        "mean": float(np.mean(arr)),
    }
