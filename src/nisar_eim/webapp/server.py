"""Local web application: dashboard and observation explorer.

Only the Python standard library is used for serving.  Scientific values come
from the processed observation directory written by ``python -m nisar_eim
process``; pixel inspection reads small windows from the local HDF5 granule.

The server is offline-first: no map tiles, CDNs or third-party services are
required to display or inspect the data.
"""

from __future__ import annotations

import json
import mimetypes
import posixpath
import re
import sys
import traceback
from collections.abc import Mapping
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

import h5py
import numpy as np

from .. import __version__
from ..errors import NisarError
from ..geospatial import GridGeometry
from ..quality import decode_mask
from ..statistics import window_summary

STATIC_DIR = Path(__file__).resolve().parent / "static"
SAFE_ID = re.compile(r"^[A-Za-z0-9._-]+$")

LAYER_DESCRIPTIONS = {
    "phase": {
        "title": "Unwrapped interferometric phase",
        "units": "radians (declared by the product)",
        "meaning": (
            "The phase difference between the two radar acquisitions, after "
            "ellipsoid and topographic flattening and after phase unwrapping. "
            "It records a change in the range between the radar and the ground, "
            "but its absolute level is arbitrary and it mixes surface motion with "
            "atmospheric, ionospheric and orbital effects."
        ),
        "not_this": "It is not a displacement map in metres, and not a vertical-motion map.",
    },
    "coherence": {
        "title": "Interferometric coherence magnitude",
        "units": "dimensionless, typically 0–1",
        "meaning": (
            "How similar the two radar observations are within each resolution "
            "cell. High coherence generally means the interferometric phase is "
            "usable; low coherence means it is dominated by noise."
        ),
        "not_this": "It is a quality indicator, not a measurement of ground movement.",
    },
    "quality": {
        "title": "Validity and water classification",
        "units": "classes",
        "meaning": (
            "Derived from the product mask: valid land, valid water, and pixels "
            "excluded because a subswath digit is zero or the mask is fill."
        ),
        "not_this": "Valid does not mean 'useful for deformation'; check coherence.",
    },
    "connected_components": {
        "title": "Connected components",
        "units": "label",
        "meaning": (
            "Regions that were unwrapped together. Different labels can carry "
            "different integer phase ambiguities, so phase is not necessarily "
            "continuous across a label boundary."
        ),
        "not_this": "A component boundary is not a fault or a physical boundary.",
    },
}


class ObservationNotFound(NisarError):
    pass


