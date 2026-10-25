"""Statistics tests: explicit validity, NaN/inf handling and display limits."""

from __future__ import annotations

import numpy as np
import pytest

from nisar_eim.errors import EmptyDataError
from nisar_eim.statistics import (
    display_limits,
    summarize,
    threshold_table,
    window_summary,
)


def test_summarize_excludes_nan_and_inf():
    values = np.array([[1.0, np.nan], [np.inf, -np.inf]])
    summary = summarize(values, name="test")
    assert summary.measured_pixels == 1
    assert summary.median == 1.0
    assert summary.coverage_fraction == pytest.approx(0.25)


def test_summarize_respects_explicit_validity_mask_and_keeps_zero():
    values = np.array([[0.0, 5.0], [10.0, 15.0]])
    valid = np.array([[True, False], [True, False]])
    summary = summarize(values, valid)
    assert summary.measured_pixels == 2
    assert summary.minimum == 0.0
    assert summary.maximum == 10.0


def test_summarize_all_invalid_raises_by_default():
    with pytest.raises(EmptyDataError) as excinfo:
        summarize(np.full((3, 3), np.nan))
    assert "no valid measurements" in excinfo.value.message.lower()
    empty = summarize(np.full((3, 3), np.nan), allow_empty=True)
    assert empty.measured_pixels == 0
    assert empty.median is None


def test_summarize_shape_mismatch():
    with pytest.raises(ValueError):
        summarize(np.zeros((2, 2)), np.ones((3, 3), dtype=bool))


def test_summarize_constant_and_outliers():
    constant = summarize(np.full((4, 4), 3.0))
    assert constant.minimum == constant.maximum == 3.0
    values = np.array([[0.0] * 99 + [1e6]])
    summary = summarize(values)
    assert summary.maximum == 1e6
    assert summary.median == 0.0
    assert summary.p95 == 0.0


def test_threshold_table_monotonic_coverage():
    rng = np.random.default_rng(3)
    coherence = rng.random((20, 20)).astype(np.float32)
    phase = rng.normal(5.0, 1.0, (20, 20)).astype(np.float32)
    valid = np.ones((20, 20), dtype=bool)
    rows = threshold_table(coherence, phase, valid, thresholds=(0.0, 0.5, 1.0))
    assert rows[0]["valid_pixels"] >= rows[1]["valid_pixels"] >= rows[2]["valid_pixels"]
    assert rows[0]["coverage_percent"] == pytest.approx(100.0)
    assert rows[2]["valid_pixels"] == 0
    assert rows[2]["phase_median"] is None
    assert rows[1]["coherence_median"] >= 0.5


def test_threshold_table_rejects_bad_thresholds():
    valid = np.ones((2, 2), dtype=bool)
    with pytest.raises(ValueError):
        threshold_table(np.ones((2, 2)), np.ones((2, 2)), valid, thresholds=(1.5,))


def test_display_limits_and_saturation_counts():
    values = np.concatenate([np.zeros(98), np.array([-100.0, 100.0])]).reshape(10, 10)
    limits = display_limits(values, lower=2, upper=98)
    assert limits["constant"] is True  # the 2nd/98th percentiles are identical
    assert limits["vmin"] == pytest.approx(-1.0)
    assert limits["vmax"] == pytest.approx(1.0)
    assert limits["saturated_low_pixels"] == 1
    assert limits["saturated_high_pixels"] == 1


def test_display_limits_empty():
    limits = display_limits(np.full((2, 2), np.nan))
    assert limits["valid_pixels"] == 0
    assert limits["vmin"] < limits["vmax"]


def test_window_summary():
    phase = np.array([[1.0, 2.0], [np.nan, 4.0]])
    coherence = np.array([[0.5, 0.6], [0.7, 0.9]])
    valid = np.array([[True, True], [True, False]])
    summary = window_summary(phase, coherence, valid)
    assert summary["valid_pixels"] == 2
    assert summary["phase_median"] == pytest.approx(1.5)
    assert summary["coherence_median"] == pytest.approx(0.55)
