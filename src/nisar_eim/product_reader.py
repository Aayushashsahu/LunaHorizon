"""Reader and product model for NISAR L2 GUNW HDF5 granules.

Design rules
------------
* The raw granule is opened read-only and is never modified.
* Metadata discovery does not read raster bodies; layer reads are explicit.
* Georeferencing is resolved **per dataset** from the raster's own HDF5
  dimension scales and its own grid group.  There is no global basename search,
  because a GUNW file legitimately contains several grids with their own
  coordinate vectors (20 m wrapped, 80 m unwrapped, geometry lookup tables).
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import h5py
import numpy as np

from .errors import (
    AmbiguousGeoreferencingError,
    GeoreferencingError,
    ProductFormatError,
)
from .geospatial import GridGeometry, build_geometry

IDENTIFICATION_ROOT = "science/LSAR/identification"
GUNW_ROOT = "science/LSAR/GUNW"
PRODUCT_TYPE = "GUNW"

#: Layer keys understood by the application, in display order.
LAYER_KEYS = (
    "phase",
    "coherence",
    "connected_components",
    "ionosphere",
    "ionosphere_uncertainty",
)

_LAYER_BASENAMES = {
    "phase": "unwrappedPhase",
    "coherence": "coherenceMagnitude",
    "connected_components": "connectedComponents",
    "ionosphere": "ionospherePhaseScreen",
    "ionosphere_uncertainty": "ionospherePhaseScreenUncertainty",
}


def decode_scalar(value: object) -> Any:
    """Convert an HDF5 scalar or small array into plain Python values."""
    if isinstance(value, (bytes, np.bytes_)):
        return value.decode("utf-8", errors="replace").strip("\x00 ")
    if isinstance(value, np.ndarray):
        if value.shape == ():
            return decode_scalar(value.item())
        if value.dtype.kind in "SUO":
            return [decode_scalar(item) for item in value]
        return np.asarray(value).tolist()
    if isinstance(value, np.generic):
        return decode_scalar(value.item())
    if isinstance(value, float) and not np.isfinite(value):
        return None if np.isnan(value) else str(value)
    return value


def dataset_attributes(ds: h5py.Dataset, *, skip_references: bool = True) -> dict[str, Any]:
    """Return readable dataset attributes, optionally dropping HDF5 references."""
    attrs: dict[str, Any] = {}
    for key, value in ds.attrs.items():
        if skip_references and key in {"DIMENSION_LIST", "REFERENCE_LIST", "CLASS"}:
            continue
        attrs[str(key)] = decode_scalar(value)
    return attrs


@dataclass(frozen=True)
class LayerSpec:
    """One raster layer of the unwrapped-interferogram grid."""

    key: str
    path: str
    shape: tuple[int, int]
    dtype: str
    units: str
    description: str
    fill_value: Any
    attrs: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "dataset_path": self.path,
            "shape_rows_cols": [int(self.shape[0]), int(self.shape[1])],
            "dtype": self.dtype,
            "units": self.units,
            "description": self.description,
            "fill_value": self.fill_value,
            "attributes": self.attrs,
        }


@dataclass(frozen=True)
class GridResolution:
    """How a raster's coordinate vectors were located and validated."""

    x_path: str
    y_path: str
    projection_path: str
    epsg: int
    method: str
    x_coords: np.ndarray
    y_coords: np.ndarray
    spacing_hints: tuple[float | None, float | None]
    projection_attrs: dict[str, Any]
    candidates_considered: list[dict[str, Any]] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "xCoordinates": self.x_path,
            "yCoordinates": self.y_path,
            "projection": self.projection_path,
            "epsg": self.epsg,
            "spacing_hints": {
                "x": self.spacing_hints[0],
                "y": self.spacing_hints[1],
            },
            "projection_attributes": self.projection_attrs,
            "candidates_considered": self.candidates_considered,
        }


