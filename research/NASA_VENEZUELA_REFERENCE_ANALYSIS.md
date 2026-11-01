# NASA Venezuela Reference Analysis

**File:** `research/NASA_VENEZUELA_REFERENCE_ANALYSIS.md`  
**Created:** 2026-11-01  
**Purpose:** Independent research into NASA's published NISAR displacement study of the June 2026 Venezuela earthquake doublet. Used to contextualise the LunaHorizon project's own observations and clearly identify what is and is not directly comparable.

---

## 1. Source Publication

**Title:** Where Venezuela's Earthquakes Shifted the Ground  
**Published:** 2026-07-10  
**Publisher:** NASA Earth Observatory / NASA Science  
**URL:** <https://science.nasa.gov/earth/earth-observatory/where-venezuelas-earthquakes-shifted-the-ground/>  
**Author:** Lauren Dauphin (NASA)  
**Accessed:** 2026-11-01

---

## 2. Event Summary

Two large earthquakes struck northern Venezuela on 24 June 2026 within approximately 32 seconds of each other:

| Event ID | Role | Magnitude | Time (UTC) | Latitude | Longitude | Depth |
|---|---|---|---|---|---|---|
| `us6000t7zc` | Foreshock | M 7.2 | 2026-06-24 22:04:31.806 | 10.3713° N | 68.5564° W | 10.0 km |
| `us6000t7zp` | Mainshock | M 7.5 | 2026-06-24 22:05:04.053 | 10.5955° N | 67.2205° W | 10.0 km |

The earthquakes caused severe structural damage in Caracas, La Guaira, and adjacent coastal zones. Up to approximately **60 cm (nearly two feet)** of ground displacement was measured by NISAR InSAR in parts of the affected region.

---

## 3. NISAR Acquisitions Used by NASA

NASA's Operations Science Team at JPL/Caltech processed **three independent interferometric pairs** to map coseismic deformation:

| Track | Direction | Reference (pre-event) | Secondary (post-event) |
|---|---|---|---|
| **A162** | Ascending | 2026-06-13 | 2026-06-25 |
| **D54** | Descending | 2026-06-17 | 2026-06-29 |
| **A61** | Ascending | 2026-06-18 | 2026-06-30 |

> **This project uses Track A162 (June 13–June 25), which is the same pair as one of NASA's three tracks.**

---

## 4. NASA's Displacement Measurement Methodology

### 4.1 Technique

NASA applied InSAR (Interferometric Synthetic Aperture Radar) using the NISAR L-band (approximately 24 cm wavelength) sensor. InSAR measures the change in range (distance) between the satellite and Earth's surface along the radar line-of-sight (LOS), which is angled roughly 40° from vertical.

### 4.2 LOS Convention

The displacement maps use the following colour convention:

- **Red / warm tones:** surface movement **towards** the satellite (eastward/uplift components depending on track geometry)
- **Blue / cool tones:** surface movement **away** from the satellite (westward/subsidence)
- **Yellow:** near-zero displacement

### 4.3 Corrections Applied

NISAR Level-2 GUNW products used by NASA include the following standard geocoding corrections, all of which are confirmed as applied in our product's metadata:

| Correction | Applied? (Our product metadata) |
|---|---|
| Ellipsoidal flattening | `True` |
| Topographic (DEM) flattening | `True` |
| Ionospheric range correction | `True` (geocoding step) |
| Ionospheric azimuth correction | `True` (geocoding step) |
| Hydrostatic tropospheric correction | `True` (geocoding step) |
| Wet tropospheric correction | `True` (geocoding step) |
| RFI mitigation | `True` |

These corrections are applied during the geocoding step to the geocoded layers; they do **not** modify the stored `unwrappedPhase` raster values directly. The unwrapped phase values in the HDF5 file therefore represent:

> **Phase difference after ellipsoidal and topographic flattening, in radians, without explicit atmospheric corrections applied to the phase array itself.**

### 4.4 Phase-to-Displacement Conversion

The standard two-way interferometric relationship is:

$$d_{\text{LOS}} = \frac{\phi \cdot \lambda}{4\pi}$$

Where:
- $\phi$ = unwrapped interferometric phase (radians)
- $\lambda$ = radar wavelength ≈ 0.2385 m for NISAR L-band (1255 MHz centre frequency)
- $d_{\text{LOS}}$ = line-of-sight displacement (metres, positive = towards satellite)

**One full phase cycle ($2\pi$ rad) corresponds to approximately $\lambda/2 \approx 11.9$ cm of LOS displacement.**

### 4.5 Sign Convention

The standard NISAR GUNW convention for unwrapped phase is:

> **Phase = secondary phase − reference phase**

Positive phase values indicate the surface moved **away** from the satellite (range increased) between the reference and secondary acquisitions. Negative values indicate movement **towards** the satellite.

