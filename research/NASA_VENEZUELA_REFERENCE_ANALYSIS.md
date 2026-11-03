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

### 4.3 Corrections and Processing Flags

Inspection of the product metadata and the NASA JPL D-102272 Rev E specification clarifies the exact scope of each processing flag:

| Correction / Parameter | Product Metadata Flag | True Scope in Product Specification (D-102272) |
|---|---|---|
| Ellipsoidal flattening | `ellipsoidalFlatteningApplied: True` | **Phase flattened:** Interferometric phase flattened with respect to reference ellipsoid |
| Topographic flattening | `topographicFlatteningApplied: True` | **Phase flattened:** Interferometric phase flattened with respect to DEM topography |
| Ionospheric range correction | `rangeIonosphericCorrectionApplied: True` | **Geolocation only:** Flag indicates range ionospheric delay correction applied *to improve pixel geolocation* |
| Ionospheric azimuth correction | `azimuthIonosphericCorrectionApplied: True` | **Geolocation only:** Flag indicates azimuth ionospheric correction applied *to improve pixel geolocation* |
| Hydrostatic tropospheric correction | `hydrostaticTroposphericCorrectionApplied: True` | **Geolocation only:** Flag indicates hydrostatic delay applied *to improve pixel geolocation* |
| Wet tropospheric correction | `wetTroposphericCorrectionApplied: True` | **Geolocation only:** Flag indicates wet tropospheric delay applied *to improve pixel geolocation* |
| RFI mitigation | `reference/rfiMitigationApplied: True` | Radio Frequency Interference filter applied to raw signal |

> **Critical Distinction:** The geocoding flags under `metadata/processingInformation/parameters/geocoding/*` record corrections applied **to improve geolocation (pixel coordinate positioning)** during geocoding. They do **not** represent subtraction of atmospheric phase delays from the `unwrappedPhase` raster. Natural atmospheric phase contributions (differential tropospheric water vapor delay and ionospheric variations) affect radar propagation and remain present in the observed interferometric phase. While the product packages separate, auxiliary atmospheric correction layers (such as an ionospheric phase screen dataset and 3D tropospheric delay cubes), these auxiliary datasets are neither automatically subtracted from nor directly embedded within the `unwrappedPhase` array.

### 4.4 Phase-to-Displacement Conversion & Radar Parameters

The standard two-way interferometric line-of-sight relationship is:

$$d_{\text{LOS}} = \frac{\phi \cdot \lambda}{4\pi}$$

Where:
- $\phi$ = unwrapped interferometric phase (radians)
- $\lambda = \frac{c}{f_0}$ = radar wavelength
- $d_{\text{LOS}}$ = line-of-sight displacement (metres)

**Product-Specific Radar Frequency:**
The granule's actual metadata records a center frequency under `grids/frequencyA/centerFrequency`:
- **Center frequency:** $f_0 = 1,239,000,000.0\text{ Hz}$ ($1.239\text{ GHz}$)
- **Derived radar wavelength:** $\lambda = \frac{299,792,458\text{ m/s}}{1,239,000,000\text{ Hz}} \approx 0.241963\text{ m}$ ($\approx 24.20\text{ cm}$)