def _dimension_scale_paths(h5: h5py.File, ds: h5py.Dataset) -> dict[str, str]:
    """Resolve the CF-1.7 dimension-scale coordinate datasets of a raster."""
    refs = ds.attrs.get("DIMENSION_LIST")
    resolved: dict[str, str] = {}
    if refs is None:
        return resolved
    target = {0: "y", 1: "x"}
    try:
        for axis, axis_refs in enumerate(refs):
            if axis not in target:
                continue
            names: list[str] = []
            for ref in np.asarray(axis_refs, dtype=object).ravel():
                obj = h5[ref]
                if isinstance(obj, h5py.Dataset):
                    names.append(obj.name)
            if len(names) == 1:
                resolved[target[axis]] = names[0]
    except Exception:  # pragma: no cover - malformed attributes on exotic files
        return {}
    return resolved


def _parent_dirs(path: str, levels: int = 3) -> list[str]:
    """Return ancestor groups of a dataset path, nearest first."""
    parts = path.rsplit("/", 1)[0]
    out: list[str] = []
    for _ in range(levels):
        if not parts:
            break
        out.append(parts)
        parts = parts.rsplit("/", 1)[0] if "/" in parts else ""
    return out


def _read_axis(h5: h5py.File, path: str) -> np.ndarray:
    ds = h5[path]
    if ds.ndim != 1:
        raise GeoreferencingError(
            f"Coordinate dataset {path} is not one-dimensional.",
            details={"path": path, "shape": list(ds.shape)},
        )
    return np.asarray(ds[()], dtype=np.float64)


def _spacing_hint(h5: h5py.File, group: str, name: str) -> float | None:
    path = f"{group}/{name}"
    if path not in h5:
        return None
    try:
        value = float(np.asarray(h5[path][()]))
    except Exception:  # pragma: no cover - defensive
        return None
    return value if np.isfinite(value) else None


def _projection_candidates(h5: h5py.File, x_path: str, grid_root: str) -> list[str]:
    candidates: list[str] = []
    for directory in _parent_dirs(x_path, levels=4):
        path = f"{directory}/projection"
        if path in h5:
            candidates.append(path)
        if directory == grid_root:
            break
    return candidates


def _coordinate_pairs(h5: h5py.File, dataset_path: str) -> list[tuple[str, str, str]]:
    """Candidate ``(x_path, y_path, source)`` pairs for a raster, nearest first."""
    pairs: list[tuple[str, str, str]] = []
    scales = _dimension_scale_paths(h5, h5[dataset_path])
    if "x" in scales and "y" in scales:
        pairs.append((scales["x"], scales["y"], "hdf5_dimension_scale"))

    for directory in _parent_dirs(dataset_path, levels=3):
        x_path = f"{directory}/xCoordinates"
        y_path = f"{directory}/yCoordinates"
        if x_path in h5 and y_path in h5:
            pairs.append((x_path, y_path, f"sibling_group:{directory}"))
    # De-duplicate while preserving precedence.
    seen: set[tuple[str, str]] = set()
    unique: list[tuple[str, str, str]] = []
    for x_path, y_path, source in pairs:
        if (x_path, y_path) in seen:
            continue
        seen.add((x_path, y_path))
        unique.append((x_path, y_path, source))
    return unique


def _all_grid_coordinates(h5: h5py.File, grid_root: str) -> list[dict[str, Any]]:
    """Describe every coordinate pair inside a grid root (diagnostics only)."""
    found: list[dict[str, Any]] = []
    if grid_root not in h5:
        return found
    for name in sorted(h5[grid_root].keys()):
        group = h5[f"{grid_root}/{name}"]
        if not isinstance(group, h5py.Group):
            continue
        for sub in _iter_groups_with_coords(group):
            x_path = f"{sub}/xCoordinates"
            y_path = f"{sub}/yCoordinates"
            if x_path in h5 and y_path in h5:
                found.append(
                    {
                        "group": sub,
                        "x_length": int(h5[x_path].shape[0]) if h5[x_path].ndim else None,
                        "y_length": int(h5[y_path].shape[0]) if h5[y_path].ndim else None,
                    }
                )
    return found


