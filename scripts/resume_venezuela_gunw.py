"""Resume an interrupted NISAR GUNW download using HTTP Range requests.

Run from the project root in the activated venv:
    python scripts\\resume_venezuela_gunw.py

The script never appends data unless the server confirms HTTP 206 and the exact
Content-Range start byte. If Range is unsupported or authentication fails, it
stops without altering the partial file.
"""
from __future__ import annotations

import re
import time
from pathlib import Path

import earthaccess

URL = (
    "https://nisar.asf.earthdatacloud.nasa.gov/NISAR/NISAR_L2_GUNW_PROVISIONAL_V1/"
    "NISAR_L2_PR_GUNW_022_162_A_007_023_4000_SH_20260613T100656_20260613T100731_"
    "20260625T100655_20260625T100730_P05023_N_F_J_001/"
    "NISAR_L2_PR_GUNW_022_162_A_007_023_4000_SH_20260613T100656_20260613T100731_"
    "20260625T100655_20260625T100730_P05023_N_F_J_001.h5"
)
OUTDIR = Path("data/raw/nisar_venezuela")
FINAL_NAME = URL.rsplit("/", 1)[-1]


def main() -> int:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    partials = sorted(p for p in OUTDIR.glob("partial_*") if p.is_file())
    final = OUTDIR / FINAL_NAME

    if final.exists():
        print(f"A file already exists at {final} ({final.stat().st_size:,} bytes).")
        print("Not overwriting it. Verify the file before continuing.")
        return 2
    if len(partials) != 1:
        print(f"Expected exactly one partial_* file in {OUTDIR}; found {len(partials)}.")
        for p in partials:
            print(f"  {p.name}: {p.stat().st_size:,} bytes")
        print("Do not delete anything yet; inspect the folder and resolve ambiguity first.")
        return 2

    partial = partials[0]
    offset = partial.stat().st_size
    if offset <= 0:
        print(f"Partial file is empty: {partial}")
        return 2

    print("Interrupted NISAR download recovery")
    print(f"Partial file: {partial}")
    print(f"Already downloaded: {offset:,} bytes ({offset / (1024**3):.3f} GiB)")
    print("Logging in to NASA Earthdata. Type credentials only into this terminal prompt.")
    earthaccess.login(strategy="interactive")
    session = earthaccess.get_requests_session()

    headers = {"Range": f"bytes={offset}-", "Accept-Encoding": "identity"}
    print("Checking whether the server supports resuming at the existing byte offset...")
    response = session.get(URL, headers=headers, stream=True, allow_redirects=True, timeout=(30, 90))

    if response.status_code == 416:
        cr = response.headers.get("Content-Range", "")
        response.close()
        match = re.fullmatch(r"bytes \*/(\d+)", cr.strip())
        if match and int(match.group(1)) == offset:
            print("Server reports the partial file already equals the advertised total size.")
            partial.replace(final)
            print(f"Renamed to {final}; validate the HDF5 file before using it.")
            return 0
        print(f"Server refused the range (HTTP 416, Content-Range={cr!r}). No file changed.")
        return 3

    if response.status_code != 206:
        status = response.status_code
        content_range = response.headers.get("Content-Range")
        response.close()
        print(f"Server did not confirm a resumable range (HTTP {status}, Content-Range={content_range!r}).")
        print("No bytes were appended. The partial file was left untouched.")
        return 3

    content_range = response.headers.get("Content-Range", "")
    match = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+)", content_range.strip())
    if not match or int(match.group(1)) != offset:
        response.close()
        print(f"Unexpected Content-Range: {content_range!r}. No bytes were appended.")
        return 3

    start, end, total = map(int, match.groups())
    if end < start or total <= end:
        response.close()
        print(f"Invalid Content-Range: {content_range!r}. No bytes were appended.")
        return 3

    print(f"Range accepted. Total expected: {total:,} bytes ({total / (1024**3):.3f} GiB).")
    print("Resuming now. Keep this terminal open; Ctrl+C can interrupt again and this script can be rerun.")
    downloaded = offset
    last_print = time.monotonic()
    try:
        with partial.open("ab") as out:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if not chunk:
                    continue
                out.write(chunk)
                downloaded += len(chunk)
                now = time.monotonic()
                if now - last_print >= 3:
                    print(f"\r{downloaded:,} / {total:,} bytes ({downloaded / total:.1%})", end="", flush=True)
                    last_print = now
    except KeyboardInterrupt:
        print("\nInterrupted. The partial file has been kept; rerun this script to resume.")
        return 130
    finally:
        response.close()

    print(f"\r{partial.stat().st_size:,} / {total:,} bytes (100.0%)")
    actual = partial.stat().st_size
    if actual != total:
        print(f"Server stream ended before total size: file has {actual:,}, expected {total:,} bytes.")
        print("Keep the partial file and rerun this script to attempt resumption.")
        return 4

    partial.replace(final)
    print(f"Download complete: {final}")
    print("Next: validate it with h5py before processing the dataset.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
