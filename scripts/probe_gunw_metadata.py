"""Focused probe: print key scalar metadata and coordinate ranges for a GUNW product."""

from __future__ import annotations

import sys
from pathlib import Path

import h5py
import numpy as np

FILE = Path(sys.argv[1])

SCALARS = [
    "science/LSAR/identification/granuleId",
    "science/LSAR/identification/productType",
    "science/LSAR/identification/productVersion",
    "science/LSAR/identification/productSpecificationVersion",
    "science/LSAR/identification/compositeReleaseId",
    "science/LSAR/identification/missionId",
    "science/LSAR/identification/instrumentName",
    "science/LSAR/identification/platformName",
    "science/LSAR/identification/lookDirection",
    "science/LSAR/identification/orbitPassDirection",
    "science/LSAR/identification/trackNumber",
    "science/LSAR/identification/frameNumber",
    "science/LSAR/identification/radarBand",
    "science/LSAR/identification/isGeocoded",
    "science/LSAR/identification/isFullFrame",
    "science/LSAR/identification/referenceAbsoluteOrbitNumber",
    "science/LSAR/identification/secondaryAbsoluteOrbitNumber",
    "science/LSAR/identification/referenceZeroDopplerStartTime",
    "science/LSAR/identification/referenceZeroDopplerEndTime",
    "science/LSAR/identification/secondaryZeroDopplerStartTime",
    "science/LSAR/identification/secondaryZeroDopplerEndTime",
    "science/LSAR/identification/processingDateTime",
    "science/LSAR/identification/processingType",
    "science/LSAR/identification/productDoi",
    "science/LSAR/identification/staticLayersDataAccess",
    "science/LSAR/identification/listOfFrequencies",
    "science/LSAR/GUNW/grids/frequencyA/centerFrequency",
    "science/LSAR/GUNW/grids/frequencyA/listOfPolarizations",
    "science/LSAR/GUNW/metadata/orbit/temporalBaseline",
    "science/LSAR/GUNW/metadata/processingInformation/parameters/unwrappedInterferogram/frequencyA/ellipsoidalFlatteningApplied",
    "science/LSAR/GUNW/metadata/processingInformation/parameters/unwrappedInterferogram/frequencyA/topographicFlatteningApplied",
    "science/LSAR/GUNW/metadata/processingInformation/parameters/unwrappedInterferogram/frequencyA/numberOfAzimuthLooks",
    "science/LSAR/GUNW/metadata/processingInformation/parameters/unwrappedInterferogram/frequencyA/numberOfRangeLooks",
    "science/LSAR/GUNW/metadata/processingInformation/parameters/geocoding/rangeIonosphericCorrectionApplied",
    "science/LSAR/GUNW/metadata/processingInformation/parameters/geocoding/azimuthIonosphericCorrectionApplied",
    "science/LSAR/GUNW/metadata/processingInformation/parameters/geocoding/hydrostaticTroposphericCorrectionApplied",
    "science/LSAR/GUNW/metadata/processingInformation/parameters/geocoding/wetTroposphericCorrectionApplied",
    "science/LSAR/GUNW/metadata/processingInformation/softwareVersion",
    "science/LSAR/GUNW/grids/frequencyA/wrappedInterferogram/HH/xCoordinateSpacing",
    "science/LSAR/GUNW/grids/frequencyA/wrappedInterferogram/HH/yCoordinateSpacing",
    "science/LSAR/GUNW/grids/frequencyA/unwrappedInterferogram/HH/xCoordinateSpacing",
    "science/LSAR/GUNW/grids/frequencyA/unwrappedInterferogram/HH/yCoordinateSpacing",
]

COORDS = [
    "science/LSAR/GUNW/grids/frequencyA/wrappedInterferogram/HH",
    "science/LSAR/GUNW/grids/frequencyA/unwrappedInterferogram/HH",
    "science/LSAR/GUNW/grids/frequencyA/pixelOffsets/HH",
    "science/LSAR/GUNW/radarGrid",
]


def dec(v: object) -> str:
    if isinstance(v, (bytes, np.bytes_)):
        return v.decode("utf-8", "replace").strip("\x00 ")
    if isinstance(v, np.ndarray):
        return str([dec(x) for x in v]) if v.dtype.kind in "SOU" else np.array2string(v)
    if isinstance(v, np.generic):
        return str(v.item())
    return str(v)