def _iter_groups_with_coords(group: h5py.Group) -> Iterator[str]:
    """Yield groups under ``group`` that contain xCoordinates and yCoordinates."""
    if "xCoordinates" in group and "yCoordinates" in group:
        yield group.name
    for child in group.values():
        if isinstance(child, h5py.Group):
            yield from _iter_groups_with_coords(child)


def resolve_grid(h5: h5py.File, dataset_path: str, grid_root: str) -> GridResolution:
    """Resolve and validate the coordinate vectors that belong to a raster.

    Only grids attached to the raster (dimension scales, sibling group, parent
    groups) are considered.  A candidate is accepted if its lengths match the
    raster shape; a candidate whose lengths differ is recorded in the
    diagnostic trail but never used.
    """
    if dataset_path not in h5:
        raise ProductFormatError(
            "Raster dataset is missing from the product.",
            details={"dataset_path": dataset_path},
        )
    ds = h5[dataset_path]
    if ds.ndim != 2:
        raise ProductFormatError(
            "Expected a two-dimensional raster dataset.",
            details={"dataset_path": dataset_path, "shape": list(ds.shape)},
        )
    rows, cols = int(ds.shape[0]), int(ds.shape[1])
    pairs = _coordinate_pairs(h5, dataset_path)

    considered: list[dict[str, Any]] = []
    matches: list[tuple[str, str, str, np.ndarray, np.ndarray]] = []
    for x_path, y_path, source in pairs:
        x = _read_axis(h5, x_path)
        y = _read_axis(h5, y_path)
        candidate = {
            "x_path": x_path,
            "y_path": y_path,
            "source": source,
            "x_length": int(x.size),
            "y_length": int(y.size),
            "matches_raster_shape": bool(x.size == cols and y.size == rows),
        }
        considered.append(candidate)
        if candidate["matches_raster_shape"]:
            matches.append((x_path, y_path, source, x, y))

    if not matches:
        grids = _all_grid_coordinates(h5, grid_root)
        ratio_x = _ratio_text(cols, considered[0]["x_length"]) if considered else "unavailable"
        ratio_y = _ratio_text(rows, considered[0]["y_length"]) if considered else "unavailable"
        raise GeoreferencingError(
            "Unable to georeference this raster: no coordinate vectors attached to "
            "the dataset match its shape.",
            details={
                "dataset_path": dataset_path,
                "raster_shape_rows_cols": [rows, cols],
                "candidate_coordinates": considered,
                "all_coordinate_grids_under": grid_root,
                "grid_inventory": grids,
                "coordinate_ratio_x": ratio_x,
                "coordinate_ratio_y": ratio_y,
                "hint": (
                    "GUNW stores independent coordinate vectors per map grid "
                    "(20 m wrapped vs 80 m unwrapped). Coordinates must come from "
                    "the raster's own grid, not from a same-named dataset elsewhere "
                    "in the file."
                ),
            },
        )

    # If several distinct matching grids exist, they must agree.
    reference = matches[0]
    for other in matches[1:]:
        if not (np.array_equal(reference[3], other[3]) and np.array_equal(reference[4], other[4])):
            raise AmbiguousGeoreferencingError(
                "Several coordinate grids match the raster shape but disagree.",
                details={
                    "candidates": [
                        {"x_path": m[0], "y_path": m[1], "source": m[2]} for m in matches
                    ]
                },
            )

    x_path, y_path, source, x, y = reference
    projection_paths = _projection_candidates(h5, x_path, grid_root)
    if not projection_paths:
        raise GeoreferencingError(
            "No projection dataset is available for this grid.",
            details={
                "x_coordinates": x_path,
                "y_coordinates": y_path,
                "grid_root": grid_root,
                "hint": "The product must provide a projection dataset with an epsg_code attribute.",
            },
        )
    projection_path = projection_paths[0]
    projection_attrs = dataset_attributes(h5[projection_path])
    epsg = projection_attrs.get("epsg_code")
    if epsg is None:
        raise GeoreferencingError(
            "The projection dataset does not declare an EPSG code.",
            details={"projection": projection_path, "attributes": projection_attrs},
        )

    spacing_hints = (
        _spacing_hint(h5, x_path.rsplit("/", 1)[0], "xCoordinateSpacing"),
        _spacing_hint(h5, y_path.rsplit("/", 1)[0], "yCoordinateSpacing"),
    )
    return GridResolution(
        x_path=x_path,
        y_path=y_path,
        projection_path=projection_path,
        epsg=int(epsg),
        method=source,
        x_coords=x,
        y_coords=y,
        spacing_hints=spacing_hints,
        projection_attrs=projection_attrs,
        candidates_considered=considered,
    )


