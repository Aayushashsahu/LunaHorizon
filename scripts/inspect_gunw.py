from __future__ import annotations

import argparse
from pathlib import Path

import h5py


def walk(name: str, obj: h5py.Dataset | h5py.Group) -> None:
    if isinstance(obj, h5py.Dataset):
        shape = "x".join(map(str, obj.shape)) if obj.shape else "scalar"
        dtype = str(obj.dtype)
        print(f"DATASET  {name}  shape={shape}  dtype={dtype}")
    else:
        print(f"GROUP    {name}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect the HDF5 tree of a NISAR GUNW product.")
    parser.add_argument("file", type=Path)
    args = parser.parse_args()
    if not args.file.exists():
        parser.error(f"File not found: {args.file}")
    if args.file.suffix.lower() not in {".h5", ".hdf5"}:
        parser.error("Expected an HDF5 file (.h5/.hdf5)")

    with h5py.File(args.file, "r") as f:
        print(f"FILE: {args.file}")
        print("ROOT ATTRIBUTES:")
        for key, value in f.attrs.items():
            print(f"  {key}: {value}")
        print("\nHDF5 TREE:")
        f.visititems(walk)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
