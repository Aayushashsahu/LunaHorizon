"""Command-line interface for NISAR // Earth in Motion.

Canonical commands (run from the repository root, PowerShell or bash)::

    python -m nisar_eim inspect  "data\\raw\\<granule>.h5"
    python -m nisar_eim validate "data\\raw\\<granule>.h5" --out data\\processed\\<id>
    python -m nisar_eim process  "data\\raw\\<granule>.h5" --id venezuela
    python -m nisar_eim list
    python -m nisar_eim serve --port 8000
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .errors import NisarError
from .pipeline import (
    DEFAULT_OUTPUT_ROOT,
    ProcessConfig,
    inspect_granule,
    process_granule,
    summarize_observation,
    validate_granule,
)
from .product_reader import open_product
from .reporting import write_json


def _fmt(value: Any, digits: int = 3) -> str:
    if value is None:
        return "not available"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:,.{digits}f}"
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


def _print_header(title: str) -> None:
    print()
    print(title)
    print("=" * len(title))


def cmd_inspect(args: argparse.Namespace) -> int:
    result = inspect_granule(args.file, frequency=args.frequency, polarization=args.polarization)
    product = open_product(args.file, frequency=args.frequency, polarization=args.polarization)
    ident = result["identification"]
    geo = result["georeferencing"]
    structure = result["product_structure"]

    _print_header("NISAR // Earth in Motion - product inspection")
    print(f"File            : {result['path']}")
    print(f"Size            : {result['file_size_bytes']:,} bytes")
    print(f"Granule         : {ident.get('granuleId')}")
    print(f"Product         : {ident.get('productType')} v{ident.get('productVersion')} "
          f"(spec {ident.get('productSpecificationVersion')})")
    print(f"Acquisitions    : {product.reference_start} -> {product.secondary_start} "
          f"({product.temporal_baseline_days} day baseline)")
    print(f"Geometry        : track {ident.get('trackNumber')}, frame {ident.get('frameNumber')}, "
          f"{ident.get('orbitPassDirection')} pass, {ident.get('lookDirection')}-looking")
    print(f"Frequency/pol   : {structure['frequency']} / {structure['polarization']} "
          f"({_fmt(result['product_structure']['layers'].get('phase', {}).get('dtype'))} phase)")
    print(f"Centre frequency: {_fmt(product.center_frequency_hz, 0)} Hz -> "
          f"wavelength {_fmt(product.wavelength_m, 6)} m (derived c/f)")

    _print_header("Layers (unwrapped interferogram grid)")
    for key, spec in structure["layers"].items():
        print(f"  {key:26s} {spec['dataset_path']}")
        print(f"  {'':26s} shape={spec['shape_rows_cols']} dtype={spec['dtype']} "
              f"units={spec['units']}")
    print(f"  {'mask':26s} {structure['mask_path'] or 'not present'}")

    _print_header("Georeferencing")
    print(f"CRS             : {geo['crs_name']} (EPSG:{geo['epsg']})")
    print(f"Shape           : {geo['height']} rows x {geo['width']} columns")
    print(f"Posting         : {geo['pixel_spacing']['x']:g} x {geo['pixel_spacing']['y']:g} m "
          f"(axes x {geo['x_axis']}, y {geo['y_axis']})")
    print(f"Convention      : {geo['pixel_convention']}")
    print(f"Method          : {geo['georeferencing_method']}")
    print(f"Coord datasets  : {json.dumps(geo['source_datasets'])}")
    print(f"Round-trip check: max map error {geo['roundtrip_check']['max_map_error']:.3e}, "
          f"max pixel error {geo['roundtrip_check']['max_pixel_error']:.3e}")
    print(f"Product polygon : {geo['product_polygon_check'].get('status')} - "
          f"{geo['product_polygon_check'].get('detail')}")
    footprint = geo["footprint"]
    product_fp = footprint.get("product_bounding_polygon")
    grid_extent = footprint.get("grid_extent") or {}
    if product_fp:
        print(f"Image footprint : {product_fp['wgs84_bounds']} "
              f"({product_fp['area_deg2']:.3f} deg2)")
    print(f"Grid extent     : {grid_extent.get('wgs84_bounds')} "
          f"({grid_extent.get('area_deg2', 0):.3f} deg2)")

    _print_header("Other grids in this granule (each has its own coordinates)")
    for grid in structure["grids"]:
        shapes = ", ".join(
            f"{name} {meta['shape']}" for name, meta in sorted(grid.get("datasets", {}).items())
        ) or "no 2-D datasets"
        print(f"  {grid['name']}: {shapes}")

    if args.json:
        write_json(Path(args.json), result)
        print(f"\nJSON written to {args.json}")
    print(f"\nInspection completed in {result['elapsed_seconds']}s")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    result = validate_granule(
        args.file,
        output_dir=args.out,
        compute_sha256_value=not args.no_sha256,
        frequency=args.frequency,
        polarization=args.polarization,
    )
    _print_header("Validation record")
    print(f"Granule : {result['source']['granule_id']}")
    print(f"Raw file: {result['source']['path']} ({result['raw_file_integrity']['size_bytes']:,} bytes)")
    print(f"SHA-256 : {result['raw_file_integrity']['sha256'] or 'not computed'}")
    print(
        "Raw file unchanged during validation: "
        f"{_fmt(result['raw_file_integrity']['unchanged_during_validation'])}"
    )
    _print_header("Checks")
    for check in result["checks"]:
        print(f"  [{check['status']:>13s}] {check['id']}")
        if check.get("detail"):
            print(f"                   {check['detail']}")
    _print_header("Reference events")
    for event in result["events"]:
        print(
            f"  {event['label']} ({event['id']}, M{event['magnitude']}): "
            f"inside raster bounds = {_fmt(event['inside_raster_bounds'])}"
            + (f", row/col = {event['row_col_fractional']}" if event["row_col_fractional"] else "")
        )
    _print_header("Georeferencing")
    geo = result["georeferencing"]
    print(f"  CRS      : {geo['crs_name']} (EPSG:{geo['epsg']})")
    print(f"  Posting  : {geo['pixel_spacing']['x']:g} x {geo['pixel_spacing']['y']:g} m")
    print(f"  Method   : {geo['georeferencing_method']}")
    print(f"  Bounds   : {json.dumps(geo['bounds'])}")
    footprint = geo["footprint"]
    product_fp = footprint.get("product_bounding_polygon")
    print(f"  Image footprint: {json.dumps((product_fp or footprint.get('grid_extent')).get('wgs84_bounds'))}")
    print(f"  Polygon  : {json.dumps(geo['product_polygon_check'])}")
    if args.out:
        print(f"\nArtifacts written to {args.out}\\validation.json and validation.md")
    print(f"\nValidation completed in {result['elapsed_seconds']}s")
    return 0


def cmd_process(args: argparse.Namespace) -> int:
    config = ProcessConfig(
        default_coherence_threshold=args.threshold,
        render_dpi=args.dpi,
    )
    metadata = process_granule(
        args.file,
        observation_id=args.id,
        output_root=args.out_root,
        config=config,
        force=args.force,
        frequency=args.frequency,
        polarization=args.polarization,
    )
    summary = summarize_observation(metadata)
    _print_header("Processing result")
    print(f"Observation : {summary['observation_id']}")
    print(f"Directory   : {summary['observation_dir']}")
    print(f"Phase units : {summary['phase']['units']}")
    print(
        f"Coverage    : {_fmt(summary['phase']['coverage_percent'], 1)}% of the raster "
        f"({_fmt(summary['phase']['valid_pixels'])} pixels)"
    )
    print(
        f"Phase       : median {_fmt(summary['phase']['median'])} "
        f"{summary['phase']['units']}, p05-p95 {_fmt(summary['phase']['p05'])} ... "
        f"{_fmt(summary['phase']['p95'])}"
    )
    print(
        f"Coherence   : median {_fmt(summary['coherence']['median'])}, "
        f"p05-p95 {_fmt(summary['coherence']['p05'])} ... {_fmt(summary['coherence']['p95'])}"
    )
    print(f"Validation  : {summary['validation'].get('overall_status')}")
    _print_header("Outputs")
    for name, relative in metadata.get("outputs", {}).items():
        path = Path(metadata["observation_dir"]) / relative
        size = path.stat().st_size if path.exists() else 0
        print(f"  {name:24s} {path!s:70s} {size:,} bytes")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    root = Path(args.data_root)
    rows = []
    for metadata_path in sorted(root.glob("*/metadata.json")):
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        summary = summarize_observation(metadata)
        rows.append(summary)
    _print_header(f"Processed observations in {root}")
    if not rows:
        print("  (none - run `python -m nisar_eim process <granule>` first)")
        return 0
    for row in rows:
        print(
            f"  {row['observation_id']:32s} {row.get('reference_start')} -> "
            f"{row.get('secondary_start')}  "
            f"coverage {_fmt(row['phase'].get('coverage_percent'), 1)}%  "
            f"validation {row['validation'].get('overall_status')}"
        )
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    from .webapp.server import run_server

    return run_server(
        host=args.host,
        port=args.port,
        data_root=Path(args.data_root),
        use_reloader=False,
    )


def legacy_quicklook_main(argv: Sequence[str] | None = None) -> int:
    """Compatibility entry point for the pre-refactor ``quicklook_gunw*.py`` scripts.

    The old scripts each re-implemented georeferencing and the v3 variant carried
    the 4x coordinate bug.  They now delegate here so that exactly one grid
    reader and one renderer produce every quicklook.
    """
    parser = argparse.ArgumentParser(
        prog="quicklook_gunw_georef_v3.py",
        description=(
            "DEPRECATED shim: process a NISAR GUNW granule with the canonical "
            "pipeline (`python -m nisar_eim process`). The layer argument is "
            "accepted for compatibility; phase, coherence, GeoTIFFs, metadata "
            "and the report are always produced together."
        ),
    )
    parser.add_argument("file", type=Path)
    parser.add_argument("layer", nargs="?", choices=("phase", "coherence"), default="phase")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="output root directory (default: data/processed)",
    )
    parser.add_argument("--id", default=None, help="observation id")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    print(
        "DEPRECATED: scripts/quicklook_gunw*.py now delegate to the canonical pipeline.\n"
        "Use: python -m nisar_eim process <granule> --id <observation-id>\n"
    )
    metadata = process_granule(
        args.file,
        observation_id=args.id,
        output_root=args.out or DEFAULT_OUTPUT_ROOT,
        force=args.force,
    )
    summary = summarize_observation(metadata)
    print(f"Observation : {summary['observation_id']}")
    print(f"Directory   : {summary['observation_dir']}")
    print(f"Phase units : {summary['phase']['units']} (not displacement)")
    print("Outputs:")
    for name, relative in metadata.get("outputs", {}).items():
        print(f"  {name:24s} {relative}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m nisar_eim",
        description=(
            "NISAR // Earth in Motion - inspect, validate and visualize NISAR L2 GUNW products. "
            "Unwrapped phase is reported in radians with coherence and masks; no phase-to-"
            "displacement conversion is applied."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    inspect = sub.add_parser("inspect", help="metadata-only inspection of a GUNW granule")
    inspect.add_argument("file", type=Path)
    inspect.add_argument("--json", type=Path, default=None, help="also write the inspection JSON here")
    inspect.add_argument("--frequency", default=None, help="frequency letter (default: first available)")
    inspect.add_argument("--polarization", default=None, help="polarization (default: first available)")
    inspect.set_defaults(func=cmd_inspect)

    validate = sub.add_parser("validate", help="validate metadata, georeferencing and footprint")
    validate.add_argument("file", type=Path)
    validate.add_argument("--out", type=Path, default=None, help="write validation.json/report here")
    validate.add_argument("--no-sha256", action="store_true", help="skip the raw-file SHA-256")
    validate.add_argument("--frequency", default=None)
    validate.add_argument("--polarization", default=None)
    validate.set_defaults(func=cmd_validate)

    process = sub.add_parser("process", help="produce quicklooks, GeoTIFFs, metadata and report")
    process.add_argument("file", type=Path)
    process.add_argument("--id", default=None, help="observation id (default derived from metadata)")
    process.add_argument("--out-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    process.add_argument("--force", action="store_true", help="reprocess even if outputs are current")
    process.add_argument("--threshold", type=float, default=0.4, help="default coherence threshold (0-1)")
    process.add_argument("--dpi", type=int, default=150, help="quicklook PNG resolution")
    process.add_argument("--frequency", default=None)
    process.add_argument("--polarization", default=None)
    process.set_defaults(func=cmd_process)

    listing = sub.add_parser("list", help="list processed observations")
    listing.add_argument("--data-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    listing.set_defaults(func=cmd_list)

    serve = sub.add_parser("serve", help="start the local web application")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--data-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    serve.set_defaults(func=cmd_serve)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    # Windows consoles default to a legacy code page; reports may contain
    # non-ASCII characters (arrows, degree signs, en dashes).
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # pragma: no cover - non-standard streams
            pass
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except NisarError as exc:
        print(f"\nERROR: {exc.render()}", file=sys.stderr)
        print(
            "\nThe raw granule was not modified. No output was written for this step.",
            file=sys.stderr,
        )
        return 2
    except KeyboardInterrupt:  # pragma: no cover - interactive
        print("\nInterrupted by user; the raw granule was not modified.", file=sys.stderr)
        return 130
    except Exception as exc:  # unexpected
        print(f"\nUNEXPECTED ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        print(
            "This is not an expected product-format error. Re-run with the same command "
            "and inspect the traceback if it recurs.",
            file=sys.stderr,
        )
        raise


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