def _ratio_text(raster: int, coords: int) -> str:
    if not raster or not coords:
        return "unavailable"
    ratio = coords / raster
    if abs(ratio - round(ratio)) < 1e-9 and round(ratio) != 1:
        return f"{round(ratio)}x"
    return f"{ratio:.4f}x"


@dataclass(frozen=True)
class GunwProduct:
    """Metadata view of a NISAR L2 GUNW granule (no raster bodies held)."""

    path: Path
    file_size: int
    granule_id: str
    product_type: str
    product_version: str | None
    product_specification_version: str | None
    identification: dict[str, Any]
    frequency: str
    polarization: str
    grid_root: str
    unwrapped_group: str
    layers: dict[str, LayerSpec]
    mask_path: str | None
    geometry: GridGeometry
    grid_resolution: GridResolution
    bounding_polygon_wkt: str | None
    reference_start: str | None
    secondary_start: str | None
    reference_end: str | None
    secondary_end: str | None
    center_frequency_hz: float | None
    temporal_baseline_days: Any
    processing_parameters: dict[str, Any]
    file_attributes: dict[str, Any]

    # -- convenience -------------------------------------------------------
    @property
    def wavelength_m(self) -> float | None:
        """Radar wavelength implied by the product's centre frequency (c / f)."""
        if not self.center_frequency_hz:
            return None
        return 299_792_458.0 / float(self.center_frequency_hz)

    @property
    def phase(self) -> LayerSpec | None:
        return self.layers.get("phase")

    @property
    def coherence(self) -> LayerSpec | None:
        return self.layers.get("coherence")

    def dataset_path(self, key: str) -> str:
        spec = self.layers.get(key)
        if spec is None:
            raise ProductFormatError(
                f"Layer '{key}' is not present in this product.",
                details={"available_layers": sorted(self.layers)},
            )
        return spec.path

    def read(self, key: str, row_slice: slice = slice(None), col_slice: slice = slice(None)) -> np.ndarray:
        """Read a rectangular window of a named layer, read-only."""
        path = self.dataset_path(key)
        with h5py.File(self.path, "r") as h5:
            return np.asarray(h5[path][row_slice, col_slice])

    def read_window(self, key: str, row: int, col: int, half: int = 2) -> np.ndarray:
        """Read a small square window centred on a pixel, clipped to the raster."""
        r0 = max(0, int(row) - half)
        r1 = min(self.geometry.height, int(row) + half + 1)
        c0 = max(0, int(col) - half)
        c1 = min(self.geometry.width, int(col) + half + 1)
        return self.read(key, slice(r0, r1), slice(c0, c1))

    def read_mask(self) -> np.ndarray | None:
        if not self.mask_path:
            return None
        with h5py.File(self.path, "r") as h5:
            return np.asarray(h5[self.mask_path][()])

    def to_json(self) -> dict[str, Any]:
        return {
            "source_path": str(self.path),
            "file_size_bytes": self.file_size,
            "granule_id": self.granule_id,
            "product_type": self.product_type,
            "product_version": self.product_version,
            "product_specification_version": self.product_specification_version,
            "frequency": self.frequency,
            "polarization": self.polarization,
            "grid_root": self.grid_root,
            "unwrapped_group": self.unwrapped_group,
            "layers": {key: spec.to_json() for key, spec in self.layers.items()},
            "mask_path": self.mask_path,
            "reference_start": self.reference_start,
            "secondary_start": self.secondary_start,
            "reference_end": self.reference_end,
            "secondary_end": self.secondary_end,
            "center_frequency_hz": self.center_frequency_hz,
            "wavelength_m": self.wavelength_m,
            "temporal_baseline_days": self.temporal_baseline_days,
            "georeferencing": self.grid_resolution.to_json(),
            "geometry": self.geometry.to_json(),
            "bounding_polygon_wkt": self.bounding_polygon_wkt,
            "processing_parameters": self.processing_parameters,
            "identification": self.identification,
            "file_attributes": self.file_attributes,
        }


