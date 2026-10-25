"""Rendering engine: presentation PNGs, web map images and GeoTIFF export.

Scientific arrays are never modified for display.  Colour limits are applied
only to a copy used for the image, and clipped values are reported so the
figure can state how much of the data is saturated at the display limits.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")  # headless: the app must run without a display server

import matplotlib.pyplot as plt
import numpy as np
import rasterio
from affine import Affine
from matplotlib.colors import Normalize
from PIL import Image
from rasterio.crs import CRS

from .errors import NisarError
from .geospatial import GridGeometry

INVALID_GREY = (0.16, 0.17, 0.19)

#: Display styles per layer.  ``units`` must come from the product metadata.
LAYER_STYLES: dict[str, dict[str, Any]] = {
    "phase": {
        "cmap": "viridis",
        "title": "Unwrapped interferometric phase",
        "legend": "Unwrapped phase ({units})",
        "percentile_limits": (2.0, 98.0),
        "extend": "both",
    },
    "coherence": {
        "cmap": "cividis",
        "title": "Interferometric coherence magnitude",
        "legend": "Coherence magnitude (dimensionless, 0–1)",
        "fixed_limits": (0.0, 1.0),
        "extend": "neither",
    },
    "quality": {
        "cmap": None,
        "title": "Validity and water classification",
        "legend": "Quality classes",
        "fixed_limits": None,
        "extend": "neither",
    },
    "connected_components": {
        "cmap": "tab20",
        "title": "Connected components of the unwrapped phase",
        "legend": "Component label",
        "fixed_limits": None,
        "extend": "neither",
    },
}


class RenderingError(NisarError):
    """The raster could not be rendered without misrepresenting it."""


@dataclass(frozen=True)
class LayerStyle:
    """Resolved display style for one layer."""

    key: str
    title: str
    legend: str
    cmap: str | None
    vmin: float | None
    vmax: float | None
    extend: str
    units: str
    saturated_low: int = 0
    saturated_high: int = 0
    extra: dict[str, Any] = field(default_factory=dict)


def resolve_style(
    key: str,
    data: np.ndarray,
    valid: np.ndarray,
    *,
    units: str,
    title_override: str | None = None,
) -> LayerStyle:
    """Build a display style for a layer, using percentiles for continuous layers."""
    template = LAYER_STYLES.get(key, LAYER_STYLES["phase"])
    vmin: float | None = None
    vmax: float | None = None
    saturated_low = 0
    saturated_high = 0
    extra: dict[str, Any] = {}

    if key == "coherence":
        vmin, vmax = (0.0, 1.0)
        finite = np.asarray(data)[np.asarray(valid, dtype=bool)]
        finite = finite[np.isfinite(finite)]
        if finite.size:
            saturated_low = int(np.count_nonzero(finite < vmin))
            saturated_high = int(np.count_nonzero(finite > vmax))
    elif key in {"phase", "ionosphere"}:
        lower, upper = template.get("percentile_limits", (2.0, 98.0))
        selected = np.asarray(data)[np.asarray(valid, dtype=bool)]
        selected = selected[np.isfinite(selected)]
        if selected.size:
            vmin, vmax = (float(v) for v in np.percentile(selected, [lower, upper]))
            if math.isclose(vmin, vmax):
                vmin, vmax = vmin - 1.0, vmax + 1.0
            saturated_low = int(np.count_nonzero(selected < vmin))
            saturated_high = int(np.count_nonzero(selected > vmax))
            extra["percentiles"] = [lower, upper]
        else:
            vmin, vmax = 0.0, 1.0
    elif key == "connected_components":
        labels = np.unique(np.asarray(data)[np.asarray(valid, dtype=bool)])
        labels = labels[labels != 65535]
        vmin = float(labels.min()) if labels.size else 0.0
        vmax = float(labels.max()) if labels.size else 1.0
        extra["label_count"] = int(labels.size)
    elif key == "quality":
        vmin, vmax = 0.0, 3.0

    legend = template["legend"]
    if key == "phase" and units and units != "unknown":
        legend = f"Unwrapped phase ({units})"
    return LayerStyle(
        key=key,
        title=title_override or template["title"],
        legend=legend,
        cmap=template["cmap"],
        vmin=vmin,
        vmax=vmax,
        extend=template.get("extend", "neither"),
        units=units,
        saturated_low=saturated_low,
        saturated_high=saturated_high,
        extra=extra,
    )


def _quality_rgba(valid: np.ndarray, water: np.ndarray | None, invalid_alpha: int = 0) -> np.ndarray:
    """Categorical validity image: land, water, invalid."""
    h, w = valid.shape
    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    land = valid & ~(water if water is not None else False)
    rgba[land] = (56, 178, 172, 230)
    if water is not None:
        rgba[valid & water] = (66, 133, 244, 230)
    rgba[~valid] = (40, 42, 48, invalid_alpha)
    return rgba


def _components_rgba(labels: np.ndarray, valid: np.ndarray) -> np.ndarray:
    cmap = matplotlib.colormaps["tab20"]
    h, w = labels.shape
    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    safe = np.where(valid, labels.astype(np.int64), 0)
    colors = (cmap(np.mod(safe, 20) / 20.0) * 255).astype(np.uint8)
    rgba[...] = colors
    rgba[~valid] = (40, 42, 48, 0)
    rgba[valid, 3] = 230
    return rgba


def layer_rgba(
    style: LayerStyle,
    data: np.ndarray,
    valid: np.ndarray,
    *,
    water: np.ndarray | None = None,
) -> np.ndarray:
    """Convert a scientific layer into an RGBA image (invalid pixels transparent)."""
    arr = np.asarray(data)
    vm = np.asarray(valid, dtype=bool)
    if arr.shape != vm.shape:
        raise RenderingError(
            "Layer data and validity mask shapes differ.",
            details={"data_shape": list(arr.shape), "mask_shape": list(vm.shape)},
        )
    if style.key == "quality":
        return _quality_rgba(vm, water)
    if style.key == "connected_components":
        return _components_rgba(np.nan_to_num(arr, nan=0.0), vm)

    assert style.cmap is not None
    assert style.vmin is not None and style.vmax is not None
    cmap = matplotlib.colormaps[style.cmap]
    norm = Normalize(vmin=style.vmin, vmax=style.vmax, clip=True)
    filled = np.where(vm, np.nan_to_num(arr, nan=style.vmin), style.vmin)
    rgba = (cmap(norm(filled)) * 255).astype(np.uint8)
    rgba[~vm] = (40, 42, 48, 0)
    rgba[vm, 3] = 255
    return rgba


def _downsample(arr: np.ndarray, factor: int) -> np.ndarray:
    if factor <= 1:
        return arr
    return arr[::factor, ::factor]


def destination_grid(
    geometry: GridGeometry, max_width: int = 1600
) -> tuple[Any, tuple[float, float, float, float], int, int]:
    """Choose a WGS84 display grid for the geographic map preview.

    Longitude/latitude pixels are not square in metres, so the height is derived
    from the latitude span scaled by cos(mean latitude) to keep the display
    roughly equal-area.
    """
    footprint = geometry.footprint_wgs84(step=64)
    west, south, east, north = (float(v) for v in footprint.bounds)
    lon_span = east - west
    lat_span = north - south
    if lon_span <= 0 or lat_span <= 0:
        raise RenderingError(
            "Geographic footprint has zero extent.",
            details={"bounds": [west, south, east, north]},
        )
    width = int(max(64, max_width))
    pixel_x = lon_span / width
    mean_lat = math.radians((south + north) / 2.0)
    aspect = (lat_span / (lon_span * max(1e-6, math.cos(mean_lat))))
    height = int(max(64, round(width * aspect)))
    pixel_y = lat_span / height
    transform = Affine(pixel_x, 0.0, west, 0.0, -pixel_y, north)
    return transform, (west, south, east, north), width, height


def _reproject(
    source: np.ndarray,
    *,
    src_transform: Any,
    src_epsg: int,
    dst_transform: Any,
    dst_shape: tuple[int, int],
    default: float = math.nan,
) -> np.ndarray:
    """Nearest-neighbour display resampling into EPSG:4326.

    Nearest neighbour is used deliberately: the preview must not invent values
    between measurements.  The GeoTIFF outputs keep the native 80 m grid.
    """
    from rasterio.warp import Resampling
    from rasterio.warp import reproject as warp_reproject

    source_arr = np.asarray(source, dtype=np.float32)
    destination = np.full(dst_shape, default, dtype=np.float32)
    warp_reproject(
        source=source_arr,
        destination=destination,
        src_transform=src_transform,
        src_crs=CRS.from_epsg(src_epsg),
        src_nodata=default,
        dst_transform=dst_transform,
        dst_crs="EPSG:4326",
        dst_nodata=default,
        resampling=Resampling.nearest,
    )
    return destination


@dataclass
class GeoPreview:
    """Display-resolution geographic arrays used by the web map."""

    phase: np.ndarray
    coherence: np.ndarray
    components: np.ndarray | None
    valid: np.ndarray
    water: np.ndarray
    transform: Any
    bounds: tuple[float, float, float, float]
    width: int
    height: int

    def to_json(self) -> dict[str, Any]:
        return {
            "crs": "EPSG:4326",
            "width": self.width,
            "height": self.height,
            "bounds": {
                "west": self.bounds[0],
                "south": self.bounds[1],
                "east": self.bounds[2],
                "north": self.bounds[3],
            },
            "transform": list(self.transform)[:6],
            "resampling": "nearest neighbour (display only)",
            "pixel_size_deg": {"x": float(self.transform.a), "y": float(-self.transform.e)},
        }


def build_geo_preview(
    geometry: GridGeometry,
    *,
    phase: np.ndarray,
    coherence: np.ndarray,
    components: np.ndarray | None,
    valid: np.ndarray,
    water: np.ndarray | None,
    max_width: int = 1600,
) -> GeoPreview:
    """Reproject display layers to a WGS84 grid for the interactive map."""
    dst_transform, bounds, width, height = destination_grid(geometry, max_width=max_width)
    dst_shape = (height, width)
    phase_geo = _reproject(
        phase,
        src_transform=geometry.transform,
        src_epsg=geometry.epsg,
        dst_transform=dst_transform,
        dst_shape=dst_shape,
    )
    coherence_geo = _reproject(
        coherence,
        src_transform=geometry.transform,
        src_epsg=geometry.epsg,
        dst_transform=dst_transform,
        dst_shape=dst_shape,
    )
    valid_geo = _reproject(
        np.asarray(valid, dtype=np.float32),
        src_transform=geometry.transform,
        src_epsg=geometry.epsg,
        dst_transform=dst_transform,
        dst_shape=dst_shape,
        default=0.0,
    ) > 0.5
    water_geo = None
    if water is not None:
        water_geo = _reproject(
            np.asarray(water, dtype=np.float32),
            src_transform=geometry.transform,
            src_epsg=geometry.epsg,
            dst_transform=dst_transform,
            dst_shape=dst_shape,
            default=0.0,
        ) > 0.5
    components_geo = None
    if components is not None:
        components_geo = _reproject(
            np.asarray(components, dtype=np.float32),
            src_transform=geometry.transform,
            src_epsg=geometry.epsg,
            dst_transform=dst_transform,
            dst_shape=dst_shape,
        )
    return GeoPreview(
        phase=phase_geo,
        coherence=coherence_geo,
        components=components_geo,
        valid=valid_geo,
        water=water_geo if water_geo is not None else np.zeros(dst_shape, dtype=bool),
        transform=dst_transform,
        bounds=bounds,
        width=width,
        height=height,
    )


def save_map_image(
    style: LayerStyle,
    data: np.ndarray,
    valid: np.ndarray,
    out_png: Path,
    *,
    water: np.ndarray | None = None,
    downsample: int = 2,
) -> dict[str, Any]:
    """Write a decoration-free RGBA PNG for the web map view."""
    out_png.parent.mkdir(parents=True, exist_ok=True)
    rgba = layer_rgba(style, data, valid, water=water)
    rgba = _downsample(rgba, downsample)
    Image.fromarray(rgba, mode="RGBA").save(out_png, optimize=True)
    return {
        "path": str(out_png),
        "downsample_factor": downsample,
        "width": int(rgba.shape[1]),
        "height": int(rgba.shape[0]),
    }


def render_quicklook(
    *,
    style: LayerStyle,
    data: np.ndarray,
    valid: np.ndarray,
    geometry: GridGeometry,
    out_png: Path,
    subtitle: str,
    source_line: str,
    warning: str,
    water: np.ndarray | None = None,
    dpi: int = 150,
    figure_size: tuple[float, float] = (12.0, 9.0),
) -> dict[str, Any]:
    """Write a presentation-quality PNG with legend, units and provenance."""
    out_png.parent.mkdir(parents=True, exist_ok=True)
    arr = np.asarray(data)
    vm = np.asarray(valid, dtype=bool)

    bounds = geometry.bounds
    # Display in map units, expressed in km when the CRS is metric.
    metric = geometry.crs.is_projected and geometry.crs.axis_info[0].unit_name in {"metre", "meter"}
    scale = 1000.0 if metric else 1.0
    axis_unit = "km" if metric else geometry.crs.axis_info[0].unit_name
    extent = (
        bounds.left / scale,
        bounds.right / scale,
        bounds.bottom / scale,
        bounds.top / scale,
    )

    if style.key == "quality":
        image = _quality_rgba(vm, water)
        extent_img = image
    elif style.key == "connected_components":
        extent_img = _components_rgba(np.nan_to_num(arr, nan=0.0), vm)
    else:
        assert style.cmap and style.vmin is not None and style.vmax is not None
        # Invalid pixels stay masked (transparent) so they can never be
        # mistaken for low-valued data; the footer reports their count.
        extent_img = np.ma.array(
            np.where(vm, np.nan_to_num(arr, nan=style.vmin), np.nan), mask=~vm
        )

    fig, ax = plt.subplots(figsize=figure_size, dpi=dpi)
    # Reserve space for the provenance footer; constrained_layout does not account
    # for fig.text, which previously collided with the axis labels.
    fig.subplots_adjust(left=0.075, right=0.88, top=0.86, bottom=0.17)
    if style.key in {"quality", "connected_components"}:
        ax.imshow(
            extent_img,
            origin="upper" if geometry.y_descending else "lower",
            extent=extent,
            interpolation="nearest",
        )
        if style.key == "quality":
            from matplotlib.patches import Patch

            handles = [
                Patch(facecolor=(56 / 255, 178 / 255, 172 / 255), label="Valid land"),
                Patch(facecolor=(66 / 255, 133 / 255, 244 / 255), label="Valid water"),
                Patch(facecolor=INVALID_GREY, label="Invalid (product mask)"),
            ]
            ax.legend(handles=handles, loc="upper right", fontsize=8, framealpha=0.9)
        else:
            count = style.extra.get("label_count", 0)
            ax.text(
                0.01,
                0.01,
                f"{count} connected-component labels present",
                transform=ax.transAxes,
                fontsize=8,
                color="white",
                bbox={"facecolor": INVALID_GREY, "alpha": 0.75, "pad": 3},
            )
    else:
        im = ax.imshow(
            extent_img,
            cmap=matplotlib.colormaps[style.cmap],
            norm=Normalize(vmin=style.vmin, vmax=style.vmax, clip=True),
            origin="upper" if geometry.y_descending else "lower",
            extent=extent,
            interpolation="nearest",
        )
        cb = fig.colorbar(im, ax=ax, shrink=0.85, extend=style.extend)
        cb.set_label(style.legend, fontsize=10)

    lon_min, lat_min, lon_max, lat_max = _lonlat_bounds(geometry)
    ax.set_xlabel(f"UTM easting ({axis_unit})" if metric else f"X ({axis_unit})")
    ax.set_ylabel(f"UTM northing ({axis_unit})" if metric else f"Y ({axis_unit})")
    ax.set_aspect("equal", adjustable="box")
    ax.set_title(
        f"NISAR // Earth in Motion — {style.title}\n"
        f"{subtitle}\n"
        f"{geometry.crs_name} (EPSG:{geometry.epsg}) · "
        f"{geometry.dx:g} m × {geometry.dy:g} m posting",
        fontsize=12,
    )

    saturation_note = ""
    if style.saturated_low or style.saturated_high:
        saturation_note = (
            f" Display limits clip {style.saturated_low:,} low and "
            f"{style.saturated_high:,} high values (colour only; GeoTIFF keeps the measurements)."
        )
    coverage = 100.0 * float(vm.mean()) if vm.size else 0.0
    fig.text(
        0.01,
        0.005,
        f"{source_line}\n"
        f"Displayed pixels: {int(vm.sum()):,} / {vm.size:,} ({coverage:.1f}%) · "
        f"WGS84 footprint: {lat_min:.3f}–{lat_max:.3f}°N, {lon_min:.3f}–{lon_max:.3f}°E."
        f"{saturation_note}\n{warning}",
        fontsize=7.5,
        va="bottom",
    )
    fig.savefig(out_png, dpi=dpi, facecolor="white")
    plt.close(fig)
    return {
        "path": str(out_png),
        "display_limits": {"vmin": style.vmin, "vmax": style.vmax},
        "saturated_low_pixels": style.saturated_low,
        "saturated_high_pixels": style.saturated_high,
    }


def colormap_stops(name: str, n: int = 11) -> list[dict[str, Any]]:
    """Sample a matplotlib colormap into CSS-friendly hex stops."""
    cmap = matplotlib.colormaps[name]
    stops = []
    for index in range(n):
        t = index / (n - 1) if n > 1 else 0.0
        r, g, b, _ = cmap(t)
        stops.append(
            {
                "t": round(t, 4),
                "hex": f"#{round(r * 255):02x}{round(g * 255):02x}{round(b * 255):02x}",
            }
        )
    return stops


def _lonlat_bounds(geometry: GridGeometry) -> tuple[float, float, float, float]:
    poly = geometry.footprint_wgs84(step=max(32, min(geometry.width, geometry.height) // 8))
    minx, miny, maxx, maxy = poly.bounds
    return (minx, miny, maxx, maxy)


def write_geotiff(
    *,
    out_tif: Path,
    data: np.ndarray,
    geometry: GridGeometry,
    band_description: str,
    tags: Mapping[str, Any],
    dtype: str = "float32",
    nodata: float = math.nan,
) -> dict[str, Any]:
    """Write a float GeoTIFF preserving the raster's native grid and NoData."""
    out_tif.parent.mkdir(parents=True, exist_ok=True)
    arr = np.asarray(data, dtype=dtype)
    if arr.shape != geometry.shape:
        raise RenderingError(
            "Refusing to write a GeoTIFF whose shape disagrees with its transform.",
            details={"data_shape": list(arr.shape), "geometry_shape": list(geometry.shape)},
        )
    string_tags = {}
    for key, value in tags.items():
        if isinstance(value, (dict, list, tuple)):
            string_tags[str(key)] = json.dumps(value, ensure_ascii=False, default=str)
        else:
            string_tags[str(key)] = str(value)
    with rasterio.open(
        out_tif,
        "w",
        driver="GTiff",
        height=arr.shape[0],
        width=arr.shape[1],
        count=1,
        dtype=dtype,
        crs=CRS.from_epsg(geometry.epsg),
        transform=geometry.transform,
        nodata=nodata,
        compress="deflate",
        predictor=3,
        tiled=False,
    ) as dst:
        dst.write(arr, 1)
        dst.set_band_description(1, band_description)
        dst.update_tags(**string_tags)
    return {"path": str(out_tif)}


