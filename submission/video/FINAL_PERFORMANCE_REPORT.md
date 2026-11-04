# Demo Video Final Master — Application Performance & Latency Report

**Project:** NISAR // Earth in Motion  
**Repository:** https://github.com/Aayushashsahu/LunaHorizon  
**Master Video:** `artifacts/demo/nisar_earth_in_motion_FINAL.mp4`  
**Measurement Script:** `scripts/measure_latency.mjs`

---

## 1. Test Environment & Methodology

Benchmarks were collected via Chrome DevTools Protocol (`scripts/measure_latency.mjs`) executing against the local Python HTTP application server running on `127.0.0.1:8000`.

- **OS / Platform:** Windows 11 (win32, x64)
- **Runtime:** Python 3.11.15, Node.js v22.14.0
- **Browser:** Headless Chrome 133.0.6943.142 (`--window-size=1920,1080`, device scale factor 1.0)
- **Network Profile:** Local loopback (`127.0.0.1`), offline-first (no external CDN, no third-party tiles)
- **Data Source:** Processed 80 m Venezuela Level-2 GUNW raster products (`phase.tif`, `coherence.tif`) with persistent cached `rasterio.windows.Window` readers.

---

## 2. Interaction Latency Benchmark Measurements

| Interaction Event | Target SLA | Measured Latency | Performance vs. SLA | Methodological Verification |
|---|---|---|---|---|
| **Server Connection** | < 50 ms | **0 ms** | Instantaneous | Immediate loopback handshake (`/api/health`) |
| **Dashboard Usable** | < 1,500 ms | **574 ms** | 62% faster than SLA | Full DOM load, style resolution, initial layout |
| **Observation Cards Populated** | < 1,000 ms | **574 ms** | 43% faster than SLA | `/api/index` fetch, parse, and card rendering |
| **Explorer Navigation & Open** | < 800 ms | **237 ms** | 70% faster than SLA | View swap (`showView('explorer')`) + observation load |
| **Phase Layer First Paint** | < 100 ms | **39 ms** | 61% faster than SLA | Canvas pixel transfer and 2D canvas paint |
| **Coherence Layer Switching** | < 150 ms | **66 ms** | 56% faster than SLA | Tab click to Magma buffer swap and repaint |
| **Coherence Slider Input** | < 30 ms | **6 ms** | 80% faster than SLA | Slider drag event dispatch to mask update |
| **Pixel Inspection Tooltip** | < 150 ms | **58 ms** | 61% faster than SLA | Pointer movement to Float32 sampling tooltip |
| **Export Initiation** | < 50 ms | **1 ms** | Instantaneous | Button click to download trigger |

---

## 3. Pixel Inspection Endpoint Optimization Summary

In previous builds, pixel inspection relied on an external background process that risked abrupt socket resets or unhandled out-of-bounds exceptions.

### Engineering Resolutions Applied:
1. **Thread-Safe Persistent Window Readers:** Replaced per-request file opening with persistent `rasterio.windows.Window` readers protected by `threading.Lock`. Windowed bounding reads execute in `< 1 ms` on local NVMe storage.
2. **Graceful Coverage Clamping:** Queries outside raster coverage now return a clean structured payload (`in_grid: false, valid: false, phase_radians: null, coherence: null`) without raising an unhandled 400 error.
3. **Socket Reset Shielding:** Disconnection exceptions (`BrokenPipeError`, `ConnectionResetError`, `ConnectionAbortedError`) on Windows are safely caught and ignored, preventing thread crashes during rapid pointer movements.
4. **Debounced Fetch with AbortController:** Frontend `sampleAt()` utilizes an `AbortController` (4,000 ms timeout) and token-based debouncing to ensure only the most recent user cursor position updates the display.
