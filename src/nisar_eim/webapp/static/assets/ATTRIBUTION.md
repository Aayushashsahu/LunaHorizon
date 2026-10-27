# Hero Asset Attribution & Provenance

## 1. Visual Asset: Earth Rotating Texture Map (Equirectangular Blue Marble)
- **Files**: `earth_texture_2048.webp` (544 KB, optimized), `earth_texture_2048.jpg` (579 KB archive)
- **Dimensions**: 2048 × 1024 px (seamless 360° × 180° equirectangular projection)
- **Source**: NASA Visible Earth (Record ID: 57735 — "The Blue Marble: Land Surface, Ocean Color, Sea Ice, and Clouds")
  - URL: `https://visibleearth.nasa.gov/images/57735/the-blue-marble-land-surface-ocean-color-sea-ice-and-clouds`
  - High-res archive: `https://eoimages.gsfc.nasa.gov/images/imagerecords/57000/57735/land_ocean_ice_cloud_2048.jpg`
- **Credit**: Reto Stöckli, NASA Goddard Space Flight Center
- **Data Source**: Terra / MODIS composite
- **License / Terms**: Public Domain (NASA Open Data Policy)
- **Role**: Continuously rotating 3D spherical globe surface texture on the landing dashboard hero, animating at 72 seconds per full revolution with fixed day/night terminator and 3D spherical shading.

## 2. Fallback Visual Asset: Earth Western Hemisphere (MODIS Blue Marble)
- **Files**: `earth_hero.webp` (317 KB, optimized), `earth_hero.jpg` (396 KB fallback)
- **Source**: NASA Visible Earth (Record ID: 57723)
  - URL: `https://visibleearth.nasa.gov/view.php?id=57723`
- **Credit**: NASA Earth Observatory / Goddard Space Flight Center (Reto Stöckli & Robert Simmon)
- **License / Terms**: Public Domain (NASA Open Data Policy)
- **Role**: Instant initial visual and static fallback under reduced-motion preference (`prefers-reduced-motion: reduce`).

## 3. Application Usage & Scientific Integrity Note
These visual assets serve exclusively as an illustrative planetary hero background for the landing dashboard. They demonstrate the macroscopic Earth context of the NASA-ISRO Synthetic Aperture Radar (NISAR) mission.

**Scientific Guardrail:**
The hero globe is strictly illustrative planetary context. It is **not** a live telemetry feed, real-time satellite position, or a representation of radar phase. The verified, georeferenced NISAR Level-2 GUNW interferograms and measurements are loaded, rendered, and analyzed exclusively inside the **Observation Explorer** (`#view-explorer`).