def validate_geotiff(
    out_tif: Path,
    *,
    expected_shape: tuple[int, int],
    expected_epsg: int,
    expected_transform: Any,
    expected_nodata: float = math.nan,
) -> dict[str, Any]:
    """Reopen a written GeoTIFF and check shape, CRS, transform, NoData and tags."""
    errors: list[str] = []
    info: dict[str, Any] = {"path": str(out_tif), "passed": False, "errors": errors}
    if not out_tif.exists():
        errors.append("file does not exist")
        return info
    try:
        with rasterio.open(out_tif) as src:
            info.update(
                {
                    "driver": src.driver,
                    "shape": [src.height, src.width],
                    "count": src.count,
                    "dtypes": list(src.dtypes),
                    "crs": src.crs.to_string() if src.crs else None,
                    "epsg": src.crs.to_epsg() if src.crs else None,
                    "transform": list(src.transform)[:6],
                    "nodata": src.nodata,
                    "band_descriptions": list(src.descriptions),
                    "tags": dict(src.tags()),
                }
            )
            if (src.height, src.width) != tuple(expected_shape):
                errors.append(
                    f"shape {(src.height, src.width)} != expected {tuple(expected_shape)}"
                )
            if src.count != 1:
                errors.append(f"band count {src.count} != 1")
            if src.crs is None or src.crs.to_epsg() != int(expected_epsg):
                errors.append(f"CRS {src.crs} does not match EPSG:{expected_epsg}")
            got = np.asarray(list(src.transform)[:6], dtype=float)
            want = np.asarray(list(expected_transform)[:6], dtype=float)
            if not np.allclose(got, want, rtol=0, atol=1e-6):
                errors.append(f"transform {got.tolist()} != expected {want.tolist()}")
            if src.nodata is None:
                errors.append("NoData value missing")
            elif math.isnan(expected_nodata):
                if not math.isnan(float(src.nodata)):
                    errors.append(f"NoData {src.nodata} != NaN")
            elif not math.isclose(float(src.nodata), float(expected_nodata)):
                errors.append(f"NoData {src.nodata} != {expected_nodata}")
            if not any(src.descriptions):
                errors.append("band description missing")
            window = src.read(1, window=((0, min(64, src.height)), (0, min(64, src.width))))
            if window.size and not np.isfinite(window).any():
                info["note"] = "top-left corner window contains no finite values"
    except Exception as exc:  # pragma: no cover - corrupt file path
        errors.append(f"could not reopen GeoTIFF: {exc}")
    info["passed"] = not errors
    return info


