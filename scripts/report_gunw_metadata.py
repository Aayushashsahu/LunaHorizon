from pathlib import Path

import h5py
import numpy as np

FILE = Path("data/demo/sample_gunw.h5")

IDENTIFICATION = [
    "granuleId",
    "productType",
    "productLevel",
    "productVersion",
    "radarBand",
    "lookDirection",
    "orbitPassDirection",
    "referenceZeroDopplerStartTime",
    "referenceZeroDopplerEndTime",
    "secondaryZeroDopplerStartTime",
    "secondaryZeroDopplerEndTime",
]

RASTERS = [
    ("science/LSAR/GUNW/grids/frequencyA/"
    "unwrappedInterferogram/HH/unwrappedPhase"),
    ("science/LSAR/GUNW/grids/frequencyA/"
    "unwrappedInterferogram/HH/coherenceMagnitude"),
    ("science/LSAR/GUNW/grids/frequencyA/"
    "unwrappedInterferogram/mask"),
    ("science/LSAR/GUNW/grids/frequencyA/"
    "unwrappedInterferogram/HH/connectedComponents"),
]

def display(value):
    if isinstance(value, (bytes, np.bytes_)):
        return value.decode("utf-8", errors="replace").strip("\x00")
    if isinstance(value, np.ndarray):
        if value.size <= 10:
            return repr(value.tolist())
        return f"array(shape={value.shape}, dtype={value.dtype})"
    if isinstance(value, np.generic):
        return value.item()
    return value

def show_attrs(obj):
    if not obj.attrs:
        print("  (no attributes)")
    for key, value in obj.attrs.items():
        print(f"  @{key} = {display(value)}")

with h5py.File(FILE, "r") as f:
    print("=== IDENTIFICATION ===")
    for key in IDENTIFICATION:
        path = f"science/LSAR/identification/{key}"
        if path in f:
            print(f"{key}: {display(f[path][()])}")

    print("\n=== RASTER METADATA ===")
    for path in RASTERS:
        if path not in f:
            print(f"\nMISSING: {path}")
            continue
        obj = f[path]
        print(f"\n{path}")
        print(f"shape={obj.shape}, dtype={obj.dtype}")
        show_attrs(obj)

    print("\n=== COORDINATES / PROJECTION ===")

    def visitor(name, obj):
        leaf = name.rsplit("/", 1)[-1].lower()
        if leaf not in {"xcoordinates", "ycoordinates", "projection"}:
            return

        print(f"\n{name}")
        if not isinstance(obj, h5py.Dataset):
            print("  HDF5 group")
            return

        print(f"shape={obj.shape}, dtype={obj.dtype}")
        show_attrs(obj)

        if leaf in {"xcoordinates", "ycoordinates"}:
            values = np.asarray(obj[()])
            values = values[np.isfinite(values)]
            if values.size:
                print(
                    f"  extent=({values.min()}, {values.max()})"
                )

    f.visititems(visitor)
