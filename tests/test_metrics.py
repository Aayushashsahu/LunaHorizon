import numpy as np

from nisar_eim.metrics import (
    phase_to_los_displacement,
    robust_summary,
    valid_coherence_mask,
)


def test_phase_to_los_displacement_zero_is_zero():
    out = phase_to_los_displacement(np.array([0.0, np.pi]), 0.24)
    assert out[0] == 0.0
    assert np.isclose(out[1], 0.06)


def test_coherence_mask():
    mask = valid_coherence_mask(np.array([0.1, 0.4, 0.8, np.nan]), 0.4)
    assert mask.tolist() == [False, True, True, False]


def test_robust_summary():
    s = robust_summary(np.array([1.0, 2.0, np.nan, 4.0]))
    assert s["count"] == 3
    assert s["median"] == 2.0
