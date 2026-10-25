"""Metadata JSON, human-readable report and machine validation artifacts."""

from __future__ import annotations

import hashlib
import json
import math
import platform
import sys
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PIPELINE_NAME = "nisar-earth-in-motion"
PIPELINE_VERSION = "0.2.0"
SCHEMA_VERSION = "1.0"

VALIDATION_CHECKS = (
    ("dataset_found", "Granule present on disk"),
    ("metadata_inspected", "Product metadata inspected"),
    ("raster_readable", "Phase and coherence rasters readable"),
    ("georeferencing_validated", "Grid georeferencing validated"),
    ("footprint_validated", "Geographic footprint validated"),
    ("scientific_interpretation_validated", "Scientific interpretation validated"),
)


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def json_safe(value: Any) -> Any:
    """Recursively convert numpy/Path values into JSON-serialisable objects."""
    import numpy as np

    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, np.generic):
        return json_safe(value.item())
    if isinstance(value, np.ndarray):
        return [json_safe(item) for item in value.tolist()]
    if isinstance(value, Mapping):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    return str(value)


def write_json(path: Path, payload: Mapping[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(json_safe(payload), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


def software_versions() -> dict[str, Any]:
    """Record the versions that produced the outputs (reproducibility)."""
    versions: dict[str, Any] = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "pipeline": PIPELINE_VERSION,
    }
    for module_name in ("numpy", "scipy", "h5py", "rasterio", "pyproj", "matplotlib", "shapely", "PIL"):
        try:
            module = __import__(module_name)
            versions[module_name] = getattr(module, "__version__", "unknown")
        except Exception:  # pragma: no cover - optional dependency
            versions[module_name] = "not installed"
    try:
        import rasterio

        versions["gdal"] = rasterio.__gdal_version__
    except Exception:  # pragma: no cover
        pass
    return versions


def file_sha256(path: Path, chunk_bytes: int = 8 * 1024 * 1024) -> str:
    """Streaming SHA-256 of a file (the raw granule is only ever read)."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_bytes), b""):
            digest.update(chunk)
    return digest.hexdigest()


def compute_fingerprint(
    *,
    source_path: Path,
    source_size: int,
    source_mtime_ns: int,
    layers: Mapping[str, Any],
    config: Mapping[str, Any],
) -> str:
    """Deterministic fingerprint of inputs + processing configuration."""
    payload = {
        "pipeline_version": PIPELINE_VERSION,
        "source_path": str(source_path).replace("\\", "/"),
        "source_size": source_size,
        "source_mtime_ns": source_mtime_ns,
        "layers": {
            key: {
                "path": spec.get("dataset_path") if isinstance(spec, Mapping) else str(spec),
                "shape": spec.get("shape_rows_cols") if isinstance(spec, Mapping) else None,
            }
            for key, spec in layers.items()
        },
        "config": config,
    }
    blob = json.dumps(json_safe(payload), sort_keys=True).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def build_validation_states(metadata: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Derive UI/API validation states from recorded evidence.

    A state is only ``passed`` when the corresponding evidence exists.  The
    scientific-interpretation state is never automatically passed: no
    phase-to-displacement conversion is claimed by this pipeline.
    """
    checks = {check["id"]: check for check in metadata.get("checks", [])}
    states = []
    for key, label in VALIDATION_CHECKS:
        check = checks.get(key)
        if check is None:
            states.append({"id": key, "label": label, "status": "not_run", "detail": None})
        else:
            states.append(
                {
                    "id": key,
                    "label": label,
                    "status": check.get("status", "not_run"),
                    "detail": check.get("detail"),
                }
            )
    return states


def human_time(value: Any) -> str:
    """Format an ISO-8601 timestamp for humans (drop sub-second digits)."""
    if not value:
        return "date unknown"
    text = str(value).strip()
    if "T" in text:
        date_part, time_part = text.split("T", 1)
        return f"{date_part} {time_part.split('.', 1)[0]} UTC"
    return text


def render_report_markdown(metadata: Mapping[str, Any]) -> str:
    """Human-readable scientific report for one processed observation."""
    source = metadata.get("source", {})
    geo = metadata.get("georeferencing", {})
    layers = metadata.get("layers", {})
    quality = metadata.get("quality", {})
    events = metadata.get("event_assessment", {})
    outputs = metadata.get("outputs", {})
    phase = layers.get("phase", {})
    coherence = layers.get("coherence", {})
    mask_info = layers.get("mask", {})
    components = layers.get("connected_components", {})

    def fmt(value: Any, digits: int = 3) -> str:
        if value is None:
            return "not available"
        if isinstance(value, float):
            return f"{value:,.{digits}f}"
        if isinstance(value, int):
            return f"{value:,}"
        return str(value)

    lines: list[str] = []
    add = lines.append

    add(f"# NISAR // Earth in Motion — observation report: {metadata.get('observation_id')}")
    add("")
    add(f"Generated **{metadata.get('generated_utc')}** by `{PIPELINE_NAME}` {PIPELINE_VERSION}.")
    add("")
    add("## 1. What this observation is")
    add("")
    add(
        f"Source granule `{source.get('granule_id')}` — NISAR {source.get('product_type')} "
        f"(product version {source.get('product_version')}, specification "
        f"{source.get('product_specification_version')})."
    )
    add("")
    add(
        f"Reference acquisition **{human_time(source.get('reference_start'))}** → secondary "
        f"acquisition **{human_time(source.get('secondary_start'))}** "
        f"(temporal baseline {source.get('temporal_baseline_days')} days)."
    )
    add("")
    add(
        f"Track {source.get('track_number')}, frame {source.get('frame_number')}, "
        f"{source.get('orbit_pass_direction')} pass, {source.get('look_direction')}-looking, "
        f"band {source.get('radar_band')}, frequency {source.get('frequency')}, "
        f"polarization {source.get('polarization')}."
    )
    add("")
    add(f"Raw file: `{source.get('path')}` ({fmt(source.get('file_size_bytes'))} bytes, unmodified).")
    add("")
    if source.get("sha256"):
        add(f"SHA-256 of the raw granule: `{source['sha256']}`")
        add("")

    add("## 2. Data layers used")
    add("")
    add("| Layer | HDF5 dataset | Units | Shape | Valid pixels | Coverage |")
    add("| --- | --- | --- | --- | --- | --- |")
    for layer_name, layer in layers.items():
        if layer_name in {"mask", "connected_components"}:
            continue
        summary = layer.get("statistics", {})
        add(
            f"| {layer_name} | `{layer.get('dataset_path')}` | {layer.get('units')} | "
            f"{layer.get('shape_rows_cols')} | {fmt(summary.get('measured_pixels'))} | "
            f"{fmt(summary.get('coverage_percent'), 1)}% |"
        )
    add("")

    add("### 2.1 Unwrapped phase")
    add("")
    add(
        "The unwrapped interferogram is the phase difference between the reference and "
        "secondary acquisitions after ellipsoid and topographic flattening. Values are in "
        f"**{phase.get('units', 'unknown')}**, the unit declared by the product dataset. "
        "This is **not** a displacement map in metres."
    )
    add("")
    phase_stats = phase.get("statistics", {})
    add(
        f"Measured pixels: {fmt(phase_stats.get('measured_pixels'))} of "
        f"{fmt(phase_stats.get('total_pixels'))} "
        f"({fmt(phase_stats.get('coverage_percent'), 1)}%). "
        f"Range {fmt(phase_stats.get('minimum'))} to {fmt(phase_stats.get('maximum'))} "
        f"{phase.get('units', '')}, median {fmt(phase_stats.get('median'))}, "
        f"p05–p95 {fmt(phase_stats.get('p05'))} to {fmt(phase_stats.get('p95'))}."
    )
    add("")
    display = phase.get("display", {})
    if display:
        add(
            f"Colour limits {fmt(display.get('vmin'))} … {fmt(display.get('vmax'))} "
            f"(percentiles {display.get('percentiles')}); "
            f"{fmt(display.get('saturated_low_pixels'))} low and "
            f"{fmt(display.get('saturated_high_pixels'))} high values are clipped for "
            "display only. The GeoTIFF keeps the original measurements."
        )
        add("")

    add("### 2.2 Coherence magnitude")
    add("")
    add(
        "Coherence magnitude describes how similar the two radar observations are. "
        "It is a quality indicator for the phase relationship, not a measurement of "
        "ground motion. Values are dimensionless on [0, 1]."
    )
    add("")
    coh_stats = coherence.get("statistics", {})
    add(
        f"Measured pixels: {fmt(coh_stats.get('measured_pixels'))}; median "
        f"{fmt(coh_stats.get('median'))}, p05–p95 {fmt(coh_stats.get('p05'))} to "
        f"{fmt(coh_stats.get('p95'))}, maximum {fmt(coh_stats.get('maximum'))}."
    )
    add("")

    add("### 2.3 Product mask")
    add("")
    if mask_info:
        mask_coverage = mask_info.get("coverage", {})
        add(
            f"Mask dataset `{mask_info.get('dataset_path')}` decoded as "
            f"`{mask_coverage.get('encoding')}`: water flag and reference/secondary "
            "subswath digits in bits 0–7, anomaly flags in bits 8–23, and an "
            "ionospheric-fill flag in bit 24."
        )
        add("")
        add(
            f"Valid pixels {fmt(mask_coverage.get('valid_pixels'))} "
            f"({fmt((mask_coverage.get('valid_pixels') or 0) / max(1, mask_coverage.get('total_pixels') or 1) * 100, 1)}%), "
            f"water {fmt(mask_coverage.get('water_pixels'))}, "
            f"ionospheric-fill flagged {fmt(mask_coverage.get('ionosphere_filled_pixels'))}, "
            f"reference-anomaly flagged {fmt(mask_coverage.get('reference_anomaly_pixels'))}."
        )
        add("")
    else:
        add("No product mask dataset was present; validity relies on finite values only.")
        add("")

    if components:
        add("### 2.4 Connected components")
        add("")
        add(
            f"{fmt(components.get('component_count'))} component labels among valid pixels; "
            f"largest label {fmt(components.get('largest_component'))} covers "
            f"{fmt((components.get('largest_component_fraction') or 0) * 100, 1)}% of valid "
            "pixels. Separate components can carry different integer phase ambiguities, "
            "so phase values between components are not necessarily continuous."
        )
        add("")

    add("## 3. Georeferencing")
    add("")
    add(
        "Coordinates were resolved from the phase raster's own HDF5 dimension scales, "
        "not by searching the file for a dataset with the same name. Each GUNW grid "
        "(20 m wrapped, 80 m unwrapped) carries its own coordinate vectors."
    )
    add("")
    add(f"- CRS: **{geo.get('crs_name')}** (EPSG:{geo.get('epsg')})")
    add(
        f"- Grid: {geo.get('width')} columns × {geo.get('height')} rows, posting "
        f"{fmt(geo.get('pixel_spacing', {}).get('x'))} m × "
        f"{fmt(geo.get('pixel_spacing', {}).get('y'))} m"
    )
    add(f"- Axis orientation: x {geo.get('x_axis')}, y {geo.get('y_axis')}")
    add(f"- Coordinate convention: {geo.get('pixel_convention')} (CF-1.7 dimension scales)")
    add(f"- Bounds: {json.dumps(geo.get('bounds'))}")
    add(f"- Resolution method: `{geo.get('georeferencing_method')}`")
    add(f"- Round-trip check: {json.dumps(geo.get('roundtrip_check'))}")
    add("")
    footprint = geo.get("footprint", {})
    product_fp = footprint.get("product_bounding_polygon")
    grid_extent = footprint.get("grid_extent") or {}
    if product_fp:
        add(
            f"- Product image footprint (WGS84 bounds): {product_fp.get('wgs84_bounds')} "
            f"({product_fp.get('vertex_count')} vertices, {product_fp.get('area_deg2'):.3f} deg²)"
        )
    if grid_extent:
        add(
            f"- Map-grid extent (WGS84 bounds): {grid_extent.get('wgs84_bounds')} "
            f"({grid_extent.get('area_deg2'):.3f} deg²); the grid is a rectangle around "
            "a rotated swath, so it is larger than the imaged area."
        )
    if product_fp or grid_extent:
        add("")
    footprint_check = geo.get("product_polygon_check", {})
    if footprint_check:
        add(
            f"- Comparison with the product's `boundingPolygon`: "
            f"{footprint_check.get('status')} — {footprint_check.get('detail')}"
        )
        add("")

    add("## 4. Geographic and event verification")
    add("")
    if events:
        add(f"- Footprint overlaps any reference event: **{events.get('summary', {}).get('footprint_overlaps_any_event')}**")
        add(f"- Events with locally usable data: {events.get('summary', {}).get('events_with_usable_local_data')}")
        add("")
        add("| Event | Magnitude | Inside raster | Nearest valid pixel | 10 km window valid | Median coherence | Status |")
        add("| --- | --- | --- | --- | --- | --- | --- |")
        for item in events.get("events", []):
            event = item.get("event", {})
            nearest = item.get("nearest_valid_pixel") or {}
            window = item.get("windows", [{}])[-1] if item.get("windows") else {}
            add(
                f"| {event.get('label')} ({event.get('id')}) | {event.get('magnitude')} | "
                f"{item.get('inside_raster_bounds')} | "
                f"{fmt(nearest.get('distance_km'), 2)} km | "
                f"{fmt((window.get('valid_fraction') or 0) * 100, 1)}% | "
                f"{fmt(window.get('coherence_median'))} | {item.get('status')} |"
            )
        add("")
        add(
            "Event coordinates come from the USGS ComCat reference file bundled with the "
            "application; the screening rules are exploratory rules of this application."
        )
        add("")

    add("## 5. Interpretation and limitations")
    add("")
    for limitation in metadata.get("limitations", []):
        add(f"- {limitation}")
    add("")
    if metadata.get("warnings"):
        add("### Warnings")
        add("")
        for warning in metadata["warnings"]:
            add(f"- {warning}")
        add("")

    add("## 6. Quality filtering")
    add("")
    add(
        f"The default exploratory coherence threshold shown in the application is "
        f"{quality.get('default_coherence_threshold')}. It is a display/quality filter "
        "chosen by this application, not a product-defined threshold."
    )
    add("")
    table = quality.get("threshold_table", [])
    if table:
        add("| Coherence ≥ | Valid pixels | Coverage of valid | Median phase (rad) | Median coherence |")
        add("| --- | --- | --- | --- | --- |")
        for row in table:
            add(
                f"| {row.get('threshold')} | {fmt(row.get('valid_pixels'))} | "
                f"{fmt(row.get('coverage_percent'), 1)}% | {fmt(row.get('phase_median'))} | "
                f"{fmt(row.get('coherence_median'))} |"
            )
        add("")

    add("## 7. Validation")
    add("")
    add("| Check | Status | Detail |")
    add("| --- | --- | --- |")
    for item in metadata.get("validation", {}).get("states", []):
        add(f"| {item.get('label')} | **{item.get('status')}** | {item.get('detail') or ''} |")
    add("")

    add("## 8. Outputs")
    add("")
    for name, path in outputs.items():
        add(f"- `{name}`: `{path}`")
    add("")

    add("## 9. Reproduce")
    add("")
    add("```powershell")
    add(f"python -m nisar_eim process \"{source.get('path')}\" --id {metadata.get('observation_id')}")
    add(f"python -m nisar_eim validate \"{source.get('path')}\"")
    add("```")
    add("")
    add("## 10. Provenance")
    add("")
    add(f"- Product DOI: {source.get('product_doi') or 'not available'}")
    add(f"- Processing date/time (product): {source.get('processing_datetime')}")
    add(f"- Processing type: {source.get('processing_type')}")
    add(f"- Composite release: {source.get('composite_release_id')}")
    add(f"- Static layers: {source.get('static_layers_url') or 'not available'}")
    add(f"- Software versions: {json.dumps(metadata.get('software_versions', {}))}")
    add("")
    add(
        "Scientific method and source documentation: `docs/SCIENTIFIC_METHOD.md`. "
        "Data validation record: `docs/DATA_VALIDATION.md`."
    )
    add("")
    return "\n".join(lines)


def write_report(path: Path, metadata: Mapping[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_report_markdown(metadata), encoding="utf-8")
    return path
