"""Safely locate and optionally download the NISAR Venezuela earthquake GUNW pair.

Target pair: 2026-06-13 (pre-event) -> 2026-06-25 (post-event).
The script does not download unless --download is supplied and the user confirms.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

COLLECTION = "NISAR_L2_GUNW_PROVISIONAL_V1"
TARGET_GRANULE = (
    "NISAR_L2_PR_GUNW_022_162_A_007_023_4000_SH_"
    "20260613T100656_20260613T100731_"
    "20260625T100655_20260625T100730_P05023_N_F_J_001"
)
# A modest bounding box around the Venezuela earthquake zone.
BBOX = (-68.8, 10.1, -68.3, 10.7)  # west, south, east, north
TEMPORAL = ("2026-06-13T00:00:00", "2026-06-26T23:59:59")
OUTDIR = Path("data/raw/nisar_venezuela")


def get_granule_id(granule) -> str:
    """Extract CMR granule identifier robustly from earthaccess result objects."""
    try:
        umm = granule.get("umm", {})
        if isinstance(umm, dict) and umm.get("GranuleUR"):
            return str(umm["GranuleUR"])
    except Exception:
        pass
    try:
        meta = granule.get("meta", {})
        if isinstance(meta, dict) and meta.get("native-id"):
            return str(meta["native-id"])
    except Exception:
        pass
    return str(granule)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--download",
        action="store_true",
        help="download the exact target granule after an interactive confirmation",
    )
    args = parser.parse_args()

    try:
        import earthaccess
    except ImportError:
        print("Missing dependency. Run: python -m pip install earthaccess", file=sys.stderr)
        return 2

    print("NISAR Venezuela earthquake GUNW target")
    print(f"Collection: {COLLECTION}")
    print(f"Granule: {TARGET_GRANULE}")
    print("Acquisition pair: 2026-06-13 -> 2026-06-25 (brackets the 2026-06-24 event)")
    print(f"Output folder: {OUTDIR.resolve()}")

    try:
        results = earthaccess.search_data(
            short_name=COLLECTION,
            bounding_box=BBOX,
            temporal=TEMPORAL,
            count=100,
        )
    except Exception as exc:
        print(f"Search failed: {exc}", file=sys.stderr)
        return 1

    print(f"Search returned {len(results)} candidate granule(s).")
    matches = [g for g in results if get_granule_id(g) == TARGET_GRANULE]

    # Some CMR responses can differ in which name field carries the full ID;
    # fall back to checking the object representation and external links.
    if not matches:
        for granule in results:
            try:
                details = " ".join(granule.data_links(access="external"))
            except Exception:
                details = ""
            if TARGET_GRANULE in str(granule) or TARGET_GRANULE in details:
                matches.append(granule)
                break

    if not matches:
        print("Exact granule was not in the filtered result set.", file=sys.stderr)
        print("No download was attempted. Widen the spatial/time search before retrying.")
        print("Candidate IDs seen:")
        for granule in results[:25]:
            print(" -", get_granule_id(granule))
        return 3

    granule = matches[0]
    try:
        size_mb = granule.size()
        print(f"Estimated granule size: {size_mb:.1f} MB")
    except Exception:
        size_mb = None
        print("Estimated granule size: not reported by CMR")

    try:
        for link in granule.data_links(access="external")[:2]:
            print(f"Data link: {link}")
    except Exception:
        pass

    if not args.download:
        print("\nDRY RUN ONLY. No download occurred.")
        print("After reviewing the size, run with --download to fetch this one granule.")
        return 0

    existing = list(OUTDIR.glob(f"{TARGET_GRANULE}*") ) if OUTDIR.exists() else []
    if existing:
        print("A matching file already exists; refusing to download a duplicate:")
        for path in existing:
            print(f" - {path}")
        return 0

    if size_mb is not None and size_mb > 5000:
        print("This granule is over 5 GB by the reported estimate; refusing automatic download.")
        print("Use the printed link and reassess storage before proceeding.")
        return 4

    confirm = input(f"Type DOWNLOAD to fetch this single granule ({size_mb or 'unknown'} MB): ").strip()
    if confirm != "DOWNLOAD":
        print("Cancelled. No data was downloaded.")
        return 0

    try:
        print("Starting interactive NASA Earthdata Login. Do not share your credentials here.")
        earthaccess.login(strategy="interactive", persist=False)
        OUTDIR.mkdir(parents=True, exist_ok=True)
        files = earthaccess.download([granule], local_path=str(OUTDIR))
        print("Download returned:")
        for file in files or []:
            print(f" - {file}")
        print("Next: inspect the downloaded HDF5 and verify its acquisition metadata.")
    except Exception as exc:
        print(f"Download failed: {exc}", file=sys.stderr)
        print("No claim is made that the granule was downloaded successfully.")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