def _identification(h5: h5py.File) -> dict[str, Any]:
    if IDENTIFICATION_ROOT not in h5:
        raise ProductFormatError(
            "The file has no NISAR identification group; it is not a supported "
            "NISAR product.",
            details={"expected_group": IDENTIFICATION_ROOT},
        )
    group = h5[IDENTIFICATION_ROOT]
    out: dict[str, Any] = {}
    for name, obj in group.items():
        if isinstance(obj, h5py.Dataset) and obj.shape == () or isinstance(obj, h5py.Dataset):
            out[name] = decode_scalar(obj[()])
    return out


def _layer_spec(h5: h5py.File, key: str, path: str) -> LayerSpec:
    ds = h5[path]
    if ds.ndim != 2:
        raise ProductFormatError(
            f"Layer '{key}' is not a two-dimensional raster.",
            details={"dataset_path": path, "shape": list(ds.shape)},
        )
    attrs = dataset_attributes(ds)
    units = str(attrs.get("units", "")) or "unknown"
    description = str(attrs.get("description", "")) or key
    return LayerSpec(
        key=key,
        path=path,
        shape=(int(ds.shape[0]), int(ds.shape[1])),
        dtype=str(ds.dtype),
        units=units,
        description=description,
        fill_value=attrs.get("_FillValue"),
        attrs=attrs,
    )


def _processing_parameters(h5: h5py.File) -> dict[str, Any]:
    path = f"{GUNW_ROOT}/metadata/processingInformation/parameters"
    if path not in h5:
        return {}
    out: dict[str, Any] = {}

    def walk(group: h5py.Group, prefix: str) -> None:
        for name, obj in group.items():
            key = f"{prefix}/{name}" if prefix else name
            if isinstance(obj, h5py.Group):
                walk(obj, key)
            elif obj.shape == () and obj.size:
                value = decode_scalar(obj[()])
                if isinstance(value, (str, int, float, bool)) or value is None:
                    out[key] = value

    walk(h5[path], "")
    # Keep the report readable: the run configuration file is large and noisy.
    out.pop("runConfigurationContents", None)
    return out


