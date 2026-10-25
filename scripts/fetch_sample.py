from __future__ import annotations

import argparse
from pathlib import Path
from urllib.request import urlopen

SAMPLE_URL = (
    "https://nisar.asf.earthdatacloud.nasa.gov/NISAR-SAMPLE-DATA/GUNW/"
    "NISAR_L2_PR_GUNW_001_030_A_019_002_2000_SH_20081012T060911_20081012T060925_20081127T061000_20081127T061014_D00404_N_F_J_001/"
    "NISAR_L2_PR_GUNW_001_030_A_019_002_2000_SH_20081012T060911_20081012T060925_20081127T061000_20081127T061014_D00404_N_F_J_001.h5"
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Download NASA's public NISAR-format sample GUNW product.")
    parser.add_argument("--out", type=Path, default=Path("data/demo/sample_gunw.h5"))
    args = parser.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading public NASA sample GUNW to {args.out} ...")
    with urlopen(SAMPLE_URL, timeout=120) as response, args.out.open("wb") as fh:
        while chunk := response.read(1024 * 1024):
            fh.write(chunk)
    print(f"Saved {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
