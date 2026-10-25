"""Mask decoding and quality-filter tests."""

from __future__ import annotations

import numpy as np
import pytest

from nisar_eim.quality import (
    coherence_range_report,
    combine_validity,
    connectivity_summary,
    decode_mask,
    largest_component_label,
    validate_threshold,
)


def test_uint8_three_digit_mask():
    raw = np.array([[11, 111, 255], [10, 1, 0]], dtype=np.uint8)
    fields = decode_mask(raw, fill_value=255)
    assert fields.encoding == "uint8_three_digit"
    # Valid requires both a reference and a secondary subswath digit: 10 has no
    # secondary subswath, 1 has no reference subswath, 0 is masked, 255 is fill.
    assert fields.valid.tolist() == [[True, True, False], [False, False, False]]
    assert fields.water.tolist() == [[False, True, False], [False, False, False]]
    assert fields.reference_subswath.tolist() == [[1, 1, 5], [1, 0, 0]]
    assert fields.secondary_subswath.tolist() == [[1, 1, 5], [0, 1, 0]]


def test_uint32_mask_anomaly_bits_do_not_corrupt_subswath_digits():
    """0x0100000C has bit 24 set; the subswath digits are still 1 and 2.

    The previous decoder divided the full 32-bit integer by 10 and read the
    wrong digit for any pixel with anomaly or ionosphere bits set.
    """
    raw = np.array([[0x0100000C, 0x0001000B, 0x0100007C]], dtype=np.uint32)
    fields = decode_mask(raw, fill_value=255)
    assert fields.valid.tolist() == [[True, True, True]]
    assert fields.reference_subswath.tolist() == [[1, 1, 2]]
    assert fields.secondary_subswath.tolist() == [[2, 1, 4]]
    assert fields.ionosphere_filled.tolist() == [[True, False, True]]
    assert fields.reference_anomaly.tolist() == [[0, 1, 0]]
    assert int(fields.water.sum()) == 1  # 0x...7C -> water digit 1
    assert fields.encoding == "uint32_bitfield_with_anomalies"


def test_mask_rejects_wrong_types_and_shapes():
    with pytest.raises(ValueError):
        decode_mask(np.zeros((2, 2), dtype=np.float32))
    with pytest.raises(ValueError):
        decode_mask(np.zeros((2, 2, 2), dtype=np.uint8))
    with pytest.raises(ValueError):
        decode_mask(np.zeros((0, 0), dtype=np.uint8))


def test_combine_validity_keeps_valid_zero_and_applies_threshold():
    phase = np.array([[0.0, 1.0, np.nan, 2.0]], dtype=np.float32)
    mask = decode_mask(np.array([[11, 11, 11, 0]], dtype=np.uint8), fill_value=255)
    coherence = np.array([[0.55, 0.2, np.nan, 0.9]], dtype=np.float32)
    valid = combine_validity(
        phase=phase, mask_fields=mask, coherence=coherence, coherence_threshold=0.4
    )
    assert valid.tolist() == [[True, False, False, False]]
    # A zero-valued phase is a real measurement, not a missing value.
    assert combine_validity(phase=phase, mask_fields=mask)[0, 0]


def test_combine_validity_shape_mismatch():
    phase = np.zeros((2, 3), dtype=np.float32)
    coherence = np.zeros((3, 2), dtype=np.float32)
    with pytest.raises(ValueError):
        combine_validity(phase=phase, coherence=coherence)


def test_combine_validity_component_label_and_ionosphere_flag():
    phase = np.ones((2, 2), dtype=np.float32)
    mask = decode_mask(
        np.array([[0x0100000B, 11], [11, 11]], dtype=np.uint32), fill_value=255
    )
    components = np.array([[1, 1], [2, 2]], dtype=np.uint16)
    valid = combine_validity(
        phase=phase,
        mask_fields=mask,
        components=components,
        component_label=1,
        exclude_ionosphere_filled=True,
    )
    assert valid.tolist() == [[False, True], [False, False]]


def test_threshold_validation():
    assert validate_threshold(0.4) == 0.4
    for bad in (-0.1, 1.1, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            validate_threshold(bad)


def test_connectivity_summary_keeps_label_zero():
    components = np.array([[0, 0, 1], [0, 65535, 1], [2, 2, 2]], dtype=np.uint16)
    valid = np.array([[1, 1, 1], [1, 0, 1], [1, 1, 1]], dtype=bool)
    summary = connectivity_summary(components, valid)
    assert summary["component_count"] == 3
    assert summary["largest_component"] == 2
    assert summary["largest_component_fraction"] == pytest.approx(3 / 8)
    assert largest_component_label(components, valid) == 2


def test_connectivity_summary_empty():
    components = np.full((2, 2), 65535, dtype=np.uint16)
    valid = np.zeros((2, 2), dtype=bool)
    summary = connectivity_summary(components, valid)
    assert summary["component_count"] == 0
    assert summary["largest_component"] is None


def test_coherence_range_report_flags_out_of_range_values():
    report = coherence_range_report(np.array([[0.2, 1.4], [-0.1, np.nan]]))
    assert report["finite_pixels"] == 3
    assert report["below_zero"] == 1
    assert report["above_one"] == 1
    assert report["within_range"] == 1