def open_product(path: str | Path, *, frequency: str | None = None, polarization: str | None = None) -> GunwProduct:
    """Open a NISAR L2 GUNW granule and validate its structure and georeferencing."""
    file_path = Path(path)
    if not file_path.exists():
        raise ProductFormatError(
            "Input granule does not exist.",
            details={"path": str(file_path)},
        )
    if not file_path.is_file():
        raise ProductFormatError("Input path is not a file.", details={"path": str(file_path)})

    try:
        h5 = h5py.File(file_path, "r")
    except OSError as exc:
        raise ProductFormatError(
            "The file could not be opened as HDF5.",
            details={"path": str(file_path), "h5py_error": str(exc)},
        ) from exc

    try:
        identification = _identification(h5)
        product_type = str(identification.get("productType", ""))
        if product_type and product_type != PRODUCT_TYPE:
            raise ProductFormatError(
                f"Unsupported NISAR product type '{product_type}'. This application "
                "supports the L2 Geocoded Unwrapped Interferogram (GUNW) product only.",
                details={"product_type": product_type, "supported": [PRODUCT_TYPE]},
            )
        if f"{GUNW_ROOT}/grids" not in h5:
            raise ProductFormatError(
                "The file has no GUNW grids group.",
                details={"expected_group": f"{GUNW_ROOT}/grids"},
            )

        available_frequencies = [
            name[len("frequency"):]
            for name in h5[f"{GUNW_ROOT}/grids"]
            if name.startswith("frequency")
        ]
        chosen_frequency = frequency or (available_frequencies[0] if available_frequencies else None)
        if chosen_frequency is None:
            raise ProductFormatError(
                "No frequency grid found in the product.",
                details={"grids_group": f"{GUNW_ROOT}/grids"},
            )
        grid_root = f"{GUNW_ROOT}/grids/frequency{chosen_frequency}"
        if grid_root not in h5:
            raise ProductFormatError(
                f"Frequency '{chosen_frequency}' is not present in this product.",
                details={"available": available_frequencies},
            )

        declared_pols: list[str] = []
        pol_path = f"{grid_root}/listOfPolarizations"
        if pol_path in h5:
            declared_pols = [str(p) for p in decode_scalar(h5[pol_path][()])]
        unwrapped_group = f"{grid_root}/unwrappedInterferogram"
        if unwrapped_group not in h5:
            raise ProductFormatError(
                "The product has no unwrappedInterferogram grid.",
                details={"expected_group": unwrapped_group},
            )
        available_pols = [
            name
            for name in h5[unwrapped_group]
            if isinstance(h5[f"{unwrapped_group}/{name}"], h5py.Group)
        ]
        chosen_pol = polarization or (declared_pols[0] if declared_pols else None)
        if chosen_pol is None or chosen_pol not in available_pols:
            if not available_pols:
                raise ProductFormatError(
                    "No polarization subgroup exists in the unwrapped interferogram grid.",
                    details={"group": unwrapped_group},
                )
            chosen_pol = available_pols[0]

        pol_group = f"{unwrapped_group}/{chosen_pol}"
        layers: dict[str, LayerSpec] = {}
        for key in LAYER_KEYS:
            candidate = f"{pol_group}/{_LAYER_BASENAMES[key]}"
            if candidate in h5:
                layers[key] = _layer_spec(h5, key, candidate)

        if "phase" not in layers:
            raise ProductFormatError(
                "The unwrapped phase dataset is missing; this granule cannot be "
                "interpreted as an unwrapped interferogram.",
                details={
                    "expected": f"{pol_group}/unwrappedPhase",
                    "available_in_group": sorted(h5[pol_group].keys()),
                },
            )
        if "coherence" not in layers:
            raise ProductFormatError(
                "The coherence magnitude dataset is missing.",
                details={
                    "expected": f"{pol_group}/coherenceMagnitude",
                    "available_in_group": sorted(h5[pol_group].keys()),
                },
            )

        base_shape = layers["phase"].shape
        for key, spec in layers.items():
            if spec.shape != base_shape:
                raise ProductFormatError(
                    f"Layer '{key}' has a different shape than the unwrapped phase.",
                    details={
                        "phase_shape": list(base_shape),
                        "layer_shape": list(spec.shape),
                        "dataset_path": spec.path,
                    },
                )

        mask_path = None
        for candidate in (f"{unwrapped_group}/mask", f"{pol_group}/mask"):
            if candidate in h5:
                mask_path = candidate
                break
        if mask_path:
            mask_shape = tuple(int(v) for v in h5[mask_path].shape)
            if mask_shape != base_shape:
                raise ProductFormatError(
                    "The product mask shape does not match the unwrapped phase raster.",
                    details={
                        "mask_path": mask_path,
                        "mask_shape": list(mask_shape),
                        "phase_shape": list(base_shape),
                    },
                )

        resolution = resolve_grid(h5, layers["phase"].path, grid_root)
        geometry = build_geometry(
            resolution.x_coords,
            resolution.y_coords,
            resolution.epsg,
            base_shape,
            spacing_hints=resolution.spacing_hints,
            method=f"phase raster + {resolution.method}",
            source_paths={
                "xCoordinates": resolution.x_path,
                "yCoordinates": resolution.y_path,
                "projection": resolution.projection_path,
            },
        )

        polygon = None
        polygon_path = f"{IDENTIFICATION_ROOT}/boundingPolygon"
        if polygon_path in h5:
            raw = h5[polygon_path][()]
            polygon = decode_scalar(raw)
            if isinstance(polygon, list):
                polygon = "".join(str(part) for part in polygon)

        center_frequency = None
        cf_path = f"{grid_root}/centerFrequency"
        if cf_path in h5:
            center_frequency = float(np.asarray(h5[cf_path][()]))

        temporal_baseline = None
        tb_path = f"{GUNW_ROOT}/metadata/orbit/temporalBaseline"
        if tb_path in h5:
            temporal_baseline = decode_scalar(h5[tb_path][()])

        file_attrs = {str(k): decode_scalar(v) for k, v in h5.attrs.items()}

        product = GunwProduct(
            path=file_path,
            file_size=file_path.stat().st_size,
            granule_id=str(identification.get("granuleId") or file_path.stem),
            product_type=product_type or PRODUCT_TYPE,
            product_version=_optional_str(identification.get("productVersion")),
            product_specification_version=_optional_str(
                identification.get("productSpecificationVersion")
            ),
            identification=identification,
            frequency=chosen_frequency,
            polarization=chosen_pol,
            grid_root=grid_root,
            unwrapped_group=unwrapped_group,
            layers=layers,
            mask_path=mask_path,
            geometry=geometry,
            grid_resolution=resolution,
            bounding_polygon_wkt=polygon,
            reference_start=_optional_str(identification.get("referenceZeroDopplerStartTime")),
            secondary_start=_optional_str(identification.get("secondaryZeroDopplerStartTime")),
            reference_end=_optional_str(identification.get("referenceZeroDopplerEndTime")),
            secondary_end=_optional_str(identification.get("secondaryZeroDopplerEndTime")),
            center_frequency_hz=center_frequency,
            temporal_baseline_days=temporal_baseline,
            processing_parameters=_processing_parameters(h5),
            file_attributes=file_attrs,
        )
        return product
    finally:
        h5.close()


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text or None