with h5py.File(FILE, "r") as h5:
    print("=== SCALARS ===")
    for p in SCALARS:
        if p in h5:
            print(f"{p.rsplit('/', 1)[-1]:48s} = {dec(h5[p][()])}")
        else:
            print(f"{p.rsplit('/', 1)[-1]:48s} = <absent>")

    print("\n=== BOUNDING POLYGON (WKT, first 700 chars) ===")
    bp = h5["science/LSAR/identification/boundingPolygon"][()]
    print(dec(bp)[:700])

    print("\n=== COORDINATE RANGES ===")
    for root in COORDS:
        if root not in h5:
            print(f"{root}: <absent>")
            continue
        x = np.asarray(h5[f"{root}/xCoordinates"][()])
        y = np.asarray(h5[f"{root}/yCoordinates"][()])
        print(f"{root}")
        print(f"  x: n={x.size} first={x[0]:.4f} last={x[-1]:.4f} dx={np.diff(x)[:3]} span={x[-1]-x[0]:.2f}")
        print(f"  y: n={y.size} first={y[0]:.4f} last={y[-1]:.4f} dy={np.diff(y)[:3]} span={y[-1]-y[0]:.2f}")

    print("\n=== MASK DESCRIPTION (full) ===")
    m = h5["science/LSAR/GUNW/grids/frequencyA/unwrappedInterferogram/mask"]
    for k, v in m.attrs.items():
        print(f"  @{k} = {dec(v)}")

    print("\n=== PHASE DS ATTRS (full) ===")
    ds = h5["science/LSAR/GUNW/grids/frequencyA/unwrappedInterferogram/HH/unwrappedPhase"]
    for k, v in ds.attrs.items():
        print(f"  @{k} = {dec(v)}")

    print("\n=== DIMENSION SCALE LINKS ON PHASE ===")
    for ax in range(ds.ndim):
        scales = ds.dims[ax]
        for s in scales.items():
            print(f"  axis {ax} -> {s.name}")
    print("\n=== CC / MASK DIMENSION SCALE LINKS ===")
    for path in [
        "science/LSAR/GUNW/grids/frequencyA/unwrappedInterferogram/HH/connectedComponents",
        "science/LSAR/GUNW/grids/frequencyA/unwrappedInterferogram/mask",
    ]:
        d = h5[path]
        for ax in range(d.ndim):
            for s in d.dims[ax].items():
                print(f"  {path} axis {ax} -> {s.name}  (len {s.shape})")

    print("\n=== radarGrid coordinate spacing hints ===")
    for p in ["science/LSAR/GUNW/radarGrid/xCoordinates", "science/LSAR/GUNW/radarGrid/yCoordinates"]:
        arr = np.asarray(h5[p][()])
        print(f"  {p}: n={arr.size} first={arr[0]:.3f} last={arr[-1]:.3f} step={np.diff(arr)[:3]}")

    print("\n=== linked groups of DIMENSION_LIST on phase (which grid owns the axes) ===")
    refs = ds.attrs.get("DIMENSION_LIST")
    print(f"  phase x dim scale = {h5[refs[1][0]].name} (n={h5[refs[1][0]].shape})")

    print("\n=== mask values sample / unique (subsampled) ===")
    sub = np.asarray(m[::50, ::50])
    vals, counts = np.unique(sub, return_counts=True)
    print("  unique(subsample):", dict(zip(vals.tolist(), counts.tolist())))

    print("\n=== very coarse raster block stats (reader validation, 512-stride) ===")
    ph = np.asarray(ds[::32, ::32], dtype=np.float32)
    coh = np.asarray(h5["science/LSAR/GUNW/grids/frequencyA/unwrappedInterferogram/HH/coherenceMagnitude"][::32, ::32], dtype=np.float32)
    cc = np.asarray(h5["science/LSAR/GUNW/grids/frequencyA/unwrappedInterferogram/HH/connectedComponents"][::32, ::32])
    msk = np.asarray(m[::32, ::32])
    print(f"  phase coarse: finite={np.isfinite(ph).sum()}/{ph.size} min={np.nanmin(ph):.3f} max={np.nanmax(ph):.3f} mean={np.nanmean(ph):.3f}")
    print(f"  coh   coarse: finite={np.isfinite(coh).sum()}/{coh.size} min={np.nanmin(coh):.3f} max={np.nanmax(coh):.3f}")
    print(f"  cc    coarse: dtype={cc.dtype} uniq={np.unique(cc)[:10]} n_uniq={np.unique(cc).size} fill={(cc==65535).sum()}")
    print(f"  mask  coarse: uniq={np.unique(msk)[:12]} n_uniq={np.unique(msk).size}")