def write_coherence_preview(
    *,
    coherence: np.ndarray,
    valid: np.ndarray,
    out_bin: Path,
    out_meta: Path,
    downsample: int = 4,
) -> dict[str, Any]:
    """Write a compact uint8 coherence preview for client-side threshold masking.

    ``255`` marks invalid pixels; ``0..200`` encode coherence ``/ 200`` in 0..1.
    Invalid values are never mapped to 0 so they cannot be confused with real
    decorrelated water.
    """
    arr = np.asarray(coherence, dtype=np.float64)
    vm = np.asarray(valid, dtype=bool)
    if arr.shape != vm.shape:
        raise RenderingError("Coherence preview received mismatched arrays.")
    scaled = np.clip(np.nan_to_num(arr, nan=0.0), 0.0, 1.0)
    encoded = np.where(vm, np.rint(scaled * 200.0), 255).astype(np.uint8)
    encoded = _downsample(encoded, downsample)
    out_bin.parent.mkdir(parents=True, exist_ok=True)
    out_bin.write_bytes(encoded.tobytes(order="C"))
    meta = {
        "path": str(out_bin),
        "width": int(encoded.shape[1]),
        "height": int(encoded.shape[0]),
        "downsample_factor": downsample,
        "encoding": "uint8; 255=invalid; value/200=coherence",
        "source_shape_rows_cols": [int(arr.shape[0]), int(arr.shape[1])],
    }
    out_meta.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta
