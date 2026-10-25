"""Product reader tests using synthetic GUNW files (no multi-GB downloads)."""

from __future__ import annotations

import h5py
import numpy as np
import pytest
from conftest import write_synthetic_gunw

from nisar_eim.errors import GeoreferencingError, ProductFormatError
from nisar_eim.product_reader import open_product, structure_summary


def test_resolves_coordinates_from_the_raster_dimension_scales(tmp_path):
    path = write_synthetic_gunw(tmp_path / "gunw.h5", rows=12, cols=20)
    product = open_product(path)

    assert product.geometry.width == 20
    assert product.geometry.height == 12
    assert product.geometry.epsg == 32619
    assert product.grid_resolution.method == "hdf5_dimension_scale"
    # The dimension scale attached to the raster is the authority, and in the
    # GUNW layout the unwrapped grid's coordinate vectors live on the group.
    assert product.grid_resolution.x_path.endswith("/unwrappedInterferogram/xCoordinates")
    assert product.grid_resolution.x_coords.size == 20
    assert product.geometry.dx == pytest.approx(80.0)
    assert product.phase.units == "radians"
    assert product.coherence.units == "1"
    assert product.mask_path.endswith("/unwrappedInterferogram/mask")
    assert product.wavelength_m == pytest.approx(299_792_458.0 / 1.239e9)


def test_does_not_pick_the_four_times_longer_wrapped_coordinates(tmp_path):
    """Regression guard: the wrapped grid coordinates are 4x longer."""
    path = write_synthetic_gunw(tmp_path / "gunw.h5", rows=10, cols=16, look_factor=4)
    with h5py.File(path, "r") as h5:
        wrapped_x = h5["science/LSAR/GUNW/grids/frequencyA/wrappedInterferogram/HH/xCoordinates"]
        unwrapped_x = h5["science/LSAR/GUNW/grids/frequencyA/unwrappedInterferogram/xCoordinates"]
        assert wrapped_x.shape[0] == 4 * unwrapped_x.shape[0]

    product = open_product(path)
    assert product.geometry.width == 16  # unwrapped raster width, not 64
    assert product.grid_resolution.x_coords.size == 16
    assert product.grid_resolution.x_path != wrapped_x.name


def test_sibling_coordinates_work_without_dimension_scales(tmp_path):
    path = write_synthetic_gunw(
        tmp_path / "gunw.h5", rows=12, cols=18, with_dimension_scales=False
    )
    product = open_product(path)
    assert product.geometry.width == 18
    assert product.grid_resolution.method.startswith("sibling_group:")


def test_wrong_length_coordinates_raise_actionable_error(tmp_path):
    path = write_synthetic_gunw(
        tmp_path / "gunw.h5",
        rows=10,
        cols=16,
        with_dimension_scales=False,
        mismatched_unwrapped_coordinates=True,
    )
    with pytest.raises(GeoreferencingError) as excinfo:
        open_product(path)
    details = excinfo.value.details
    assert details["raster_shape_rows_cols"] == [10, 16]
    assert details["coordinate_ratio_x"] == "4x"
    assert details["grid_inventory"]
    assert "20 m wrapped vs 80 m unwrapped" in details["hint"]
    # The message tells the operator the raw file is untouched and what to do.
    rendered = excinfo.value.render()
    assert "unwrappedPhase" in rendered
    assert "coordinate_ratio_x" in rendered


def test_unsupported_product_type_is_rejected(tmp_path):
    path = write_synthetic_gunw(tmp_path / "gcov.h5", product_type="GCOV")
    with pytest.raises(ProductFormatError) as excinfo:
        open_product(path)
    assert "supports the L2 Geocoded Unwrapped Interferogram" in excinfo.value.message


def test_missing_phase_dataset_is_rejected(tmp_path):
    path = write_synthetic_gunw(tmp_path / "gunw.h5")
    with h5py.File(path, "a") as h5:
        del h5["science/LSAR/GUNW/grids/frequencyA/unwrappedInterferogram/HH/unwrappedPhase"]
    with pytest.raises(ProductFormatError) as excinfo:
        open_product(path)
    assert "unwrapped phase dataset is missing" in excinfo.value.message.lower()
    assert "available_in_group" in excinfo.value.details


def test_mask_shape_mismatch_is_rejected(tmp_path):
    path = write_synthetic_gunw(tmp_path / "gunw.h5", rows=10, cols=12)
    with h5py.File(path, "a") as h5:
        group = h5["science/LSAR/GUNW/grids/frequencyA/unwrappedInterferogram"]
        del group["mask"]
        mask = group.create_dataset("mask", data=np.zeros((9, 12), dtype=np.uint32))
        mask.attrs["_FillValue"] = 255
    with pytest.raises(ProductFormatError) as excinfo:
        open_product(path)
    assert "mask shape" in excinfo.value.message.lower()


def test_corrupt_file_is_rejected_without_crashing(tmp_path):
    path = tmp_path / "broken.h5"
    path.write_bytes(b"this is not an HDF5 file")
    with pytest.raises(ProductFormatError) as excinfo:
        open_product(path)
    assert "could not be opened as HDF5" in excinfo.value.message


def test_missing_file_reports_path(tmp_path):
    with pytest.raises(ProductFormatError) as excinfo:
        open_product(tmp_path / "absent.h5")
    assert "does not exist" in excinfo.value.message


def test_uint8_mask_product_opens(tmp_path):
    path = write_synthetic_gunw(tmp_path / "gunw.h5", mask_dtype="uint8")
    product = open_product(path)
    mask = product.read_mask()
    assert mask is not None and mask.dtype == np.uint8


def test_structure_summary_is_metadata_only(tmp_path):
    path = write_synthetic_gunw(tmp_path / "gunw.h5", rows=8, cols=10)
    with h5py.File(path, "r") as h5:
        summary = structure_summary(h5)
    assert summary["datasets"]
    assert any(d["path"].endswith("unwrappedPhase") for d in summary["datasets"])
    phase = next(d for d in summary["datasets"] if d["path"].endswith("unwrappedPhase"))
    assert phase["shape"] == [8, 10]
    assert phase["attributes"]["units"] == "radians"


def test_missing_identification_is_rejected(tmp_path):
    path = write_synthetic_gunw(tmp_path / "gunw.h5")
    with h5py.File(path, "a") as h5:
        del h5["science/LSAR/identification"]
    with pytest.raises(ProductFormatError) as excinfo:
        open_product(path)
    assert "identification" in excinfo.value.message.lower()


def test_window_read_slices_are_clipped(tmp_path):
    path = write_synthetic_gunw(tmp_path / "gunw.h5", rows=10, cols=12)
    product = open_product(path)
    window = product.read_window("phase", row=0, col=0, half=3)
    assert window.shape == (4, 4)
    corner = product.read_window("phase", row=9, col=11, half=3)
    assert corner.shape == (4, 4)
