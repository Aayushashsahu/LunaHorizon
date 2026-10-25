"""Mask decoding and quality filtering for NISAR GUNW layers.

The GUNW product mask is *encoded*, not boolean.  Two layouts exist in the wild:

* ``UByte`` masks (older/sample products, product spec Rev E) store a three-digit
  decimal number in one byte: water flag, reference subswath, secondary subswath.
* ``UInt32`` masks (current production products) keep the same three digits in
  bits 0-7 and add anomaly flags in bits 8-23 and an ionospheric-fill flag in
  bit 24.

Both are decoded here from the low byte, which is why ``value & 0xFF`` is used
rather than integer division on the full 32-bit value: pixels with anomaly bits
set (e.g. ``0x0100000C``) would otherwise decode to the wrong subswath digits.
This is a real defect in ``scripts/quicklook_gunw_georef_v3.py`` as it stood.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

FILL_VALUE_COMPONENTS = 65535

#: Bits of the UInt32 mask layout, per the product dataset description.
MASK_BITS = {
    "subswath_and_water": (0, 8),
    "secondary_anomaly": (8, 16),
    "reference_anomaly": (16, 24),
    "ionosphere_filled": (24, 25),
}


@dataclass(frozen=True)
class MaskFields:
    """Decoded components of a GUNW product mask."""

    valid: np.ndarray
    water: np.ndarray
    reference_subswath: np.ndarray
    secondary_subswath: np.ndarray
    reference_anomaly: np.ndarray
    secondary_anomaly: np.ndarray
    ionosphere_filled: np.ndarray
    fill: np.ndarray
    encoding: str

    def coverage_json(self) -> dict[str, Any]:
        total = int(self.valid.size)
        return {
            "encoding": self.encoding,
            "total_pixels": total,
            "valid_pixels": int(self.valid.sum()),
            "invalid_pixels": int(total - self.valid.sum()),
            "water_pixels": int(self.water.sum()),
            "water_fraction_of_valid": _fraction(self.water, self.valid),
            "ionosphere_filled_pixels": int(self.ionosphere_filled.sum()),
            "reference_anomaly_pixels": int((self.reference_anomaly > 0).sum()),
            "secondary_anomaly_pixels": int((self.secondary_anomaly > 0).sum()),
            "fill_pixels": int(self.fill.sum()),
        }


def _fraction(part: np.ndarray, whole: np.ndarray) -> float | None:
    count = int(np.count_nonzero(whole))
    if count == 0:
        return None
    return float(np.count_nonzero(part) / count)


def decode_mask(
    values: np.ndarray,
    *,
    fill_value: Any = 255,
    description: str | None = None,
) -> MaskFields:
    """Decode a GUNW mask into boolean fields.

    Parameters
    ----------
    values:
        Raw mask array as stored in the product.  Must be integer typed.
    fill_value:
        The dataset's ``_FillValue`` attribute (``255`` for GUNW masks).
    description:
        Dataset description, used only to label the detected encoding.

    Raises
    ------
    ValueError
        If the array is not integer typed or its values cannot represent a
        three-digit GUNW mask.
    """
    arr = np.asarray(values)
    if arr.ndim != 2:
        raise ValueError(f"Mask must be two-dimensional, got shape {arr.shape}.")
    if not np.issubdtype(arr.dtype, np.integer):
        raise ValueError(f"Mask must be an integer array, got dtype {arr.dtype}.")
    if arr.size == 0:
        raise ValueError("Mask array is empty.")

    raw = arr.astype(np.uint32, copy=False)
    low = raw & 0xFF
    water_digit = (low // 100) % 10
    reference_digit = (low // 10) % 10
    secondary_digit = low % 10

    fill_int = _as_fill_int(fill_value)
    if fill_int is not None:
        fill = raw == fill_int
    else:
        fill = np.zeros(raw.shape, dtype=bool)

    # A water digit of 0 or 1 is meaningful; 2+ appears only in fill-style values.
    valid = (~fill) & (water_digit <= 1) & (reference_digit > 0) & (secondary_digit > 0)

    uint32_layout = arr.dtype.itemsize >= 4
    if uint32_layout:
        reference_anomaly = ((raw >> 16) & 0xFF).astype(np.uint16)
        secondary_anomaly = ((raw >> 8) & 0xFF).astype(np.uint16)
        ionosphere_filled = ((raw >> 24) & 0x1).astype(bool)
        encoding = "uint32_bitfield_with_anomalies"
    else:
        reference_anomaly = np.zeros(raw.shape, dtype=np.uint16)
        secondary_anomaly = np.zeros(raw.shape, dtype=np.uint16)
        ionosphere_filled = np.zeros(raw.shape, dtype=bool)
        encoding = "uint8_three_digit"

    if description and "Bits 0-7" in description:
        encoding = "uint32_bitfield_with_anomalies"

    return MaskFields(
        valid=valid,
        water=valid & (water_digit == 1),
        reference_subswath=reference_digit.astype(np.uint8),
        secondary_subswath=secondary_digit.astype(np.uint8),
        reference_anomaly=reference_anomaly,
        secondary_anomaly=secondary_anomaly,
        ionosphere_filled=ionosphere_filled,
        fill=fill,
        encoding=encoding,
    )


def _as_fill_int(fill_value: Any) -> int | None:
    if fill_value is None:
        return None
    try:
        value = float(fill_value)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(value):
        return None
    return int(value)


def finite_values(arr: np.ndarray) -> np.ndarray:
    """Boolean mask of finite entries."""
    return np.isfinite(np.asarray(arr))


def combine_validity(
    *,
    phase: np.ndarray,
    mask_fields: MaskFields | None = None,
    fill_value: Any = np.nan,
    coherence: np.ndarray | None = None,
    coherence_threshold: float | None = None,
    components: np.ndarray | None = None,
    component_label: int | None = None,
    exclude_ionosphere_filled: bool = False,
) -> np.ndarray:
    """Combine measurement, mask and quality conditions into one validity mask.

    Every condition is recorded by the caller in the output metadata; this
    function only evaluates them.  ``coherence_threshold`` is a user-facing
    exploratory filter, never a product-defined truth.
    """
    phase_arr = np.asarray(phase)
    if phase_arr.ndim != 2:
        raise ValueError(f"Phase must be two-dimensional, got {phase_arr.shape}.")
    valid = np.isfinite(phase_arr)
    if fill_value is not None:
        try:
            fill = float(fill_value)
        except (TypeError, ValueError):
            fill = None
        if fill is not None and np.isfinite(fill):
            valid &= phase_arr != fill
    if mask_fields is not None:
        if mask_fields.valid.shape != valid.shape:
            raise ValueError(
                f"Mask shape {mask_fields.valid.shape} does not match phase {valid.shape}."
            )
        valid &= mask_fields.valid
        if exclude_ionosphere_filled:
            valid &= ~mask_fields.ionosphere_filled
    if coherence is not None:
        coh = np.asarray(coherence)
        if coh.shape != valid.shape:
            raise ValueError(
                f"Coherence shape {coh.shape} does not match phase {valid.shape}."
            )
        valid &= np.isfinite(coh)
        if coherence_threshold is not None:
            threshold = validate_threshold(coherence_threshold)
            valid &= coh >= threshold
    if components is not None:
        cc = np.asarray(components)
        if cc.shape != valid.shape:
            raise ValueError(
                f"Connected-components shape {cc.shape} does not match phase {valid.shape}."
            )
        if component_label is not None:
            valid &= cc == component_label
    return valid


def validate_threshold(threshold: float) -> float:
    value = float(threshold)
    if not np.isfinite(value) or not 0.0 <= value <= 1.0:
        raise ValueError("Coherence threshold must be a finite value between 0 and 1.")
    return value


def connectivity_summary(
    components: np.ndarray,
    valid: np.ndarray,
    *,
    fill_value: Any = FILL_VALUE_COMPONENTS,
    top_n: int = 8,
) -> dict[str, Any]:
    """Describe connected components among valid pixels.

    Label ``0`` is a legitimate component label in GUNW products; only the
    ``_FillValue`` (``65535``) marks missing data.  Labels are therefore never
    discarded by value, only by the accompanying validity mask.
    """
    cc = np.asarray(components)
    mask = np.asarray(valid, dtype=bool)
    if cc.shape != mask.shape:
        raise ValueError(f"Components shape {cc.shape} does not match mask {mask.shape}.")
    if not np.issubdtype(cc.dtype, np.integer):
        raise ValueError(f"Connected components must be integer typed, got {cc.dtype}.")

    fill_int = _as_fill_int(fill_value)
    usable = mask & (cc != (fill_int if fill_int is not None else -1))
    if not usable.any():
        return {
            "component_count": 0,
            "valid_pixels": 0,
            "largest_component": None,
            "largest_component_fraction": None,
            "components": [],
            "label_semantics": "0 is a valid label; 65535 (fill) is missing data",
        }

    labels, counts = np.unique(cc[usable], return_counts=True)
    order = np.argsort(counts)[::-1]
    total = int(counts.sum())
    top = [
        {
            "label": int(labels[i]),
            "pixels": int(counts[i]),
            "fraction_of_valid": float(counts[i] / total),
        }
        for i in order[:top_n]
    ]
    largest = top[0]
    return {
        "component_count": int(labels.size),
        "valid_pixels": total,
        "largest_component": largest["label"],
        "largest_component_fraction": largest["fraction_of_valid"],
        "components": top,
        "label_semantics": "0 is a valid label; 65535 (fill) is missing data",
    }


def largest_component_label(components: np.ndarray, valid: np.ndarray, *, fill_value: Any = FILL_VALUE_COMPONENTS) -> int | None:
    """Return the label covering the most valid pixels, or ``None``."""
    summary = connectivity_summary(components, valid, fill_value=fill_value, top_n=1)
    return summary["largest_component"]


def coherence_range_report(coherence: np.ndarray) -> dict[str, Any]:
    """Report values outside the documented [0, 1] range without clipping them."""
    coh = np.asarray(coherence, dtype=np.float64)
    finite = np.isfinite(coh)
    n = int(finite.sum())
    if n == 0:
        return {"finite_pixels": 0, "below_zero": 0, "above_one": 0, "within_range": 0}
    values = coh[finite]
    below = int(np.count_nonzero(values < 0.0))
    above = int(np.count_nonzero(values > 1.0))
    return {
        "finite_pixels": n,
        "below_zero": below,
        "above_one": above,
        "within_range": int(n - below - above),
        "documented_range": [0.0, 1.0],
        "note": (
            "Coherence magnitude is documented in the interval [0, 1]; values "
            "outside it are reported, not clipped, in the scientific arrays."
        ),
    }
