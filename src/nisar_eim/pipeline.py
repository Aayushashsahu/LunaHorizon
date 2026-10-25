"""Processing, validation and inspection pipeline for NISAR GUNW granules.

Separation of concerns
----------------------
* :mod:`nisar_eim.product_reader` - HDF5 structure, identification, grid resolution
* :mod:`nisar_eim.geospatial`     - affine georeferencing and footprints
* :mod:`nisar_eim.quality`        - mask decoding, coherence and component filters
* :mod:`nisar_eim.statistics`     - summaries and threshold tables
* :mod:`nisar_eim.rendering`      - PNG and GeoTIFF output
* :mod:`nisar_eim.reporting`      - metadata JSON and the human report
* this module                     - orchestration, caching, checks
"""

from __future__ import annotations

import json
import sys
import time
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import h5py
import numpy as np
from shapely import wkt as shapely_wkt
from shapely.geometry import Point

from . import __version__
from .errors import EmptyDataError, ProductFormatError
from .event import assess_events, load_reference_events
from .product_reader import (
    GunwProduct,
    iter_row_chunks,
    open_product,
    structure_summary,
)
from .quality import (
    coherence_range_report,
    connectivity_summary,
    decode_mask,
    largest_component_label,
)
from .rendering import (
    RenderingError,
    build_geo_preview,
    colormap_stops,
    render_quicklook,
    resolve_style,
    save_map_image,
    validate_geotiff,
    write_coherence_preview,
    write_geotiff,
)
from .reporting import (
    PIPELINE_NAME,
    PIPELINE_VERSION,
    SCHEMA_VERSION,
    build_validation_states,
    compute_fingerprint,
    file_sha256,
    json_safe,
    software_versions,
    utc_now,
    write_json,
    write_report,
)

DEFAULT_OUTPUT_ROOT = Path("data/processed")
PRE_LAUNCH_DATE = "2025-07-30"  # NISAR launch; earlier dates are sample products

LIMITATIONS = [
    (
        "Unwrapped phase is reported in radians, the unit declared by the product. "
        "No phase-to-displacement conversion is applied: the GUNW product does not "
        "document a sign convention that this project could verify, and metric "
        "displacement requires assumptions that are not validated here."
    ),
    (
        "The product includes an ionospheric phase screen and geocoded tropospheric "
        "and solid-Earth-tide correction layers but does not apply them to the "
        "interferometric phase. Long-wavelength phase patterns therefore mix "
        "atmospheric and orbital effects with any surface signal."
    ),
    (
        "Coherence magnitude is a similarity/quality indicator. A coherence threshold "
        "is an exploratory filter chosen in the interface; no product-defined "
        "universal threshold exists."
    ),
    (
        "Pixels in different connected components can carry different integer phase "
        "ambiguities, so phase is not necessarily continuous across component "
        "boundaries."
    ),
    (
        "Geolocation is validated only for internal consistency (coordinate vectors, "
        "affine transform, EPSG code, footprint). Absolute product geolocation accuracy "
        "is not independently assessed."
    ),
    (
        "Geographic overlap with the 24 June 2026 Venezuela earthquake sequence does "
        "not establish that earthquake-induced deformation was measured. Any such "
        "statement would require a verified phase-to-displacement conversion, "
        "corrections and independent validation."
    ),
]


@dataclass(frozen=True)
class ProcessConfig:
    """User-facing processing configuration (recorded in the metadata)."""

    default_coherence_threshold: float = 0.40
    threshold_steps: tuple[float, ...] = (0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8)
    map_preview_width: int = 1600
    render_dpi: int = 150

    def to_json(self) -> dict[str, Any]:
        data = asdict(self)
        data["threshold_steps"] = list(self.threshold_steps)
        return data


def default_observation_id(product: GunwProduct) -> str:
    """Stable, metadata-derived observation identifier."""
    dates = []
    for value in (product.reference_start, product.secondary_start):
        if value and len(value) >= 10:
            dates.append(value[:10].replace("-", ""))
    suffix = "_".join(dates) if dates else "undated"
    return (
        f"nisar_gunw_t{product.identification.get('trackNumber', 'x')}"
        f"_f{product.identification.get('frameNumber', 'x')}_{suffix}"
    ).lower()


#: ASCII fallbacks for the typographic characters used in progress messages.
#: Windows PowerShell 5.1 captures stdout as cp1252, where printing "→" raises
#: UnicodeEncodeError; the report and PNG files stay UTF-8, only the console is
#: transliterated.
_CONSOLE_FALLBACK = {
    "\u2014": "-",
    "\u2013": "-",
    "\u2192": "->",
    "\u00d7": "x",
    "\u00b7": "-",
    "\u00b0": " deg",
    "\u2265": ">=",
    "\u2026": "...",
}


def _console_safe(message: str) -> str:
    """Return ``message`` if stdout can encode it, else an ASCII transliteration."""
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    try:
        message.encode(encoding)
        return message
    except (UnicodeEncodeError, LookupError):
        return "".join(
            char if ord(char) < 128 else _CONSOLE_FALLBACK.get(char, "?")
            for char in message
        )


def _print_step(message: str, start: float | None = None) -> None:
    prefix = "[nisar-eim]"
    if start is None:
        print(_console_safe(f"{prefix} {message}"), flush=True)
    else:
        print(
            _console_safe(f"{prefix} {message} ({time.perf_counter() - start:.1f}s)"),
            flush=True,
        )


# ---------------------------------------------------------------------------
# Layer loading
# ---------------------------------------------------------------------------
@dataclass
class LoadedLayers:
    phase: np.ndarray
    coherence: np.ndarray
    components: np.ndarray | None
    mask_valid: np.ndarray | None
    water: np.ndarray | None
    ionosphere_filled: np.ndarray | None
    mask_counts: dict[str, Any]
    valid: np.ndarray = field(init=False)

    def __post_init__(self) -> None:
        valid = np.isfinite(self.phase)
        if self.mask_valid is not None:
            valid &= self.mask_valid
        self.valid = valid


