"""Search public NISAR GUNW granules over the June 2026 Venezuela earthquakes.

This script only searches and reports metadata. It does NOT download large files.
Requires the project's environment with `earthaccess` installed.
"""
from __future__ import annotations

import argparse
from collections.abc import Mapping
from typing import Any

COLLECTION = "NISAR_L2_GUNW_PROVISIONAL_V1"
# Approximate epicentral / affected region point, in longitude, latitude.
VENEZUELA_POINT = (-68.60, 10.30)
START = "2026-06-01"
END = "2026-08-31"


def get_path(obj: Any, *keys: str) -> Any:
    """Read nested mappings or Earthaccess model objects defensively."""
    cur = obj
    for key in keys:
        if cur is None:
            return None
        try:
            if isinstance(cur, Mapping):
                cur = cur.get(key)
            else:
                cur = cur[key]
            continue
        except Exception:
            pass
        try:
            cur = getattr(cur, key)
        except Exception:
            return None
    return cur


def clean(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace").strip("\x00")
    return str(value).replace("\n", " ").strip()


def granule_metadata(granule: Any) -> tuple[str, str, str, str]:
    umm = get_path(granule, "umm")
    if umm is None:
        try:
            umm = granule["umm"]
        except Exception:
            umm = {}

    granule_id = (
        get_path(umm, "GranuleUR")
        or get_path(umm, "GranuleId")
        or get_path(granule, "meta", "native-id")
        or str(granule)
    )
    temporal = get_path(umm, "TemporalExtent", "RangeDateTime") or {}
    start = get_path(temporal, "BeginningDateTime")
    end = get_path(temporal, "EndingDateTime")
    title = get_path(umm, "AdditionalAttributes")
    title_str = ""
    if title:
        title_str = "; ".join(
            f"{clean(get_path(item, 'Name'))}={clean(get_path(item, 'Values'))}"
            for item in title[:4]
        )
    return clean(granule_id), clean(start), clean(end), title_str


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-results", type=int, default=100)
    parser.add_argument("--start", default=START, help="Search start date (YYYY-MM-DD)")
    parser.add_argument("--end", default=END, help="Search end date (YYYY-MM-DD)")
    args = parser.parse_args()

    try:
        import earthaccess
    except ImportError:
        print("Missing dependency. Activate .venv and run: python -m pip install earthaccess")
        return 2

    print("NISAR GUNW search — Venezuela earthquake region")
    print(f"Collection: {COLLECTION}")
    print(f"Search point (lon, lat): {VENEZUELA_POINT}")
    print(f"Time window: {args.start} to {args.end}")
    print("Mode: metadata search only; no downloads will start.\n")

    try:
        results = earthaccess.search_data(
            short_name=COLLECTION,
            point=VENEZUELA_POINT,
            temporal=(args.start, args.end),
            count=args.max_results,
        )
    except Exception as exc:
        print(f"Earthaccess search failed: {type(exc).__name__}: {exc}")
        print("Check network access and try again. This search does not require downloading data.")
        return 1

    print(f"Returned {len(results)} candidate granule(s).\n")
    if not results:
        print("No matches in this collection/window/point filter. Next steps: widen the")
        print("time window or search the NASA Disasters portal's event-specific links.")
        return 0

    for index, granule in enumerate(results):
        granule_id, begin, end, attrs = granule_metadata(granule)
        print(f"[{index}] {granule_id}")
        print(f"    CMR temporal extent: {begin} → {end}")
        if attrs:
            print(f"    Extra attributes: {attrs}")
        try:
            links = granule.data_links(access="external")
            if links:
                print(f"    External data links: {len(links)}")
                print(f"    First link: {links[0]}")
        except Exception:
            pass
        print()

    print("IMPORTANT: these are candidates only. Confirm the granule name includes")
    print("the intended reference/secondary acquisitions and check its spatial footprint")
    print("before downloading. This script deliberately never downloads automatically.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
