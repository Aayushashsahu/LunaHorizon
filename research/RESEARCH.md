# NISAR Research Baseline

## 2026-09-20 baseline

### Product choice
GUNW is the first product to investigate because it is an L2 geocoded unwrapped interferogram. The ASF guide states that GUNW is derived from RIFG/RUNW and includes unwrapped interferometric phase, coherence, connected-component masks, offsets, and ionospheric phase information. The geocoded grid is 80 m for the unwrapped phase and includes 20 m/80 m coherence layers.

### Scientific language
A single GUNW gives **line-of-sight (LOS) displacement information**, not arbitrary vertical or 3D ground motion. NASA's Venezuela material describes the GUNW as measuring surface displacement in the radar line-of-sight direction.

Coherence ranges from 0 to 1 and is useful both as a quality indicator and as a clue to surface disturbance. Low coherence means phase-based measurements may be unreliable.

### First validation event
Use the **June 24, 2026 Venezuela earthquake sequence** as the first target event. NASA reports that NISAR data acquired before and after the earthquakes were used to map significant ground displacement around La Guaira and nearby areas, making it an excellent reference case for our independent processing and presentation.

### Data access
NASA's current NISAR data pages list L2 GUNW and L2 GCOV products. ASF documents searchable provisional collection identifiers including `NISAR_L2_GUNW_PROVISIONAL_V1`. NASA sample-data pages also provide downloadable representative products for learning and tool preparation.

### Development principle
Use the lowest-level product necessary. Do **not** start by processing raw SLC data. The project should initially consume analysis-ready Level-2 products.

## Questions to answer before frontend work

1. Which GUNW datasets/paths are exposed in a current production HDF5 file?
2. What scale/offset/units are encoded in the current product baseline?
3. Which coherence layer and mask should define valid pixels for the first visualization?
4. How should LOS displacement be converted and labeled without overstating precision?
5. Can we reproduce a visually/quantitatively consistent result for the Venezuela case?
6. What is the smallest cached demo asset that preserves scientific meaning and loads instantly?
7. Can the application explain data quality and limitations at the exact place the user is inspecting?

## Research references

- NASA NISAR Data Overview: https://science.nasa.gov/mission/nisar/data/
- NASA NISAR Sample Data: https://science.nasa.gov/mission/nisar/sample-data/
- ASF GUNW Data User Guide: https://nisar-docs.asf.alaska.edu/gunw/
- ASF NISAR Data Overview: https://nisar-docs.asf.alaska.edu/products-overview/
- ASF Phase/Coherence guide: https://nisar-docs.asf.alaska.edu/phase/
- NASA Geosphere / Venezuela: https://science.nasa.gov/earth-science/research/geosphere/
- NASA Earth Observatory / Venezuela: https://science.nasa.gov/earth/earth-observatory/where-venezuelas-earthquakes-shifted-the-ground/
- ASF NISAR Cookbook: https://github.com/ASFOpenSARlab/NISAR_Cookbook
- ISRO NISAR S-band product release (24 Jul 2026): https://www.isro.gov.in/NISARS_Band_SAR_Data_Products_Release.html

## Provenance rule

Do not copy benchmark values from NASA's published image into our calculations. Use NASA's result as a **reference/validation target**, then clearly distinguish our computed values from NASA's published values.