def load_layers(product: GunwProduct) -> LoadedLayers:
    """Read the unwrapped-interferogram layers with bounded extra copies."""
    _print_step(f"reading {product.phase.path}")
    phase = product.read("phase").astype(np.float32, copy=False)
    _print_step(f"reading {product.coherence.path}")
    coherence = product.read("coherence").astype(np.float32, copy=False)

    components = None
    if "connected_components" in product.layers:
        components = product.read("connected_components")
        if components.shape != phase.shape:
            raise ProductFormatError(
                "Connected components shape does not match the phase raster.",
                details={"components": list(components.shape), "phase": list(phase.shape)},
            )

    mask_valid = None
    water = None
    ionosphere_filled = None
    mask_counts: dict[str, Any] = {}
    if product.mask_path:
        _print_step(f"decoding mask {product.mask_path}")
        with h5py.File(product.path, "r") as h5:
            ds = h5[product.mask_path]
            fill = ds.attrs.get("_FillValue", 255)
            description = str(ds.attrs.get("description", ""))
            mask_valid = np.zeros(phase.shape, dtype=bool)
            water = np.zeros(phase.shape, dtype=bool)
            ionosphere_filled = np.zeros(phase.shape, dtype=bool)
            totals = {
                "total_pixels": int(phase.size),
                "valid_pixels": 0,
                "water_pixels": 0,
                "ionosphere_filled_pixels": 0,
                "reference_anomaly_pixels": 0,
                "secondary_anomaly_pixels": 0,
                "fill_pixels": 0,
            }
            encoding = None
            for rows in iter_row_chunks(ds, rows_per_chunk=512):
                fields = decode_mask(
                    np.asarray(ds[rows, :]),
                    fill_value=fill,
                    description=description,
                )
                encoding = fields.encoding
                mask_valid[rows, :] = fields.valid
                water[rows, :] = fields.water
                ionosphere_filled[rows, :] = fields.ionosphere_filled
                totals["valid_pixels"] += int(fields.valid.sum())
                totals["water_pixels"] += int(fields.water.sum())
                totals["ionosphere_filled_pixels"] += int(fields.ionosphere_filled.sum())
                totals["reference_anomaly_pixels"] += int((fields.reference_anomaly > 0).sum())
                totals["secondary_anomaly_pixels"] += int((fields.secondary_anomaly > 0).sum())
                totals["fill_pixels"] += int(fields.fill.sum())
            totals["encoding"] = encoding or "unknown"
            totals["invalid_pixels"] = totals["total_pixels"] - totals["valid_pixels"]
            totals["water_fraction_of_valid"] = (
                totals["water_pixels"] / totals["valid_pixels"]
                if totals["valid_pixels"]
                else None
            )
            mask_counts = totals

    has_any = bool(np.isfinite(phase).any())
    if not has_any:
        raise EmptyDataError(
            "The unwrapped phase raster contains no finite values.",
            details={"dataset": product.phase.path, "shape": list(phase.shape)},
        )
    return LoadedLayers(
        phase=phase,
        coherence=coherence,
        components=components,
        mask_valid=mask_valid,
        water=water,
        ionosphere_filled=ionosphere_filled,
        mask_counts=mask_counts,
    )


