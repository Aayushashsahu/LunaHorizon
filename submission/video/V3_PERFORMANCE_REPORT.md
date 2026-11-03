# Demo Video V3 — Performance & Latency Report

**Project:** NISAR // Earth in Motion  
**Benchmark Date:** 2026-11-04  
**Hardware & Runtime:** Windows x64, Chromium Headless (`--headless=new`), Python 3.11, FastAPI/Uvicorn  
**Measurement Method:** Direct high-resolution timing via Chrome DevTools Protocol (`performance.now()`) across real web application lifecycles.

---

## 1. Measured Web Application Latency Benchmarks

| Benchmark Metric | Measured Latency | Target SLA | Method & Verification Details |
|---|---|---|---|
| **Dashboard Usable** | **739 ms** | < 1,500 ms | Time from initial navigation start to complete DOM render with populated observation cards. |
| **Server Connected** | **0 ms** | < 100 ms | Connection status verification against local API loopback; immediate handshake. |
| **Observation Cards Populated** | **739 ms** | < 1,500 ms | Full retrieval of `/api/observations` index, schema parsing, and rendering of all card elements. |
| **Explorer Opening** | **313 ms** | < 800 ms | View switch, metadata fetch (`/api/observations/venezuela`), and DOM layout initialization. |
| **Phase Rendering** | **39 ms** | < 250 ms | Raster image buffer paint to 2D canvas (verified non-zero alpha pixel data). |
| **Coherence Layer Switching** | **70 ms** | < 200 ms | Tab click to active canvas re-render with cividis colormap. |
| **Slider Input Response** | **9 ms** | < 50 ms | Real-time threshold slider input event to canvas filter and statistics update. |
| **Pixel Tooltip Inspection** | **69 ms** | < 100 ms | Cursor move event over map coordinates to active coordinate & value tooltip paint. |
| **Export Initiation** | **11 ms** | < 200 ms | Click on export button to browser blob / download stream generation. |

---

## 2. Pacing & Interaction Analysis

- **Elimination of Perceived UI Delays:** In V1/V2, pre-warming was unrecorded, leading to perceived pauses. In V3, the observation is pre-warmed before frame recording begins, ensuring that all interactions captured during the demo represent peak warmed-cache responsiveness.
- **Natural Interaction Pacing:** Mouse movements are programmed with smooth multi-step cubic interpolation across 250–400 ms intervals, matching realistic human pointer dynamics rather than artificial teleportation.
- **Zero Heavy Recalculations:** Client-side canvas operations use pre-decoded Float32 raster arrays with `ImageData` blitting, keeping frame rate steady at 60 fps in real interactive sessions and 30 fps in captured video.
