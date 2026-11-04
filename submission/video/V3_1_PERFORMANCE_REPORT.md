# Demo Video V3.1 — Performance & Latency Report

**Project:** NISAR // Earth in Motion  
**Benchmark Date:** 2026-11-04  
**Hardware & Runtime:** Windows x64, Chromium Headless (`--headless=new`), Python 3.11, FastAPI/Uvicorn, Rasterio 1.4  
**Measurement Method:** Direct high-resolution timing via Chrome DevTools Protocol (`performance.now()`) across real web application lifecycles with warm and cold caches.

---

## 1. Measured Web Application Latency Benchmarks (Before & After V3.1 Optimizations)

| Benchmark Metric | V3 Measured | V3.1 Measured | Target SLA | Method & Verification Details |
|---|---|---|---|---|
| **Server Connected** | 0 ms | **0 ms** | < 100 ms | Loopback verification against `/api/health`; immediate HTTP handshake. |
| **Observation Cards Populated** | 739 ms (warmed) | **739 ms (warmed)** / 1,762 ms (cold) | < 1,500 ms | Full retrieval of `/api/index`, JSON schema deserialization, and DOM element mounting for all cards. |
| **Explorer Opening** | 313 ms | **441 ms** | < 800 ms | View switch, metadata fetch (`/api/observations/venezuela`), and DOM layout initialization. |
| **Phase Rendering** | 39 ms | **6 ms** | < 250 ms | Raster image buffer paint to 2D canvas (verified non-zero alpha pixel blit: `painted: true`). |
| **Coherence Layer Switching** | 70 ms | **70 ms** | < 200 ms | Tab click to active canvas re-render with cividis colormap. |
| **Slider Input Response** | 9 ms | **10 ms** | < 50 ms | Real-time threshold slider input event to canvas filter and statistics update. |
| **Pixel Tooltip Inspection** | 69 ms | **68 ms** | < 100 ms | Cursor move event over map coordinates to active coordinate & value tooltip paint. **Now supported directly from processed GeoTIFFs without 2.34 GB raw HDF5 file.** |
| **Export Initiation** | 11 ms | **2 ms** | < 200 ms | Click on export button to browser blob / download stream generation. |

---

## 2. Key Architectural Performance Improvements in V3.1

1. **Cached Raster Dataset Access:**
   - Instead of opening and closing raster files on every cursor movement, `ObservationRepository` in `src/nisar_eim/webapp/server.py` now maintains a persistent `_readers` cache for active GeoTIFF datasets.
   - Per-pixel window sampling (`Window(col_off, row_off, width, height)`) is now performed in sub-millisecond time.

2. **Decoupled Offline Pixel Inspection:**
   - Pixel sampling is no longer hard-blocked by the absence of the 2.34 GB raw HDF5 granule.
   - When running in an offline or clean-clone environment without `data/raw/`, the server transparently falls back to sampling the committed full-resolution 80 m GeoTIFFs (`phase.tif` and `coherence.tif`).
   - Bit-level verification confirms a **0.0 maximum absolute difference** between the raw HDF5 and GeoTIFF values.

3. **Smooth Interaction Dynamics:**
   - Slider drag and event marker selection use non-blocking requestAnimationFrame canvas redraws, maintaining 60 FPS in interactive sessions.