# ---------------------------------------------------------------------------
# Process
# ---------------------------------------------------------------------------
def process_granule(
    granule: str | Path,
    *,
    observation_id: str | None = None,
    output_root: str | Path = DEFAULT_OUTPUT_ROOT,
    config: ProcessConfig | None = None,
    force: bool = False,
    frequency: str | None = None,
    polarization: str | None = None,
    progress: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Produce all deliverables for one granule and return its metadata."""
    cfg = config or ProcessConfig()
    emit = progress or (lambda message: _print_step(message))
    started = time.perf_counter()
    path = Path(granule)
    emit(f"opening {path.name}")
    product = open_product(path, frequency=frequency, polarization=polarization)
    obs_id = observation_id or default_observation_id(product)

    source_stat = path.stat()
    fingerprint = compute_fingerprint(
        source_path=path,
        source_size=source_stat.st_size,
        source_mtime_ns=source_stat.st_mtime_ns,
        layers={key: spec.to_json() for key, spec in product.layers.items()},
        config=cfg.to_json(),
    )
    out_dir = Path(output_root) / obs_id
    metadata_path = out_dir / "metadata.json"
    if not force and metadata_path.exists():
        existing = _read_metadata(metadata_path)
        if existing and existing.get("fingerprint") == fingerprint and _outputs_present(
            existing, out_dir
        ):
            emit(f"{obs_id}: outputs are current for this granule and configuration — skipping")
            return existing
        emit(f"{obs_id}: cached outputs are stale or incomplete — reprocessing")

    out_dir.mkdir(parents=True, exist_ok=True)
    emit(f"observation id: {obs_id}")

    emit(f"resolving grid and reading layers ({product.geometry.width}×{product.geometry.height})")
    layers = load_layers(product)

    emit("computing statistics")
    mask_valid = layers.mask_valid
    phase_stats = _phase_statistics(layers, mask_valid)
    coherence_stats = _coherence_statistics(layers, mask_valid)
    components_info = (
        connectivity_summary(layers.components, layers.valid)
        if layers.components is not None
        else None
    )
    threshold_table = _threshold_table(layers, cfg)
    coherence_report = coherence_range_report(layers.coherence)

    # Display styles and images -------------------------------------------------
    emit("rendering phase and coherence quicklooks")
    phase_style = resolve_style(
        "phase", layers.phase, layers.valid, units=product.phase.units
    )
    coherence_style = resolve_style(
        "coherence", layers.coherence, layers.valid, units=product.coherence.units
    )
    subtitle = (
        f"{human_time(product.reference_start)} → {human_time(product.secondary_start)} · "
        f"{product.polarization} · "
        f"{product.identification.get('orbitPassDirection', 'pass unknown')} pass"
    )
    phase_png = out_dir / "phase.png"
    coherence_png = out_dir / "coherence.png"

    map_dir = out_dir / "preview"
    map_phase = map_dir / "map_phase.png"
    map_coherence = map_dir / "map_coherence.png"
    map_quality = map_dir / "map_quality.png"
    phase_tif = out_dir / "phase.tif"
    coherence_tif = out_dir / "coherence.tif"

    if not layers.valid.any():
        raise EmptyDataError(
            "No valid pixels remain after applying the product mask.",
            details={
                "mask_path": product.mask_path,
                "mask_counts": layers.mask_counts,
                "hint": "Inspect the product mask encoding before interpreting this granule.",
            },
        )

    phase_render = render_quicklook(
        style=phase_style,
        data=layers.phase,
        valid=layers.valid,
        geometry=product.geometry,
        out_png=phase_png,
        subtitle=subtitle,
        source_line=(
            f"Source: {path.name}\n"
            f"Dataset: {product.phase.path} · valid pixels after mask: "
            f"{int(layers.valid.sum()):,}/{layers.valid.size:,}"
        ),
        warning=(
            "Unwrapped interferometric phase (radians) — NOT a displacement map. "
            "Atmospheric, ionospheric and orbital effects are present; no metric "
            "displacement has been measured."
        ),
        dpi=cfg.render_dpi,
    )
    coherence_render = render_quicklook(
        style=coherence_style,
        data=layers.coherence,
        valid=layers.valid,
        geometry=product.geometry,
        out_png=coherence_png,
        subtitle=subtitle,
        source_line=(
            f"Source: {path.name}\n"
            f"Dataset: {product.coherence.path} · valid pixels after mask: "
            f"{int(layers.valid.sum()):,}/{layers.valid.size:,}"
        ),
        warning=(
            "Coherence magnitude is a quality indicator for the phase relationship, "
            "not a measurement of ground motion."
        ),
        dpi=cfg.render_dpi,
    )

    emit("building geographic display preview (EPSG:4326, nearest-neighbour)")
    geo = build_geo_preview(
        product.geometry,
        phase=layers.phase,
        coherence=layers.coherence,
        components=layers.components,
        valid=layers.valid,
        water=layers.water,
        max_width=cfg.map_preview_width,
    )
    map_images: dict[str, Any] = {}
    map_images["phase"] = save_map_image(
        phase_style, geo.phase, geo.valid, map_phase, downsample=1
    )
    map_images["coherence"] = save_map_image(
        coherence_style, geo.coherence, geo.valid, map_coherence, downsample=1
    )
    quality_style = resolve_style(
        "quality", geo.valid.astype(np.float32), geo.valid, units="1"
    )
    map_images["quality"] = save_map_image(
        quality_style,
        geo.valid.astype(np.float32),
        geo.valid,
        map_quality,
        water=geo.water,
        downsample=1,
    )
    if geo.components is not None:
        comp_style = resolve_style(
            "connected_components", geo.components, geo.valid, units="1"
        )
        map_images["connected_components"] = save_map_image(
            comp_style,
            geo.components,
            geo.valid,
            map_dir / "map_components.png",
            downsample=1,
        )

    preview_meta = write_coherence_preview(
        coherence=geo.coherence,
        valid=geo.valid,
        out_bin=map_dir / "coherence_u8.bin",
        out_meta=map_dir / "coherence_u8.json",
        downsample=1,
    )

    emit("writing GeoTIFFs")
    phase_data = np.where(layers.valid, layers.phase, np.nan).astype(np.float32)
    coherence_data = np.where(layers.valid, layers.coherence, np.nan).astype(np.float32)
    write_geotiff(
        out_tif=phase_tif,
        data=phase_data,
        geometry=product.geometry,
        band_description=f"unwrapped interferometric phase ({product.phase.units})",
        tags={
            "NISAR_OBSERVATION_ID": obs_id,
            "NISAR_GRANULE_ID": product.granule_id,
            "NISAR_SOURCE_DATASET": product.phase.path,
            "NISAR_REFERENCE_START": product.reference_start or "unknown",
            "NISAR_SECONDARY_START": product.secondary_start or "unknown",
            "NISAR_PRODUCT_VERSION": product.product_version or "unknown",
            "NISAR_UNITS": product.phase.units,
            "NISAR_VALID_RULE": "finite phase AND product mask valid",
            "NISAR_INTERPRETATION": (
                "Unwrapped phase in radians. Not a displacement map. No phase-to-"
                "displacement conversion is applied by this pipeline."
            ),
        },
    )
    write_geotiff(
        out_tif=coherence_tif,
        data=coherence_data,
        geometry=product.geometry,
        band_description="interferometric coherence magnitude (dimensionless, 0-1)",
        tags={
            "NISAR_OBSERVATION_ID": obs_id,
            "NISAR_GRANULE_ID": product.granule_id,
            "NISAR_SOURCE_DATASET": product.coherence.path,
            "NISAR_REFERENCE_START": product.reference_start or "unknown",
            "NISAR_SECONDARY_START": product.secondary_start or "unknown",
            "NISAR_PRODUCT_VERSION": product.product_version or "unknown",
            "NISAR_UNITS": "1",
            "NISAR_VALID_RULE": "finite coherence AND product mask valid",
            "NISAR_INTERPRETATION": (
                "Coherence magnitude is a quality indicator for the interferometric "
                "phase relationship, not a displacement measurement."
            ),
        },
    )
    phase_tif_check = validate_geotiff(
        phase_tif,
        expected_shape=product.geometry.shape,
        expected_epsg=product.geometry.epsg,
        expected_transform=product.geometry.transform,
    )
    coherence_tif_check = validate_geotiff(
        coherence_tif,
        expected_shape=product.geometry.shape,
        expected_epsg=product.geometry.epsg,
        expected_transform=product.geometry.transform,
    )
    if not phase_tif_check["passed"] or not coherence_tif_check["passed"]:
        raise RenderingError(
            "A written GeoTIFF failed read-back validation.",
            details={
                "phase_tif": phase_tif_check,
                "coherence_tif": coherence_tif_check,
            },
        )

    emit("verifying event overlap (independent USGS reference)")
    reference = load_reference_events()
    image_footprint = _product_polygon(product)
    event_result = assess_events(
        product.geometry,
        phase=layers.phase,
        coherence=layers.coherence,
        valid=layers.valid,
        components=layers.components,
        mask_fields=None,
        events=reference["events"],
        footprint=image_footprint,
        footprint_source=(
            "product_bounding_polygon" if image_footprint is not None else "grid_extent"
        ),
    )
    event_result["reference_retrieved_utc"] = reference.get("retrieved_utc")
    event_result["reference_sources"] = reference.get("sources", [])
    event_result["sequence"] = reference.get("sequence")

    footprint_check = _footprint_check(product)
    roundtrip = product.geometry.validate_roundtrip()
    pre_launch = _is_pre_launch(product)

    warnings: list[str] = []
    if pre_launch:
        warnings.append(
            "This granule predates the NISAR launch (2025-07-30). Treat it as a "
            "format/pipeline sample, not a real-world observation."
        )
    if coherence_report.get("below_zero") or coherence_report.get("above_one"):
        warnings.append(
            "Coherence values outside the documented [0, 1] range were found and are "
            "reported without clipping."
        )
    if layers.mask_counts.get("reference_anomaly_pixels") or layers.mask_counts.get(
        "secondary_anomaly_pixels"
    ):
        warnings.append(
            "The product mask flags RSLC data anomalies in some pixels; these are "
            "reported and left in the arrays unless explicitly filtered."
        )
    if (
        layers.mask_counts.get("ionosphere_filled_pixels", 0)
        and layers.mask_counts["ionosphere_filled_pixels"] > 0.05 * layers.mask_counts["total_pixels"]
    ):
        warnings.append(
            "More than 5% of pixels are flagged as filled by the ionospheric filter; "
            "phase in those areas is interpolated during product generation."
        )
    if not event_result["summary"]["footprint_overlaps_any_event"]:
        warnings.append(
            "The raster footprint does not contain any reference event location; the "
            "interface must not label this observation as covering the earthquake."
        )

    checks = _build_checks(
        product=product,
        layers=layers,
        phase_stats=phase_stats,
        roundtrip=roundtrip,
        footprint_check=footprint_check,
        phase_tif_check=phase_tif_check,
        coherence_tif_check=coherence_tif_check,
        pre_launch=pre_launch,
    )

    outputs = {
        "phase_png": phase_png.name,
        "coherence_png": coherence_png.name,
        "phase_tif": phase_tif.name,
        "coherence_tif": coherence_tif.name,
        "metadata_json": "metadata.json",
        "report_md": "report.md",
        "map_phase_png": str(map_phase.relative_to(out_dir)).replace("\\", "/"),
        "map_coherence_png": str(map_coherence.relative_to(out_dir)).replace("\\", "/"),
        "map_quality_png": str(map_quality.relative_to(out_dir)).replace("\\", "/"),
        "coherence_preview_bin": str(
            (map_dir / "coherence_u8.bin").relative_to(out_dir)
        ).replace("\\", "/"),
    }
    if "connected_components" in map_images:
        outputs["map_components_png"] = str(
            (map_dir / "map_components.png").relative_to(out_dir)
        ).replace("\\", "/")
    output_sizes = {
        name: (out_dir / relative).stat().st_size
        for name, relative in outputs.items()
        if (out_dir / relative).exists()
    }

    metadata: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "observation_id": obs_id,
        "observation_label": _observation_label(product, reference),
        "generated_utc": utc_now(),
        "pipeline": {
            "name": PIPELINE_NAME,
            "version": PIPELINE_VERSION,
            "package_version": __version__,
        },
        "software_versions": software_versions(),
        "observation_dir": str(out_dir),
        "source": _source_block(product, path, pre_launch),
        "product_structure": {
            "frequency": product.frequency,
            "polarization": product.polarization,
            "grid_root": product.grid_root,
            "unwrapped_group": product.unwrapped_group,
            "layers": {key: spec.to_json() for key, spec in product.layers.items()},
            "mask_path": product.mask_path,
            "other_grids": _other_grids(product),
        },
        "georeferencing": {
            **product.geometry.to_json(),
            "grid_resolution": product.grid_resolution.to_json(),
            "roundtrip_check": roundtrip,
            "footprint": _footprint_block(product),
            "product_polygon_check": footprint_check,
        },
        "layers": {
            "phase": _layer_block(product.phase, phase_stats, phase_render, phase_style),
            "coherence": _layer_block(
                product.coherence, coherence_stats, coherence_render, coherence_style
            ),
            "mask": _mask_block(product, layers.mask_counts),
            "connected_components": (
                {
                    "dataset_path": product.layers["connected_components"].path,
                    "component_count": components_info["component_count"],
                    "largest_component": components_info["largest_component"],
                    "largest_component_fraction": components_info["largest_component_fraction"],
                    "components": components_info["components"],
                    "label_semantics": components_info["label_semantics"],
                }
                if components_info
                else None
            ),
        },
        "quality": {
            "default_coherence_threshold": cfg.default_coherence_threshold,
            "threshold_table": threshold_table,
            "coherence_range": coherence_report,
            "validity_rules": {
                "phase": "finite value AND product mask valid",
                "coherence": "finite value AND product mask valid",
                "display_threshold": (
                    "pixels below the interactively selected coherence threshold are "
                    "hidden in the map overlay; the exported GeoTIFF keeps all valid "
                    "measurements"
                ),
                "connected_components": "labels retained; 0 is a valid label, fill is missing",
            },
            "largest_component": (
                largest_component_label(layers.components, layers.valid)
                if layers.components is not None
                else None
            ),
        },
        "event_assessment": event_result,
        "checks": checks,
        "validation": {
            "states": build_validation_states({"checks": checks}),
            "overall_status": (
                "validated_for_phase_and_coherence_display"
                if all(check["status"] == "passed" for check in checks[:5])
                else "incomplete"
            ),
            "geotiff_readback": {
                "phase": phase_tif_check,
                "coherence": coherence_tif_check,
            },
        },
        "outputs": outputs,
        "output_sizes": output_sizes,
        "limitations": LIMITATIONS,
        "warnings": warnings,
        "processing_config": cfg.to_json(),
        "fingerprint": fingerprint,
        "map_view": {
            "images": _relative_map_images(map_images, out_dir),
            "coherence_preview": {
                **preview_meta,
                "path": str((map_dir / "coherence_u8.bin").relative_to(out_dir)).replace("\\", "/"),
                "metadata_path": str(
                    (map_dir / "coherence_u8.json").relative_to(out_dir)
                ).replace("\\", "/"),
            },
            "display_grid": geo.to_json(),
            "native_bounds": product.geometry.bounds.to_json(),
            "epsg": product.geometry.epsg,
            "crs_name": product.geometry.crs_name,
            "geometry": product.geometry.to_json(),
            "legends": {
                "phase": {
                    "label": phase_style.legend,
                    "vmin": phase_style.vmin,
                    "vmax": phase_style.vmax,
                    "colormap": phase_style.cmap,
                    "stops": colormap_stops(str(phase_style.cmap), 11),
                    "extend": phase_style.extend,
                    "saturated_low_pixels": phase_style.saturated_low,
                    "saturated_high_pixels": phase_style.saturated_high,
                },
                "coherence": {
                    "label": coherence_style.legend,
                    "vmin": coherence_style.vmin,
                    "vmax": coherence_style.vmax,
                    "colormap": coherence_style.cmap,
                    "stops": colormap_stops(str(coherence_style.cmap), 11),
                    "extend": coherence_style.extend,
                },
                "quality": {
                    "label": quality_style.legend,
                    "classes": [
                        {"label": "Valid land", "color": "#38b2ac"},
                        {"label": "Valid water", "color": "#4285f4"},
                        {"label": "Invalid / outside swath", "color": "transparent"},
                    ],
                },
                "connected_components": {
                    "label": "Connected-component label (colour cycles every 20 labels)",
                    "label_count": (
                        comp_style.extra.get("label_count") if geo.components is not None else None
                    ),
                    "stops": colormap_stops("tab20", 20),
                },
            },
            "note": (
                "Map preview is resampled to a WGS84 display grid with nearest-neighbour "
                "resampling; quicklook PNGs and GeoTIFFs retain the native grid."
            ),
        },
    }

    write_json(out_dir / "metadata.json", metadata)
    write_json(out_dir / "validation.json", metadata["validation"])
    write_report(out_dir / "report.md", metadata)
    emit(f"done in {time.perf_counter() - started:.1f}s → {out_dir}")
    return json_safe(metadata)


def _relative_map_images(images: Mapping[str, Mapping[str, Any]], out_dir: Path) -> dict[str, Any]:
    """Rewrite map image paths relative to the observation directory."""
    out: dict[str, Any] = {}
    for key, value in images.items():
        entry = dict(value)
        try:
            entry["path"] = str(Path(str(value["path"])).relative_to(out_dir)).replace("\\", "/")
        except ValueError:
            pass
        out[key] = entry
    return out


def human_time(value: str | None) -> str:
    """Format an ISO-8601 acquisition time for display without nanoseconds."""
    if not value:
        return "date unknown"
    text = value.strip()
    if "T" in text:
        date_part, time_part = text.split("T", 1)
        seconds = time_part.split(".", 1)[0]
        return f"{date_part} {seconds} UTC"
    return text


def _read_metadata(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _outputs_present(metadata: Mapping[str, Any], out_dir: Path) -> bool:
    outputs = metadata.get("outputs", {})
    if not outputs:
        return False
    return all((out_dir / str(name)).exists() for name in outputs.values())


def _phase_statistics(layers: LoadedLayers, mask_valid: np.ndarray | None) -> dict[str, Any]:
    from .statistics import summarize

    return summarize(
        layers.phase,
        layers.valid,
        name="unwrapped phase",
        units="radians",
    ).to_json()


def _coherence_statistics(layers: LoadedLayers, mask_valid: np.ndarray | None) -> dict[str, Any]:
    from .statistics import summarize

    return summarize(
        layers.coherence,
        layers.valid,
        name="coherence magnitude",
        units="1",
    ).to_json()


def _threshold_table(layers: LoadedLayers, cfg: ProcessConfig) -> list[dict[str, Any]]:
    from .statistics import threshold_table

    return threshold_table(
        layers.coherence,
        layers.phase,
        layers.valid,
        thresholds=cfg.threshold_steps,
    )


def _layer_block(spec: Any, stats: Mapping[str, Any], render: Mapping[str, Any], style: Any) -> dict[str, Any]:
    display = dict(render.get("display_limits", {}))
    display.update(
        {
            "percentiles": style.extra.get("percentiles"),
            "saturated_low_pixels": render.get("saturated_low_pixels", 0),
            "saturated_high_pixels": render.get("saturated_high_pixels", 0),
            "legend": style.legend,
            "colormap": style.cmap,
        }
    )
    return {
        "dataset_path": spec.path,
        "units": spec.units,
        "description": spec.description,
        "shape_rows_cols": [int(spec.shape[0]), int(spec.shape[1])],
        "dtype": spec.dtype,
        "fill_value": spec.fill_value,
        "dataset_attributes": spec.attrs,
        "statistics": dict(stats),
        "display": display,
        "outputs": {"quicklook_png": render.get("path")},
    }


def _mask_block(product: GunwProduct, counts: Mapping[str, Any]) -> dict[str, Any] | None:
    if not product.mask_path:
        return None
    return {
        "dataset_path": product.mask_path,
        "coverage": dict(counts),
        "decoding": (
            "bits 0-7: water flag (hundreds digit), reference subswath (tens), "
            "secondary subswath (ones); a zero subswath digit means invalid. "
            "bits 8-15 secondary RSLC anomaly flags, bits 16-23 reference RSLC "
            "anomaly flags, bit 24 ionospheric-filter fill flag."
        ),
    }


def _source_block(product: GunwProduct, path: Path, pre_launch: bool) -> dict[str, Any]:
    identification = product.identification
    return {
        "path": str(path),
        "file_name": path.name,
        "file_size_bytes": product.file_size,
        "granule_id": product.granule_id,
        "product_type": product.product_type,
        "product_version": product.product_version,
        "product_specification_version": product.product_specification_version,
        "product_doi": identification.get("productDoi"),
        "processing_datetime": identification.get("processingDateTime"),
        "processing_type": identification.get("processingType"),
        "processing_center": identification.get("processingCenter"),
        "composite_release_id": identification.get("compositeReleaseId"),
        "mission_id": identification.get("missionId"),
        "instrument_name": identification.get("instrumentName"),
        "platform_name": identification.get("platformName"),
        "radar_band": identification.get("radarBand"),
        "track_number": identification.get("trackNumber"),
        "frame_number": identification.get("frameNumber"),
        "orbit_pass_direction": identification.get("orbitPassDirection"),
        "look_direction": identification.get("lookDirection"),
        "is_geocoded": identification.get("isGeocoded"),
        "is_full_frame": identification.get("isFullFrame"),
        "reference_absolute_orbit": identification.get("referenceAbsoluteOrbitNumber"),
        "secondary_absolute_orbit": identification.get("secondaryAbsoluteOrbitNumber"),
        "reference_start": product.reference_start,
        "reference_end": product.reference_end,
        "secondary_start": product.secondary_start,
        "secondary_end": product.secondary_end,
        "temporal_baseline_days": product.temporal_baseline_days,
        "frequency": product.frequency,
        "polarization": product.polarization,
        "center_frequency_hz": product.center_frequency_hz,
        "wavelength_m": product.wavelength_m,
        "wavelength_derivation": "c / centerFrequency (derived here; not a product field)",
        "static_layers_url": identification.get("staticLayersDataAccess"),
        "is_pre_launch_sample": pre_launch,
        "bounding_polygon_wkt": product.bounding_polygon_wkt,
        "identification": identification,
        "file_attributes": product.file_attributes,
        "processing_parameters": product.processing_parameters,
    }


def _other_grids(product: GunwProduct) -> list[dict[str, Any]]:
    """List sibling grids so the UI can explain why coordinates are per-grid."""
    grids: list[dict[str, Any]] = []
    try:
        with h5py.File(product.path, "r") as h5:
            root = h5[product.grid_root]
            for name in sorted(root.keys()):
                obj = root[name]
                if not isinstance(obj, h5py.Group):
                    continue
                entry: dict[str, Any] = {"name": name, "datasets": {}}
                for sub_name, sub in obj.items():
                    if isinstance(sub, h5py.Group):
                        for ds_name, ds in sub.items():
                            if isinstance(ds, h5py.Dataset) and ds.ndim == 2:
                                entry["datasets"][f"{sub_name}/{ds_name}"] = {
                                    "shape": list(ds.shape),
                                    "dtype": str(ds.dtype),
                                }
                    elif isinstance(sub, h5py.Dataset) and sub.ndim == 2:
                        entry["datasets"][sub_name] = {
                            "shape": list(sub.shape),
                            "dtype": str(sub.dtype),
                        }
                grids.append(entry)
    except Exception:  # pragma: no cover - diagnostics only
        return grids
    return grids


def _polygon_block(
    poly: Any, *, derivation: str, source_dataset: str | None = None
) -> dict[str, Any]:
    # Product footprints are OGR WKT with an ellipsoidal height as third ordinate.
    coords = [[float(coord[0]), float(coord[1])] for coord in poly.exterior.coords]
    minx, miny, maxx, maxy = poly.bounds
    block: dict[str, Any] = {
        "type": "Polygon",
        "crs": "EPSG:4326",
        "coordinates": coords,
        "vertex_count": len(coords),
        "wgs84_bounds": [round(minx, 6), round(miny, 6), round(maxx, 6), round(maxy, 6)],
        "area_deg2": float(poly.area),
        "derivation": derivation,
    }
    if source_dataset:
        block["source_dataset"] = source_dataset
    return block


def _product_polygon(product: GunwProduct) -> Any | None:
    """Authoritative image footprint from the product, when present."""
    if not product.bounding_polygon_wkt:
        return None
    try:
        poly = shapely_wkt.loads(product.bounding_polygon_wkt)
    except Exception:
        return None
    if not poly.is_valid:
        poly = poly.buffer(0)
    if poly.is_empty:
        return None
    return poly


def _footprint_block(product: GunwProduct) -> dict[str, Any]:
    """Both footprints: the derived grid extent and the product image footprint.

    A GUNW map grid is a rectangle in UTM that *contains* a rotated radar swath.
    The rectangle is therefore larger than the imaged area and its corners may be
    entirely empty.  The product's ``boundingPolygon`` describes the actual image
    footprint and is preferred whenever it is present.
    """
    grid_extent = _polygon_block(
        product.geometry.footprint_wgs84(),
        derivation="densified edges of the raster's coordinate grid, transformed with pyproj",
    )
    product_poly = _product_polygon(product)
    product_block = None
    if product_poly is not None:
        product_block = _polygon_block(
            product_poly,
            derivation="product identification/boundingPolygon (OGR WKT, EPSG:4326)",
            source_dataset="science/LSAR/identification/boundingPolygon",
        )
    return {
        "primary": "product_bounding_polygon" if product_block else "grid_extent",
        "grid_extent": grid_extent,
        "product_bounding_polygon": product_block,
    }


def _footprint_check(product: GunwProduct) -> dict[str, Any]:
    """Check the product image footprint against the derived grid extent."""
    grid_extent = product.geometry.footprint_wgs84()
    product_poly = _product_polygon(product)
    if product_poly is None:
        return {
            "status": "not_available",
            "detail": "The product does not provide a parsable identification/boundingPolygon.",
            "grid_extent_area_deg2": float(grid_extent.area),
        }
    try:
        intersection = grid_extent.intersection(product_poly).area
        product_inside_grid = intersection / product_poly.area if product_poly.area else 0.0
        grid_inside_product = intersection / grid_extent.area if grid_extent.area else 0.0
    except Exception as exc:  # pragma: no cover - exotic geometry
        return {"status": "failed", "detail": f"footprint comparison failed: {exc}"}
    status = "passed" if product_inside_grid >= 0.99 else "failed"
    detail = (
        f"{product_inside_grid * 100:.2f}% of the product image footprint lies inside "
        f"the derived UTM grid extent. The grid extent is "
        f"{grid_extent.area / product_poly.area:.2f}x the image footprint area, which is "
        "expected because a map grid is a rectangle around a rotated swath."
    )
    return {
        "status": status,
        "product_inside_grid_fraction": float(product_inside_grid),
        "grid_inside_product_fraction": float(grid_inside_product),
        "grid_extent_area_deg2": float(grid_extent.area),
        "product_area_deg2": float(product_poly.area),
        "detail": detail,
    }


def _is_pre_launch(product: GunwProduct) -> bool:
    dates = [d for d in (product.reference_start, product.secondary_start) if d]
    return any(d[:10] < PRE_LAUNCH_DATE for d in dates)


def _observation_label(product: GunwProduct, reference: Mapping[str, Any]) -> str:
    ident = product.identification
    return (
        f"NISAR GUNW {product.polarization} · track {ident.get('trackNumber', '?')} "
        f"frame {ident.get('frameNumber', '?')} · "
        f"{str(product.reference_start)[:10]} → {str(product.secondary_start)[:10]}"
    )


def _build_checks(
    *,
    product: GunwProduct,
    layers: LoadedLayers,
    phase_stats: Mapping[str, Any],
    roundtrip: Mapping[str, Any],
    footprint_check: Mapping[str, Any],
    phase_tif_check: Mapping[str, Any],
    coherence_tif_check: Mapping[str, Any],
    pre_launch: bool,
) -> list[dict[str, Any]]:
    geotiff_ok = phase_tif_check.get("passed") and coherence_tif_check.get("passed")
    checks = [
        {
            "id": "dataset_found",
            "label": "Granule present on disk",
            "status": "passed",
            "detail": f"{product.file_size:,} bytes at {product.path}",
        },
        {
            "id": "metadata_inspected",
            "label": "Product metadata inspected",
            "status": "passed",
            "detail": (
                f"{product.product_type} v{product.product_version} "
                f"(spec {product.product_specification_version}); "
                f"{len(product.layers)} layers; frequency {product.frequency}, "
                f"polarization {product.polarization}"
            ),
        },
        {
            "id": "raster_readable",
            "label": "Phase and coherence rasters readable",
            "status": "passed" if layers.valid.any() else "failed",
            "detail": (
                f"phase {list(layers.phase.shape)} {layers.phase.dtype}; "
                f"coherence {list(layers.coherence.shape)} {layers.coherence.dtype}; "
                f"valid pixels {int(layers.valid.sum()):,}/{layers.valid.size:,}"
            ),
        },
        {
            "id": "georeferencing_validated",
            "label": "Grid georeferencing validated",
            "status": "passed",
            "detail": (
                f"EPSG:{product.geometry.epsg} ({product.geometry.crs_name}); "
                f"{product.geometry.dx:g}×{product.geometry.dy:g} m posting; "
                f"method {product.geometry.method}; round-trip max error "
                f"{roundtrip.get('max_map_error', 0):.2e}; GeoTIFF read-back "
                f"{'passed' if geotiff_ok else 'failed'}"
            ),
        },
        {
            "id": "footprint_validated",
            "label": "Geographic footprint validated",
            "status": footprint_check.get("status", "failed"),
            "detail": footprint_check.get("detail"),
        },
        {
            "id": "scientific_interpretation_validated",
            "label": "Scientific interpretation validated",
            "status": "not_validated",
            "detail": (
                "Phase is delivered in radians with coherence and masks. No "
                "phase-to-displacement conversion is applied, so no deformation "
                "interpretation is claimed."
            ),
        },
    ]
    if pre_launch:
        checks.append(
            {
                "id": "sample_product_notice",
                "label": "Pre-launch sample product",
                "status": "warning",
                "detail": "Acquisition dates precede the NISAR launch; not a real observation.",
            }
        )
    return checks


# ---------------------------------------------------------------------------
# Validate
# ---------------------------------------------------------------------------
def validate_granule(
    granule: str | Path,
    *,
    output_dir: str | Path | None = None,
    compute_sha256_value: bool = True,
    frequency: str | None = None,
    polarization: str | None = None,
) -> dict[str, Any]:
    """Inspect metadata, georeferencing, readable windows and footprint overlap."""
    path = Path(granule)
    started = time.perf_counter()
    product = open_product(path, frequency=frequency, polarization=polarization)
    stat_before = path.stat()

    with h5py.File(path, "r") as h5:
        read_report = {}
        for key in ("phase", "coherence", "connected_components"):
            if key not in product.layers:
                read_report[key] = {"present": False}
                continue
            ds = h5[product.layers[key].path]
            probe = np.asarray(ds[0:2, 0:2])
            read_report[key] = {
                "present": True,
                "dataset_path": ds.name,
                "shape": list(ds.shape),
                "dtype": str(ds.dtype),
                "first_values": json_safe(probe.ravel().tolist()),
            }
        if product.mask_path:
            ds = h5[product.mask_path]
            read_report["mask"] = {
                "present": True,
                "dataset_path": ds.name,
                "shape": list(ds.shape),
                "dtype": str(ds.dtype),
                "fill_value": json_safe(ds.attrs.get("_FillValue")),
            }

    sample = _window_sample(product, rows=32, cols=32)
    footprint_check = _footprint_check(product)
    roundtrip = product.geometry.validate_roundtrip()
    stat_after = path.stat()
    sha = file_sha256(path) if compute_sha256_value else None

    checks = [
        {
            "id": "dataset_found",
            "status": "passed" if path.exists() else "failed",
            "detail": f"{stat_after.st_size:,} bytes",
        },
        {
            "id": "metadata_inspected",
            "status": "passed",
            "detail": f"{product.granule_id}",
        },
        {
            "id": "raster_readable",
            "status": (
                "passed"
                if read_report.get("phase", {}).get("present")
                and read_report.get("coherence", {}).get("present")
                else "failed"
            ),
            "detail": ", ".join(
                f"{k}: {v.get('shape')}" for k, v in read_report.items() if v.get("present")
            ),
        },
        {
            "id": "georeferencing_validated",
            "status": "passed",
            "detail": (
                f"EPSG:{product.geometry.epsg}; round-trip checked "
                f"{roundtrip['checked_pixels']} pixels; max map error "
                f"{roundtrip['max_map_error']:.2e}"
            ),
        },
        {
            "id": "footprint_validated",
            "status": footprint_check.get("status", "failed"),
            "detail": footprint_check.get("detail"),
        },
        {
            "id": "scientific_interpretation_validated",
            "status": "not_validated",
            "detail": "No displacement conversion or event-causation claim is validated.",
        },
    ]

    reference = load_reference_events()
    image_poly = _product_polygon(product)
    events = []
    for event in reference["events"]:
        lon = float(event["longitude"])
        lat = float(event["latitude"])
        easting, northing = product.geometry.lonlat_to_map(lon, lat)
        inside = product.geometry.contains_map(easting, northing)
        row, col = product.geometry.map_to_pixel(easting, northing)
        inside_image = (
            bool(image_poly.contains(Point(lon, lat))) if image_poly is not None else None
        )
        events.append(
            {
                "id": event["id"],
                "label": event["label"],
                "magnitude": event["magnitude"],
                "inside_raster_bounds": bool(inside),
                "inside_image_footprint": inside_image,
                "row_col_fractional": [float(row), float(col)] if inside else None,
                "source_url": event["source_url"],
            }
        )

    result: dict[str, Any] = {
        "generated_utc": utc_now(),
        "pipeline": {"name": PIPELINE_NAME, "version": PIPELINE_VERSION},
        "software_versions": software_versions(),
        "source": _source_block(product, path, _is_pre_launch(product)),
        "raw_file_integrity": {
            "size_bytes": stat_after.st_size,
            "mtime_ns": stat_after.st_mtime_ns,
            "unchanged_during_validation": (
                stat_before.st_size == stat_after.st_size
                and stat_before.st_mtime_ns == stat_after.st_mtime_ns
            ),
            "sha256": sha,
        },
        "product_structure": {
            "frequency": product.frequency,
            "polarization": product.polarization,
            "grid_root": product.grid_root,
            "layers": {key: spec.to_json() for key, spec in product.layers.items()},
            "mask_path": product.mask_path,
            "other_grids": _other_grids(product),
        },
        "georeferencing": {
            **product.geometry.to_json(),
            "grid_resolution": product.grid_resolution.to_json(),
            "roundtrip_check": roundtrip,
            "footprint": _footprint_block(product),
            "product_polygon_check": footprint_check,
        },
        "read_test": read_report,
        "window_sample": sample,
        "events": events,
        "checks": checks,
        "validation": {
            "states": build_validation_states({"checks": checks}),
            "overall_status": (
                "metadata_and_georeferencing_validated"
                if all(c["status"] == "passed" for c in checks[:5])
                else "incomplete"
            ),
        },
        "elapsed_seconds": round(time.perf_counter() - started, 2),
    }

    if output_dir is not None:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        write_json(out / "validation.json", result)
        (out / "validation.md").write_text(_render_validation_markdown(result), encoding="utf-8")
    return json_safe(result)


def _window_sample(product: GunwProduct, *, rows: int, cols: int) -> dict[str, Any]:
    r1 = min(rows, product.geometry.height)
    c1 = min(cols, product.geometry.width)
    phase = product.read("phase", slice(0, r1), slice(0, c1))
    coherence = product.read("coherence", slice(0, r1), slice(0, c1))
    return {
        "window_rows": [0, r1],
        "window_cols": [0, c1],
        "phase_finite_fraction": float(np.isfinite(phase).mean()),
        "coherence_finite_fraction": float(np.isfinite(coherence).mean()),
        "phase_nan_count": int(np.count_nonzero(~np.isfinite(phase))),
        "note": "NaNs in an edge window are expected where the rotated footprint leaves the grid.",
    }


def _render_validation_markdown(result: Mapping[str, Any]) -> str:
    source = result.get("source", {})
    geo = result.get("georeferencing", {})
    lines = [
        f"# Validation record — {source.get('granule_id')}",
        "",
        f"Generated {result.get('generated_utc')} by {PIPELINE_NAME} {PIPELINE_VERSION}.",
        "",
        "## Checks",
        "",
        "| Check | Status | Detail |",
        "| --- | --- | --- |",
    ]
    for check in result.get("checks", []):
        lines.append(f"| {check.get('id')} | **{check.get('status')}** | {check.get('detail')} |")
    lines += [
        "",
        "## Georeferencing",
        "",
        f"- CRS: {geo.get('crs_name')} (EPSG:{geo.get('epsg')})",
        f"- Shape: {geo.get('height')} rows × {geo.get('width')} columns",
        f"- Posting: {geo.get('pixel_spacing')}",
        f"- Coordinate convention: {geo.get('pixel_convention')}",
        f"- Method: {geo.get('georeferencing_method')}",
        f"- Round trip: {json.dumps(geo.get('roundtrip_check'))}",
        f"- Product polygon check: {json.dumps(geo.get('product_polygon_check'))}",
        "",
        "## Raw file integrity",
        "",
        f"```json\n{json.dumps(result.get('raw_file_integrity'), indent=2)}\n```",
        "",
        "## Reference events",
        "",
        "| Event | Magnitude | Inside raster bounds | Row/col |",
        "| --- | --- | --- | --- |",
    ]
    for event in result.get("events", []):
        lines.append(
            f"| {event.get('label')} ({event.get('id')}) | {event.get('magnitude')} | "
            f"{event.get('inside_raster_bounds')} | {event.get('row_col_fractional')} |"
        )
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Inspect
# ---------------------------------------------------------------------------
def inspect_granule(
    granule: str | Path, *, frequency: str | None = None, polarization: str | None = None
) -> dict[str, Any]:
    """Metadata-only inspection: structure, layers, grids and georeferencing."""
    path = Path(granule)
    started = time.perf_counter()
    product = open_product(path, frequency=frequency, polarization=polarization)
    with h5py.File(path, "r") as h5:
        structure = structure_summary(h5)
        grids = _other_grids(product)
    result = {
        "generated_utc": utc_now(),
        "pipeline": {"name": PIPELINE_NAME, "version": PIPELINE_VERSION},
        "path": str(path),
        "file_size_bytes": product.file_size,
        "identification": product.identification,
        "product_structure": {
            "frequency": product.frequency,
            "polarization": product.polarization,
            "grid_root": product.grid_root,
            "unwrapped_group": product.unwrapped_group,
            "layers": {key: spec.to_json() for key, spec in product.layers.items()},
            "mask_path": product.mask_path,
            "grids": grids,
        },
        "georeferencing": {
            **product.geometry.to_json(),
            "grid_resolution": product.grid_resolution.to_json(),
            "roundtrip_check": product.geometry.validate_roundtrip(),
            "footprint": _footprint_block(product),
            "product_polygon_check": _footprint_check(product),
        },
        "structure": {
            "group_count": len(structure["groups"]),
            "dataset_count": len(structure["datasets"]),
            "truncated": structure["truncated"],
        },
        "elapsed_seconds": round(time.perf_counter() - started, 2),
    }
    return json_safe(result)


# ---------------------------------------------------------------------------
# Reporting helpers used by the CLI
# ---------------------------------------------------------------------------
def summarize_observation(metadata: Mapping[str, Any]) -> dict[str, Any]:
    """Compact observation summary for dashboards."""
    source = metadata.get("source", {})
    layers = metadata.get("layers", {})
    phase = layers.get("phase", {}).get("statistics", {})
    coherence = layers.get("coherence", {}).get("statistics", {})
    return {
        "observation_id": metadata.get("observation_id"),
        "label": metadata.get("observation_label"),
        "granule_id": source.get("granule_id"),
        "reference_start": source.get("reference_start"),
        "secondary_start": source.get("secondary_start"),
        "polarization": source.get("polarization"),
        "track_number": source.get("track_number"),
        "frame_number": source.get("frame_number"),
        "orbit_pass_direction": source.get("orbit_pass_direction"),
        "is_pre_launch_sample": source.get("is_pre_launch_sample"),
        "phase": {
            "units": layers.get("phase", {}).get("units"),
            "valid_pixels": phase.get("measured_pixels"),
            "total_pixels": phase.get("total_pixels"),
            "coverage_percent": phase.get("coverage_percent"),
            "median": phase.get("median"),
            "p05": phase.get("p05"),
            "p95": phase.get("p95"),
        },
        "coherence": {
            "median": coherence.get("median"),
            "p05": coherence.get("p05"),
            "p95": coherence.get("p95"),
            "coverage_percent": coherence.get("coverage_percent"),
        },
        "validation": metadata.get("validation", {}),
        "event_summary": metadata.get("event_assessment", {}).get("summary"),
        "generated_utc": metadata.get("generated_utc"),
        "observation_dir": metadata.get("observation_dir"),
    }