class ObservationRepository:
    """Read processed observation bundles from ``data/processed``."""

    def __init__(self, data_root: str | Path) -> None:
        self.data_root = Path(data_root)

    # -- discovery --------------------------------------------------------
    def ids(self) -> list[str]:
        if not self.data_root.exists():
            return []
        return sorted(
            path.parent.name
            for path in self.data_root.glob("*/metadata.json")
            if SAFE_ID.match(path.parent.name)
        )

    def load(self, observation_id: str) -> dict[str, Any]:
        if not SAFE_ID.match(observation_id):
            raise ObservationNotFound("Invalid observation id.")
        path = self.data_root / observation_id / "metadata.json"
        if not path.exists():
            raise ObservationNotFound(
                f"Observation '{observation_id}' has not been processed.",
                details={"expected_metadata": str(path)},
            )
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise ObservationNotFound(
                f"Observation '{observation_id}' metadata could not be read: {exc}"
            ) from exc

    def directory(self, observation_id: str) -> Path:
        return self.data_root / observation_id

    def summaries(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for observation_id in self.ids():
            try:
                metadata = self.load(observation_id)
            except NisarError:
                continue
            out.append(_summary(metadata))
        return out

    # -- artifacts --------------------------------------------------------
    def artifact(self, observation_id: str, name: str) -> Path:
        metadata = self.load(observation_id)
        directory = self.directory(observation_id)
        allowed = set(metadata.get("outputs", {}).values()) | {
            "metadata.json",
            "report.md",
            "validation.json",
            str((metadata.get("map_view", {}).get("coherence_preview") or {}).get("path", "")),
            str((metadata.get("map_view", {}).get("coherence_preview") or {}).get("metadata_path", "")),
        }
        for image in (metadata.get("map_view", {}).get("images") or {}).values():
            allowed.add(str(image.get("path")))
        clean = posixpath.normpath(name.replace("\\", "/"))
        if clean.startswith("..") or clean not in allowed:
            raise ObservationNotFound(
                f"Artifact '{name}' is not part of this observation.",
                details={"allowed": sorted(a for a in allowed if a)},
            )
        path = (directory / clean).resolve()
        if not str(path).startswith(str(directory.resolve())):
            raise ObservationNotFound("Artifact path escapes the observation directory.")
        if not path.exists():
            raise ObservationNotFound(f"Artifact '{name}' is missing on disk.")
        return path

    # -- analysis ---------------------------------------------------------
    def threshold(self, observation_id: str, threshold: float) -> dict[str, Any]:
        metadata = self.load(observation_id)
        table = metadata.get("quality", {}).get("threshold_table", [])
        if not table:
            raise NisarError("This observation has no coherence threshold table.")
        value = max(0.0, min(1.0, float(threshold)))
        rows = sorted(table, key=lambda row: row["threshold"])
        lower = rows[0]
        upper = rows[-1]
        for row in rows:
            if row["threshold"] <= value:
                lower = row
            if row["threshold"] >= value:
                upper = row
                break
        if upper["threshold"] == lower["threshold"]:
            weight = 0.0
        else:
            weight = (value - lower["threshold"]) / (upper["threshold"] - lower["threshold"])
        valid_pixels = _lerp(lower.get("valid_pixels"), upper.get("valid_pixels"), weight)
        coverage = _lerp(lower.get("coverage_percent"), upper.get("coverage_percent"), weight)
        return {
            "threshold": round(value, 3),
            "interpolated": not any(abs(row["threshold"] - value) < 1e-9 for row in rows),
            "valid_pixels": round(valid_pixels) if valid_pixels is not None else None,
            "coverage_percent": round(coverage, 3) if coverage is not None else None,
            "phase_median": upper.get("phase_median") if weight > 0.5 else lower.get("phase_median"),
            "coherence_median": (
                upper.get("coherence_median") if weight > 0.5 else lower.get("coherence_median")
            ),
            "table": table,
            "note": (
                "Coverage is interpolated from the exact threshold table computed over "
                "the full-resolution valid pixels. The coherence threshold is an "
                "exploratory filter, not a product definition."
            ),
        }

    def sample(
        self,
        observation_id: str,
        *,
        row: int | None = None,
        col: int | None = None,
        lon: float | None = None,
        lat: float | None = None,
        half: int = 2,
    ) -> dict[str, Any]:
        metadata = self.load(observation_id)
        geometry = GridGeometry.from_json(metadata["map_view"]["geometry"])
        if lon is not None and lat is not None:
            row_f, col_f = geometry.rowcol_of_lonlat(float(lon), float(lat))
            if not (0 <= row_f <= geometry.height - 1 and 0 <= col_f <= geometry.width - 1):
                raise NisarError(
                    "Coordinate lies outside this observation's grid.",
                    details={
                        "lon": lon,
                        "lat": lat,
                        "row": row_f,
                        "col": col_f,
                        "grid_shape": [geometry.height, geometry.width],
                    },
                )
            row_i = round(row_f)
            col_i = round(col_f)
        elif row is not None and col is not None:
            row_i = int(row)
            col_i = int(col)
            if not (0 <= row_i < geometry.height and 0 <= col_i < geometry.width):
                raise NisarError(
                    "Pixel index lies outside this observation's grid.",
                    details={"row": row_i, "col": col_i},
                )
            row_f, col_f = float(row_i), float(col_i)
        else:
            raise NisarError("Provide either lon/lat or row/col for pixel inspection.")

        source = Path(metadata.get("source", {}).get("path", ""))
        if not source.exists():
            raise NisarError(
                "The raw granule is not available, so full-resolution pixel inspection "
                "is disabled. The processed quicklooks and statistics still work offline.",
                details={"source_path": str(source)},
            )

        layers = metadata.get("product_structure", {}).get("layers", {})
        phase_path = layers.get("phase", {}).get("dataset_path")
        coherence_path = layers.get("coherence", {}).get("dataset_path")
        cc_path = layers.get("connected_components", {}).get("dataset_path")
        mask_path = metadata.get("product_structure", {}).get("mask_path")
        if not phase_path or not coherence_path:
            raise NisarError("Processed metadata does not describe the phase/coherence layers.")

        r0 = max(0, row_i - half)
        r1 = min(geometry.height, row_i + half + 1)
        c0 = max(0, col_i - half)
        c1 = min(geometry.width, col_i + half + 1)
        with h5py.File(source, "r") as h5:
            phase_window = np.asarray(h5[phase_path][r0:r1, c0:c1], dtype=np.float32)
            coherence_window = np.asarray(h5[coherence_path][r0:r1, c0:c1], dtype=np.float32)
            components_window = (
                np.asarray(h5[cc_path][r0:r1, c0:c1]) if cc_path else None
            )
            mask_window = np.asarray(h5[mask_path][r0:r1, c0:c1]) if mask_path else None
            fill = h5[mask_path].attrs.get("_FillValue", 255) if mask_path else 255
            description = str(h5[mask_path].attrs.get("description", "")) if mask_path else ""

        mask_fields = (
            decode_mask(mask_window, fill_value=fill, description=description)
            if mask_window is not None
            else None
        )
        valid_window = np.isfinite(phase_window)
        if mask_fields is not None:
            valid_window &= mask_fields.valid
        summary = window_summary(
            phase_window,
            coherence_window,
            valid_window,
            name=f"{r1 - r0}x{c1 - c0} pixel window",
        )

        centre_valid = bool(valid_window[row_i - r0, col_i - c0])
        lon_c, lat_c = geometry.lonlat_of(row_i, col_i)
        mask_out: dict[str, Any] = {"available": mask_fields is not None}
        if mask_fields is not None:
            idx = (row_i - r0, col_i - c0)
            mask_out.update(
                {
                    "valid": bool(mask_fields.valid[idx]),
                    "water": bool(mask_fields.water[idx]),
                    "reference_subswath": int(mask_fields.reference_subswath[idx]),
                    "secondary_subswath": int(mask_fields.secondary_subswath[idx]),
                    "reference_anomaly": int(mask_fields.reference_anomaly[idx]),
                    "secondary_anomaly": int(mask_fields.secondary_anomaly[idx]),
                    "ionosphere_filled": bool(mask_fields.ionosphere_filled[idx]),
                    "encoding": mask_fields.encoding,
                }
            )
        return {
            "observation_id": observation_id,
            "row": row_i,
            "col": col_i,
            "row_fractional": row_f,
            "col_fractional": col_f,
            "lon": lon_c,
            "lat": lat_c,
            "easting": geometry.pixel_centre(row_i, col_i)[0],
            "northing": geometry.pixel_centre(row_i, col_i)[1],
            "epsg": geometry.epsg,
            "phase_radians": _clean(phase_window[row_i - r0, col_i - c0]),
            "coherence": _clean(coherence_window[row_i - r0, col_i - c0]),
            "connected_component": (
                int(components_window[row_i - r0, col_i - c0])
                if components_window is not None
                else None
            ),
            "valid": centre_valid,
            "mask": mask_out,
            "window": summary,
            "units": {"phase": "radians", "coherence": "1"},
            "note": (
                "Phase is reported in radians. It is not converted to displacement and "
                "cannot be read as vertical motion."
            ),
        }


class Application:
    """Pure application layer, independent of HTTP (used directly by tests)."""

    def __init__(self, data_root: str | Path) -> None:
        self.repository = ObservationRepository(data_root)
        self.limitations: list[str] = []

    def index(self) -> dict[str, Any]:
        observations = self.repository.summaries()
        reference_events: list[dict[str, Any]] = []
        limitations: list[str] = []
        for observation in observations:
            metadata = self.repository.load(observation["observation_id"])
            assessment = metadata.get("event_assessment", {})
            if not reference_events:
                for item in assessment.get("events", []):
                    reference_events.append(item.get("event", {}))
            for limitation in metadata.get("limitations", []):
                if limitation not in limitations:
                    limitations.append(limitation)
        return {
            "app": {
                "name": "NISAR // Earth in Motion",
                "tagline": "See how Earth changes. Understand what the radar reveals.",
                "version": __version__,
                "offline": True,
                "disclaimer": (
                    "Unwrapped phase is shown in radians with coherence and masks. "
                    "No phase-to-displacement conversion is applied and no earthquake "
                    "causation is claimed."
                ),
            },
            "observations": observations,
            "reference_events": reference_events,
            "limitations": limitations,
            "layer_descriptions": LAYER_DESCRIPTIONS,
            "palette": _palette(observations),
        }

    def observation(self, observation_id: str) -> dict[str, Any]:
        metadata = self.repository.load(observation_id)
        assets = {}
        for name, relative in (metadata.get("outputs") or {}).items():
            assets[name] = {
                "path": relative,
                "url": f"/api/observations/{observation_id}/artifact/{relative}",
            }
        preview = metadata.get("map_view", {})
        images = {}
        for key, image in (preview.get("images") or {}).items():
            images[key] = {
                "url": f"/api/observations/{observation_id}/artifact/{image.get('path')}",
                "width": image.get("width"),
                "height": image.get("height"),
            }
        coherence_preview = preview.get("coherence_preview") or {}
        payload = {
            "observation": _summary(metadata),
            "metadata": metadata,
            "assets": assets,
            "map": {
                "images": images,
                "display_grid": preview.get("display_grid"),
                "coherence_preview": (
                    {
                        "url": (
                            f"/api/observations/{observation_id}/preview/coherence.bin"
                        ),
                        "width": coherence_preview.get("width"),
                        "height": coherence_preview.get("height"),
                        "encoding": coherence_preview.get("encoding"),
                    }
                    if coherence_preview
                    else None
                ),
            },
            "layer_descriptions": LAYER_DESCRIPTIONS,
            "threshold": self.repository.threshold(
                observation_id,
                float(metadata.get("quality", {}).get("default_coherence_threshold") or 0.4),
            ),
        }
        return payload

    def threshold(self, observation_id: str, threshold: float) -> dict[str, Any]:
        return self.repository.threshold(observation_id, threshold)

    def sample(self, observation_id: str, **kwargs: Any) -> dict[str, Any]:
        return self.repository.sample(observation_id, **kwargs)

    def artifact(self, observation_id: str, name: str) -> Path:
        return self.repository.artifact(observation_id, name)


def _summary(metadata: Mapping[str, Any]) -> dict[str, Any]:
    from ..pipeline import summarize_observation

    summary = summarize_observation(metadata)
    source = metadata.get("source", {})
    summary["validation_states"] = metadata.get("validation", {}).get("states", [])
    summary["checks"] = metadata.get("checks", [])
    summary["warnings"] = metadata.get("warnings", [])
    summary["limitations"] = metadata.get("limitations", [])
    summary["georeferencing"] = {
        key: metadata.get("georeferencing", {}).get(key)
        for key in ("crs_name", "epsg", "pixel_spacing", "crs", "footprint")
    }
    summary["footprint"] = (metadata.get("georeferencing", {}) or {}).get("footprint")
    summary["event_assessment"] = metadata.get("event_assessment", {})
    summary["layer_paths"] = {
        key: spec.get("dataset_path")
        for key, spec in (metadata.get("product_structure", {}).get("layers") or {}).items()
    }
    summary["source"] = {
        key: source.get(key)
        for key in (
            "file_name",
            "file_size_bytes",
            "product_version",
            "product_specification_version",
            "product_doi",
            "processing_datetime",
            "is_pre_launch_sample",
            "granule_id",
            "path",
        )
    }
    summary["threshold_table"] = metadata.get("quality", {}).get("threshold_table", [])
    summary["default_coherence_threshold"] = metadata.get("quality", {}).get(
        "default_coherence_threshold"
    )
    summary["connected_components"] = metadata.get("layers", {}).get("connected_components")
    summary["mask"] = metadata.get("layers", {}).get("mask")
    return summary


def _palette(observations: list[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "phase": {
            "colormap": "viridis",
            "legend": "Unwrapped phase (radians)",
            "note": "sequential, no implied zero",
        },
        "coherence": {
            "colormap": "cividis",
            "legend": "Coherence magnitude (0–1)",
        },
        "quality": {
            "classes": [
                {"label": "Valid land", "color": "#38b2ac"},
                {"label": "Valid water", "color": "#4285f4"},
                {"label": "Invalid", "color": "transparent"},
            ]
        },
    }


def _lerp(a: Any, b: Any, weight: float) -> float | None:
    if a is None or b is None:
        return None
    return float(a) + (float(b) - float(a)) * float(weight)


def _clean(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if np.isfinite(out) else None


class Handler(BaseHTTPRequestHandler):
    server_version = f"nisar-eim/{__version__}"
    app: Application
    static_dir: Path = STATIC_DIR

    def log_message(self, fmt: str, *args: Any) -> None:
        if self.path.startswith("/static/"):
            return
        sys.stderr.write(f"[web] {self.address_string()} {self.command} {self.path} - {fmt % args}\n")

    # -- helpers ----------------------------------------------------------
    def _send_json(self, payload: Any, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_error_json(self, status: int, message: str, details: Any = None) -> None:
        self._send_json({"error": message, "details": details}, status=status)

    def _send_file(self, path: Path) -> None:
        mime, _ = mimetypes.guess_type(str(path))
        body = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mime or "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def _send_bytes(self, body: bytes, content_type: str) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    # -- routing ----------------------------------------------------------
    def do_GET(self) -> None:
        try:
            self._route()
        except ObservationNotFound as exc:
            self._send_error_json(404, exc.message, exc.details)
        except NisarError as exc:
            self._send_error_json(400, exc.message, exc.details)
        except BrokenPipeError:  # pragma: no cover - client disconnected
            pass
        except Exception as exc:  # unexpected
            traceback.print_exc()
            self._send_error_json(500, f"Internal error: {type(exc).__name__}: {exc}")

    def _route(self) -> None:
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        query = parse_qs(parsed.query)

        if path in ("/", "/index.html"):
            return self._send_file(self.static_dir / "index.html")
        if path.startswith("/static/"):
            relative = path[len("/static/") :]
            clean = posixpath.normpath(relative)
            if clean.startswith(("..", "/")):
                return self._send_error_json(404, "Not found")
            target = (self.static_dir / clean).resolve()
            if not str(target).startswith(str(self.static_dir.resolve())) or not target.exists():
                return self._send_error_json(404, "Static file not found", {"path": relative})
            return self._send_file(target)

        if path == "/api/index":
            return self._send_json(self.app.index())
        if path == "/api/health":
            return self._send_json({"status": "ok", "version": __version__})

        parts = [part for part in path.split("/") if part]
        if len(parts) >= 3 and parts[0] == "api" and parts[1] == "observations":
            observation_id = parts[2]
            if len(parts) == 3:
                return self._send_json(self.app.observation(observation_id))
            if len(parts) == 4 and parts[3] == "sample":
                row = _float_param(query, "row")
                col = _float_param(query, "col")
                lon = _float_param(query, "lon")
                lat = _float_param(query, "lat")
                half = int(_float_param(query, "half") or 2)
                return self._send_json(
                    self.app.sample(
                        observation_id,
                        row=int(row) if row is not None else None,
                        col=int(col) if col is not None else None,
                        lon=lon,
                        lat=lat,
                        half=max(1, min(half, 8)),
                    )
                )
            if len(parts) == 4 and parts[3] == "threshold":
                value = _float_param(query, "value")
                if value is None:
                    return self._send_error_json(400, "Missing 'value' parameter")
                return self._send_json(self.app.threshold(observation_id, value))
            if len(parts) == 5 and parts[3] == "artifact":
                return self._send_file(self.app.artifact(observation_id, parts[4]))
            if len(parts) == 5 and parts[3] == "preview" and parts[4] == "coherence.bin":
                metadata = self.app.repository.load(observation_id)
                preview = (metadata.get("map_view", {}) or {}).get("coherence_preview") or {}
                relative = preview.get("path")
                if not relative:
                    return self._send_error_json(404, "No coherence preview for this observation")
                path_bin = self.app.artifact(observation_id, relative)
                return self._send_bytes(path_bin.read_bytes(), "application/octet-stream")
            # artifacts with nested paths: /artifact/preview/map_phase.png
            if len(parts) > 5 and parts[3] == "artifact":
                name = "/".join(parts[4:])
                return self._send_file(self.app.artifact(observation_id, name))

        return self._send_error_json(404, "Not found", {"path": path})


def _float_param(query: Mapping[str, list[str]], key: str) -> float | None:
    values = query.get(key)
    if not values:
        return None
    try:
        return float(values[0])
    except ValueError as exc:
        raise NisarError(f"Query parameter '{key}' must be numeric.") from exc


def create_server(
    host: str = "127.0.0.1", port: int = 8000, data_root: str | Path = "data/processed"
) -> ThreadingHTTPServer:
    """Create (but do not start) the HTTP server."""
    app = Application(data_root)
    handler = type(
        "BoundHandler",
        (Handler,),
        {"app": app, "static_dir": STATIC_DIR},
    )
    server = ThreadingHTTPServer((host, port), handler)
    server.daemon_threads = True
    return server


def run_server(
    host: str = "127.0.0.1",
    port: int = 8000,
    data_root: str | Path = "data/processed",
    use_reloader: bool = False,
) -> int:
    """Run the application until interrupted."""
    static_index = STATIC_DIR / "index.html"
    if not static_index.exists():
        print(f"ERROR: static assets missing at {STATIC_DIR}", file=sys.stderr)
        return 2
    server = create_server(host, port, data_root)
    actual_port = server.server_address[1]
    observations = Application(data_root).repository.ids()
    print()
    print("  NISAR // Earth in Motion")
    print(f"  Local application: http://{host}:{actual_port}/")
    print(f"  Data root        : {Path(data_root).resolve()}")
    print(f"  Observations     : {len(observations)}"
          + (f" ({', '.join(observations)})" if observations else ""))
    if not observations:
        print("  NOTE: no processed observations yet — run `python -m nisar_eim process <granule>`.")
    print("  Press Ctrl+C to stop.")
    print()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
    finally:
        server.server_close()
    return 0