def iter_row_chunks(dataset: h5py.Dataset, rows_per_chunk: int = 512) -> Iterable[slice]:
    """Yield row slices for memory-bounded full-raster iteration."""
    rows = int(dataset.shape[0])
    for start in range(0, rows, max(1, rows_per_chunk)):
        yield slice(start, min(rows, start + rows_per_chunk))


def structure_summary(h5: h5py.File, max_datasets: int = 4000) -> dict[str, Any]:
    """Metadata-only structural inventory of an HDF5 file (no raster bodies)."""
    datasets: list[dict[str, Any]] = []
    groups: list[str] = []

    def visitor(name: str, obj: h5py.Dataset | h5py.Group) -> None:
        if len(datasets) >= max_datasets:
            return
        if isinstance(obj, h5py.Dataset):
            datasets.append(
                {
                    "path": name,
                    "shape": list(obj.shape),
                    "dtype": str(obj.dtype),
                    "chunks": list(obj.chunks) if obj.chunks else None,
                    "compression": obj.compression,
                    "attributes": dataset_attributes(obj, skip_references=True),
                }
            )
        else:
            groups.append(name)

    h5.visititems(visitor)
    return {
        "file_attributes": {str(k): decode_scalar(v) for k, v in h5.attrs.items()},
        "groups": groups,
        "datasets": datasets,
        "truncated": len(datasets) >= max_datasets,
    }
