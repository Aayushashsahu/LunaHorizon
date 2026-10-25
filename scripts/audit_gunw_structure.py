"""Metadata-only structural audit of a NISAR GUNW HDF5 product.

Never reads full raster bodies; only dataset metadata (shape, dtype, attrs) plus
optionally a tiny corner sample when --samples is passed.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import h5py
import numpy as np


def fmt(value: object, limit: int = 240) -> str:
    if isinstance(value, (bytes, np.bytes_)):
        text = value.decode("utf-8", errors="replace").strip("\x00 ")
    elif isinstance(value, np.ndarray):
        if value.size > 12:
            text = np.array2string(value.ravel()[:12], threshold=12) + f" ... (size={value.size})"
        else:
            text = np.array2string(value)
    else:
        text = str(value)
    text = " ".join(text.split())
    return text[:limit] + ("..." if len(text) > limit else "")


def dump(path: Path, samples: bool, out: Path | None) -> None:
    lines: list[str] = []

    def emit(line: str = "") -> None:
        lines.append(line)

    with h5py.File(path, "r") as h5:
        emit(f"FILE: {path}")
        emit(f"SIZE: {path.stat().st_size:,} bytes")
        emit("")
        emit("=== ROOT / FILE-LEVEL ATTRIBUTES ===")
        for k, v in h5.attrs.items():
            emit(f"  @{k} = {fmt(v)}")
        emit("")
        emit("=== STRUCTURE ===")

        def visitor(name: str, obj: h5py.Dataset | h5py.Group) -> None:
            depth = name.count("/")
            pad = "  " * depth
            if isinstance(obj, h5py.Dataset):
                emit(
                    f"{pad}{name.rsplit('/', 1)[-1]}  DATASET shape={obj.shape} "
                    f"dtype={obj.dtype} chunks={obj.chunks} compression={obj.compression}"
                )
                for k, v in obj.attrs.items():
                    emit(f"{pad}    @{k} = {fmt(v)}")
                if samples and obj.ndim >= 1 and obj.size and obj.dtype != object:
                    try:
                        idx = tuple(slice(0, min(4, d)) for d in obj.shape)
                        arr = np.asarray(obj[idx])
                        emit(f"{pad}    sample[0:4,...] = {fmt(arr, 400)}")
                    except Exception as exc:  # pragma: no cover - diagnostics only
                        emit(f"{pad}    sample failed: {exc}")
            else:
                emit(f"{pad}{name.rsplit('/', 1)[-1]}/  GROUP")
                for k, v in obj.attrs.items():
                    emit(f"{pad}    @{k} = {fmt(v)}")

        h5.visititems(visitor)

    text = "\n".join(lines)
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(f"wrote {out} ({len(lines)} lines)")
    else:
        print(text)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("file", type=Path)
    ap.add_argument("--samples", action="store_true", help="also print tiny corner samples")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    if not args.file.exists():
        print(f"not found: {args.file}", file=sys.stderr)
        return 2
    dump(args.file, args.samples, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
