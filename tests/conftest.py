"""Synthetic NISAR GUNW fixtures.

The real granule stores a 20 m wrapped grid (16956 x 16596) and an 80 m
unwrapped grid (4239 x 4149) side by side, each with its own coordinate
vectors.  These fixtures reproduce that structure at a small scale so the
georeferencing regression can be tested without a 2.34 GB file.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import h5py
import numpy as np
from pyproj import Transformer


def _scalar(group: h5py.Group, name: str, value: Any) -> None:
    if isinstance(value, str):
        group.create_dataset(name, data=np.bytes_(value))
    else:
        group.create_dataset(name, data=value)


def _wkt_footprint(epsg: int, left: float, bottom: float, right: float, top: float) -> str:
    transformer = Transformer.from_crs(f"EPSG:{epsg}", "EPSG:4326", always_xy=True)
    corners = [
        transformer.transform(left, top),
        transformer.transform(right, top),
        transformer.transform(right, bottom),
        transformer.transform(left, bottom),
    ]
    points = ",".join(f"{lon:.9f} {lat:.9f} 0.0" for lon, lat in corners)
    return f"POLYGON (({points},{points.split(',')[0]}))"


def write_synthetic_gunw(
    path: Path,
    *,
    rows: int = 24,
    cols: int = 32,
    epsg: int = 32619,
    posting: float = 80.0,
    look_factor: int = 4,
    x0: float = 500040.0,
    y0: float = 1_200_000.0,
    reference_date: str = "2026-06-13T10:06:56.000000000",
    secondary_date: str = "2026-06-25T10:06:55.000000000",
    product_type: str = "GUNW",
    with_dimension_scales: bool = True,
    with_sibling_coordinates: bool = True,
    mismatched_unwrapped_coordinates: bool = False,
    all_invalid: bool = False,
    mask_dtype: str = "uint32",
    coherent_fraction: float = 0.6,
    with_bounding_polygon: bool = True,
    with_connected_components: bool = True,
    with_ionosphere: bool = False,
) -> Path:
    """Write a small GUNW-format HDF5 file and return its path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(7)
    phase = np.full((rows, cols), np.nan, dtype=np.float32)
    coherence = np.full((rows, cols), np.nan, dtype=np.float32)
    valid = np.zeros((rows, cols), dtype=bool)
    valid[:, :] = False
    # A valid rectangular block with a smooth phase ramp and a patch of water.
    r0, r1 = 2, rows - 3
    c0, c1 = 3, cols - 4
    rr, cc = np.mgrid[0:rows, 0:cols]
    phase[r0:r1, c0:c1] = (0.02 * rr + 0.05 * cc)[r0:r1, c0:c1].astype(np.float32)
    valid[r0:r1, c0:c1] = True
    coherence[valid] = 0.15 + 0.75 * rng.random(int(valid.sum()))
    water = np.zeros((rows, cols), dtype=bool)
    water[r0:r1, c0 : c0 + max(2, (c1 - c0) // 4)] = True
    if all_invalid:
        phase[:] = np.nan
        coherence[:] = np.nan
        valid[:] = False
    low_coherence = coherence < 0.4
    coherence[valid & low_coherence] = 0.1

    components = np.full((rows, cols), 65535, dtype=np.uint16)
    components[valid] = 1
    components[valid & (cc < c0 + (c1 - c0) // 2)] = 0

    unwrapped_x = x0 + posting * np.arange(cols)
    unwrapped_y = y0 - posting * np.arange(rows)
    wrapped_cols = cols * look_factor
    wrapped_rows = rows * look_factor
    wrapped_x = (x0 - posting / 2) + (posting / look_factor) * np.arange(wrapped_cols)
    wrapped_y = (y0 + posting / 2) - (posting / look_factor) * np.arange(wrapped_rows)
    if mismatched_unwrapped_coordinates:
        unwrapped_x = wrapped_x.copy()
        unwrapped_y = wrapped_y.copy()

    with h5py.File(path, "w") as h5:
        h5.attrs["Conventions"] = np.bytes_("CF-1.7")
        h5.attrs["title"] = np.bytes_("NISAR L2 GUNW Product")
        h5.attrs["institution"] = np.bytes_("NASA JPL")
        h5.attrs["mission_name"] = np.bytes_("NISAR")

        ident = h5.create_group("science/LSAR/identification")
        _scalar(ident, "granuleId", path.stem)
        _scalar(ident, "productType", product_type)
        _scalar(ident, "productVersion", "1.0.11")
        _scalar(ident, "productSpecificationVersion", "1.5.0")
        _scalar(ident, "referenceZeroDopplerStartTime", reference_date)
        _scalar(ident, "referenceZeroDopplerEndTime", reference_date)
        _scalar(ident, "secondaryZeroDopplerStartTime", secondary_date)
        _scalar(ident, "secondaryZeroDopplerEndTime", secondary_date)
        _scalar(ident, "trackNumber", np.uint32(162))
        _scalar(ident, "frameNumber", np.uint16(7))
        _scalar(ident, "orbitPassDirection", "Ascending")
        _scalar(ident, "lookDirection", "Left")
        _scalar(ident, "radarBand", "L")
        _scalar(ident, "processingDateTime", "2026-08-11T11:07:23")
        _scalar(ident, "processingType", "Nominal")
        _scalar(ident, "productDoi", "10.5067/TEST")
        _scalar(ident, "missionId", "NISAR")
        _scalar(ident, "instrumentName", "L-SAR")
        _scalar(ident, "platformName", "NISAR")
        _scalar(ident, "isGeocoded", "True")
        if with_bounding_polygon:
            left = float(unwrapped_x.min() - posting / 2)
            right = float(unwrapped_x.max() + posting / 2)
            bottom = float(unwrapped_y.min() - posting / 2)
            top = float(unwrapped_y.max() + posting / 2)
            _scalar(ident, "boundingPolygon", _wkt_footprint(epsg, left, bottom, right, top))

        grids = h5.create_group("science/LSAR/GUNW/grids/frequencyA")
        _scalar(grids, "centerFrequency", np.float64(1.239e9))
        grids.create_dataset("listOfPolarizations", data=np.array([b"HH"]))

        def add_coords(
            group: h5py.Group, xs: np.ndarray, ys: np.ndarray, *, attach_to: list[h5py.Dataset]
        ) -> None:
            if not with_sibling_coordinates:
                return
            x_ds = group.create_dataset("xCoordinates", data=xs)
            y_ds = group.create_dataset("yCoordinates", data=ys)
            for axis, ds_scale in ((1, x_ds), (0, y_ds)):
                ds_scale.make_scale("x" if axis == 1 else "y")
                ds_scale.attrs["units"] = "meters"
                ds_scale.attrs["standard_name"] = (
                    "projection_x_coordinate" if axis == 1 else "projection_y_coordinate"
                )
            for raster in attach_to:
                if with_dimension_scales:
                    raster.dims[1].attach_scale(x_ds)
                    raster.dims[0].attach_scale(y_ds)
            _scalar(group, "xCoordinateSpacing", np.float64(xs[1] - xs[0]))
            _scalar(group, "yCoordinateSpacing", np.float64(ys[1] - ys[0]))
            ds = group.create_dataset("projection", data=np.uint32(epsg))
            ds.attrs["epsg_code"] = epsg
            ds.attrs["grid_mapping_name"] = "transverse_mercator"
            return

        # ---- wrapped grid (fine posting) ----
        wrapped = grids.create_group("wrappedInterferogram/HH")
        wrapped_coherence = wrapped.create_dataset(
            "coherenceMagnitude", data=np.zeros((wrapped_rows, wrapped_cols), dtype=np.float32)
        )
        wrapped_coherence.attrs["_FillValue"] = np.nan
        wrapped_coherence.attrs["units"] = "1"
        add_coords(grids["wrappedInterferogram/HH"], wrapped_x, wrapped_y, attach_to=[wrapped_coherence])
        wmask = grids["wrappedInterferogram"].create_dataset(
            "mask", data=np.zeros((wrapped_rows, wrapped_cols), dtype=np.uint32)
        )
        wmask.attrs["_FillValue"] = 255

        # ---- unwrapped grid (coarse posting) ----
        unwrapped = grids.create_group("unwrappedInterferogram")
        pol = unwrapped.create_group("HH")
        phase_ds = pol.create_dataset("unwrappedPhase", data=phase)
        phase_ds.attrs["_FillValue"] = np.nan
        phase_ds.attrs["units"] = "radians"
        phase_ds.attrs["description"] = "Unwrapped interferogram between HH layers"
        coherence_ds = pol.create_dataset("coherenceMagnitude", data=coherence)
        coherence_ds.attrs["_FillValue"] = np.nan
        coherence_ds.attrs["units"] = "1"
        cc_ds = None
        if with_connected_components:
            cc_ds = pol.create_dataset("connectedComponents", data=components)
            cc_ds.attrs["_FillValue"] = np.uint16(65535)
        iono_ds = None
        if with_ionosphere:
            iono_ds = pol.create_dataset(
                "ionospherePhaseScreen", data=np.where(valid, 0.5, np.nan).astype(np.float32)
            )
            iono_ds.attrs["_FillValue"] = np.nan
            iono_ds.attrs["units"] = "radians"

        mask_values = np.zeros((rows, cols), dtype=np.uint32)
        mask_values[valid] = 11
        mask_values[valid & water] = 111
        mask_values[valid & (cc > c0 + 5)] = 0x0100000B  # bit 24: ionosphere-filled
        if mask_dtype == "uint8":
            raw_mask = mask_values.astype(np.uint8)
            raw_mask[valid & (cc > c0 + 5)] = 11  # uint8 cannot carry bit 24
        else:
            raw_mask = mask_values
        mask_ds = unwrapped.create_dataset("mask", data=raw_mask)
        mask_ds.attrs["_FillValue"] = 255
        mask_ds.attrs["description"] = (
            "Combination of a water mask and subswath mask. Bits 0-7 represent "
            "subswath encoding; bits 8-15 and 16-23 anomaly flags; bit 24 the "
            "ionospheric phase mask."
            if mask_dtype != "uint8"
            else "Combination of water mask and a mask of subswaths of valid samples."
        )

        rasters = [phase_ds, coherence_ds] + ([cc_ds] if cc_ds is not None else []) + ([iono_ds] if iono_ds is not None else [])
        # The mask uses the group-level coordinates.
        add_coords(unwrapped, unwrapped_x, unwrapped_y, attach_to=rasters)
        if with_sibling_coordinates and with_dimension_scales:
            # Mask dimension scales point at the group-level coordinates.
            x_ds = unwrapped["xCoordinates"]
            y_ds = unwrapped["yCoordinates"]
            mask_ds.dims[1].attach_scale(x_ds)
            mask_ds.dims[0].attach_scale(y_ds)
        # Polarization-level copies like the real product.
        if with_sibling_coordinates:
            pol.create_dataset("xCoordinateSpacing", data=np.float64(posting))
            pol.create_dataset("yCoordinateSpacing", data=np.float64(-posting))
            proj = pol.create_dataset("projection", data=np.uint32(epsg))
            proj.attrs["epsg_code"] = epsg
            if mismatched_unwrapped_coordinates:
                pol.create_dataset("xCoordinates", data=unwrapped_x)
                pol.create_dataset("yCoordinates", data=unwrapped_y)

        metadata = h5.create_group("science/LSAR/GUNW/metadata")
        orbit = metadata.create_group("orbit")
        orbit.create_dataset("temporalBaseline", data=np.uint16(11))
        params = metadata.create_group("processingInformation/parameters/unwrappedInterferogram/frequencyA")
        params.create_dataset("ellipsoidalFlatteningApplied", data=np.bytes_("True"))
        params.create_dataset("topographicFlatteningApplied", data=np.bytes_("True"))
        geocoding = metadata.create_group("processingInformation/parameters/geocoding")
        geocoding.create_dataset("rangeIonosphericCorrectionApplied", data=np.bytes_("True"))

    return path


def write_processed_metadata(
    observation_dir: Path,
    *,
    source_path: Path,
    observation_id: str = "fixture_observation",
    **overrides: Any,
) -> Path:
    """Create a minimal processed bundle for web-application tests."""
    from nisar_eim.pipeline import ProcessConfig, process_granule

    process_granule(
        source_path,
        observation_id=observation_id,
        output_root=observation_dir.parent,
        config=ProcessConfig(render_dpi=60, map_preview_width=200),
        force=True,
    )
    return observation_dir / "metadata.json"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