This convention is confirmed by NASA JPL documentation (D-102272, NISAR NASA SDS Product Specification L2 GUNW, which is the reference document stated in our product's HDF5 file attributes).

### 4.6 Uncertainty and Limitations Reported by NASA

- LOS displacement maps provide a 1D projection of 3D surface motion; vertical and horizontal components cannot be independently separated from a single track.
- Multi-track combination (ascending + descending) is required to decompose into vertical and east–west components.
- Near-field areas with strong phase gradients may have residual unwrapping errors.
- Phase observations in areas with coherence loss (vegetation, heavy rainfall, or large displacements exceeding the unwrapping capacity) are unreliable.
- Atmospheric phase residuals remain after correction application.

---

## 5. Comparison with the LunaHorizon Project

### 5.1 What is identical

| Parameter | NASA (Track A162) | LunaHorizon |
|---|---|---|
| NISAR track | A162 | A162 |
| Reference acquisition | 2026-06-13 | 2026-06-13 10:06:56 UTC |
| Secondary acquisition | 2026-06-25 | 2026-06-25 10:06:55 UTC |
| Temporal baseline | 12 days | 11 days 23:59:59 (~12.000 days) |
| Product type | L-2 GUNW | L-2 GUNW |
| Specification | D-102272 | D-102272 v1.5.0 |
| Corrections applied | Iono, tropo, topo, ellipsoidal | Same (confirmed from metadata) |

**The LunaHorizon project is working with the same Track A162 interferometric product that NASA used for one of its three displacement maps.**

### 5.2 What is different

| Aspect | NASA | LunaHorizon |
|---|---|---|
| Number of tracks processed | 3 (A162, D54, A61) | 1 (A162) |
| Displacement map produced | Yes (LOS, cm) | Not published — phase in radians |
| Sign convention documented | Yes (towards/away from satellite) | Identified from D-102272 |
| Multi-track decomposition | Planned/partial | Not applicable |
| Independent validation | Yes (published July 10, 2026) | Referenced, not replicated |
| Fault trace overlay | Yes (geological fault map) | Not included |

### 5.3 Whether LOS displacement can be derived from our product

Based on this investigation:

**The physical preconditions for computing relative LOS displacement from the bundled A162 product ARE met:**

1. ✅ Wavelength is documented: NISAR L-band, centre frequency 1255 MHz → $\lambda \approx 0.2385$ m
2. ✅ Phase unit is confirmed: radians (declared in HDF5 dataset attributes)
3. ✅ Corrections applied during geocoding: iono, tropo, topo, ellipsoidal flattening
4. ✅ Sign convention is defined: secondary − reference; positive = away from satellite
5. ✅ Connected components are provided: ambiguity-safe within a component
6. ✅ Coherence magnitude is provided: quality filter applicable
7. ⚠️ Solid-Earth tidal correction: not explicitly listed in geocoding parameters; may be embedded in the product processing
8. ⚠️ Orbital error ramp: not corrected in the product; large-scale phase trends may include orbital contributions
9. ⚠️ Reference pixel: no absolute reference; only **relative** displacement (change relative to a chosen reference point) can be computed without GPS ground truth

**Conclusion:** A **relative LOS displacement** estimate is scientifically defensible, provided:
- It is presented as **relative** (not absolute displacement)
- Coherence thresholding is applied (recommend ≥ 0.4)
- Connected-component boundaries are respected
- The computation is clearly labeled as illustrative, not independently validated
- The sign convention and wavelength assumption are disclosed

The metric conversion is: **1 radian ≈ 1.9 cm LOS displacement** at L-band.

---

## 6. Reproducibility Notes

### 6.1 Data access

The Track A162 product used in this project is:

```
NISAR_L2_PR_GUNW_022_162_A_007_023_4000_SH_20260613T100656_20260613T100731_20260625T100655_20260625T100730_P05023_N_F_J_001.h5
```

It was obtained from NASA Earthdata / Alaska Satellite Facility (ASF). The raw HDF5 file (2.34 GB) is not committed to this repository; it is stored under `data/raw/nisar_venezuela/` and gitignored.

### 6.2 Accessing additional NASA tracks

The D54 and A61 tracks used by NASA for the multi-track decomposition are potentially accessible through:
- NASA Earthdata: <https://search.earthdata.nasa.gov/>
- Alaska Satellite Facility: <https://search.asf.alaska.edu/>
- NISAR Urgent Response products: <https://nisar.jpl.nasa.gov/>

Earthdata credentials are required and must not be stored in this repository.

### 6.3 Compatibility check required

Before ingesting any additional NISAR product, the pipeline requires verification of:
- Product type and version
- Reference and secondary acquisition timestamps
- Track, frame, and frequency
- Raster dimensions and grid spacing
- HDF5 dimension scale availability
- Consistency with the existing `data/processed/venezuela/` observation

---

## 7. References

1. Dauphin, L. (2026-07-10). *Where Venezuela's Earthquakes Shifted the Ground*. NASA Earth Observatory / NASA Science. <https://science.nasa.gov/earth/earth-observatory/where-venezuelas-earthquakes-shifted-the-ground/>
2. NASA JPL. (2026). *NASA SDS Product Specification: Level-2 Geocoded UNWRapped Interferogram (GUNW)*. Document D-102272. Referenced in HDF5 product file attributes.
3. USGS. (2026). *Earthquake event us6000t7zc (M 7.2)*. <https://earthquake.usgs.gov/earthquakes/eventpage/us6000t7zc>
4. USGS. (2026). *Earthquake event us6000t7zp (M 7.5)*. <https://earthquake.usgs.gov/earthquakes/eventpage/us6000t7zp>