*(Note: While generic literature often quotes NISAR's nominal L-band center as 1.255 GHz or 1.2575 GHz giving $\lambda \approx 23.85\text{ cm}$, the authoritative product metadata for this granule specifically records $1.239\text{ GHz}$. Product-specific metadata must take precedence.)*

**Derived Metric Conversions:**
- **Per radian:** $\frac{\lambda}{4\pi} = \frac{0.241963\text{ m}}{4\pi} \approx 0.019255\text{ m} \approx \mathbf{1.93\text{ cm/radian}}$
- **Per full $2\pi$ phase cycle:** $\frac{\lambda}{2} = \frac{0.241963\text{ m}}{2} \approx 0.12098\text{ m} \approx \mathbf{12.10\text{ cm}}$ (rather than the generic 11.9 cm)

### 4.5 Phase Sign Convention — Unresolved in Specification

In SAR interferometry, the sign convention depends on whether the interferogram is formed as $S_1 S_2^*$ or $S_2 S_1^*$:
- Under $S_{\text{secondary}} S_{\text{reference}}^*$, an increasing range away from the radar yields positive phase.
- Under $S_{\text{reference}} S_{\text{secondary}}^*$, an increasing range away from the radar yields negative phase.

**Audit finding:** An exhaustive audit of the NASA JPL Level-2 GUNW specification (D-102272 Rev E) reveals that **no explicit phase sign convention is defined in the product specification**. Section 5 defines `unwrappedPhase` merely as *"Unwrapped interferogram between HH layers"*. Without an explicit definition in product documentation or independent ground-truth calibration against continuous GNSS stations, **the phase sign convention remains unresolved for this product**.

### 4.6 Uncertainty and Limitations Reported by NASA

- LOS displacement maps provide a 1D projection of 3D surface motion; vertical and horizontal components cannot be independently separated from a single track.
- Multi-track combination (ascending + descending) is required to decompose into vertical and east–west components.
- Near-field areas with strong phase gradients may have residual unwrapping errors.
- Phase observations in areas with coherence loss (vegetation, heavy rainfall, or large displacements exceeding the unwrapping capacity) are unreliable.
- Atmospheric phase residuals remain after correction application.

---

## 5. Comparison with the LunaHorizon Project

### 5.1 What is comparable

| Parameter | NASA Study (A162 track) | LunaHorizon Observation |
|---|---|---|
| NISAR orbital track | Track 162 (Ascending) | Track 162 (Ascending) |
| Reference acquisition | 2026-06-13 | 2026-06-13 10:06:56 UTC |
| Secondary acquisition | 2026-06-25 | 2026-06-25 10:06:55 UTC |
| Temporal baseline | ~12 days | 11 days 23:59:59 UTC (~12.000 calendar days) |
| Product family | NISAR Level-2 GUNW | NISAR Level-2 GUNW (v1.0.11, spec 1.5.0) |
| Center frequency | L-band (1.239 GHz) | 1,239,000,000.0 Hz (derived $\lambda \approx 0.2420$ m) |
| Flattening | Ellipsoidal + DEM topographic | Ellipsoidal + DEM topographic (`True` in metadata) |

**Relationship:** The LunaHorizon project processes an authentic NISAR Level-2 GUNW granule covering the same orbital pass (Ascending Track 162) and same nominal date pair (June 13 and June 25, 2026) that NASA used as one of its three InSAR tracks. However, NASA's published study was produced by the NASA/JPL Operations Science Team using their specialized processing, multi-track combination (integrating A162 with Descending D54 and Ascending A61), and calibrated deformation modeling. LunaHorizon displays standalone Level-2 unwrapped phase in radians and does not claim to reproduce or replicate NASA's multi-track displacement solution.

### 5.2 Key Differences

| Aspect | NASA Study | LunaHorizon Project |
|---|---|---|
| Number of tracks processed | 3 (A162, D54, A61) | 1 (A162 standalone granule) |
| Output quantity | Derived LOS displacement (cm) | Unwrapped interferometric phase (radians) |
| Multi-track 3D decomposition | Yes (combined geometry) | No (single track line-of-sight only) |
| Atmospheric phase screen | Evaluated / modeled | Separated as distinct product layers; un-subtracted from phase |
| Phase sign convention | Operational pipeline convention | Explicitly marked unresolved in product spec |
| Independent validation | Yes (published research result) | Marked `scientific_interpretation_validated: false` |

### 5.3 Scientific Prerequisites for Metric Displacement

A scientifically defensible conversion from unwrapped phase to ground displacement requires satisfying several prerequisites:

1. ⚠️ **Phase sign convention:** Unresolved in product specification D-102272; must be confirmed before assigning direction (uplift vs. subsidence).
2. ⚠️ **Reference anchoring:** Single-granule InSAR requires an independently verified reference point (e.g. continuous GNSS station) to convert relative phase differences to absolute ground displacement.
3. ⚠️ **Atmospheric phase contributions:** Physical propagation delays through the atmosphere (tropospheric water vapor turbulence and ionospheric TEC gradients) remain present in the observed `unwrappedPhase`. While the Level-2 product provides separate auxiliary correction layers and cubes, isolating true tectonic deformation requires explicitly modeling and subtracting these atmospheric contributions rather than assuming the interferogram is free of atmospheric phase.
4. ⚠️ **Orbital ramp removal:** Residual orbital trajectory errors produce long-wavelength ramps that must be removed via baseline modeling.
5. ✅ **Radar wavelength:** Authoritatively determined from product metadata: $f_0 = 1.239\text{ GHz} \rightarrow \lambda \approx 0.2420\text{ m}$.
6. ✅ **Quality masking:** Coherence magnitude and product validity masks allow rigorous exclusion of unreliable decorrelated pixels.

**Conclusion:** Because prerequisites 1–4 are not resolved within this single Level-2 GUNW granule, the application strictly and honestly presents **unwrapped phase in radians**, accompanied by coherence and validity masks. The metric conversion factor ($1\text{ rad} \approx 1.93\text{ cm}$ LOS, $2\pi\text{ rad} \approx 12.10\text{ cm}$) is documented as an educational reference, not asserted as a calibrated measurement.

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
