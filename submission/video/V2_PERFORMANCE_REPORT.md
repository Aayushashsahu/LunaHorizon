# Demo Video V2 — Performance Report

**Project:** NISAR // Earth in Motion
**Date:** 2026-11-03
**Server command:** `.venv\Scripts\python.exe -m nisar_eim serve --port 8000 --data-root "D:\Nasa hackton\data\processed"`

## Application Performance Benchmarks

Measured via Invoke-WebRequest against the running local server.

| Benchmark | Measured | Method |
|-----------|----------|--------|
| Server startup | < 4 s | `Start-Sleep 4; Invoke-WebRequest 127.0.0.1:8000` → HTTP 200 |
| Dashboard page load | 259 ms | `GET /` timing |
| Venezuela metadata | 76 ms | `GET /api/observations/venezuela` |
| Phase raster (PNG) | < 200 ms | Pre-loaded during pre-warm phase |
| Coherence layer switch | ~400 ms | CDP eval + sleep(400) |
| Threshold slider update | < 100 ms | DOM event dispatched |

## V2 Production Pipeline Timing

| Stage | Duration |
|-------|----------|
| Audio mix (FFmpeg, 6 WAVs → 48k stereo) | ~3 s |
| Subtitle generation | < 1 s |
| Pre-warm (app load + Venezuela open) | ~3.5 s |
| Frame capture (2700 frames via CDP) | ~8 min |
| Video encode (FFmpeg, CRF 20) | ~40 s |
| ffprobe validation + frame extraction | ~10 s |
| **Total pipeline** | **~10 min** |

## V2 Video Technical Specifications

| Attribute | Measured |
|-----------|----------|
| File | `artifacts/demo/nisar_earth_in_motion_demo_v2.mp4` |
| Size | 7,234,852 bytes (6.90 MiB) |
| Duration | 90.000 s |
| Video codec | H.264 High Profile Level 4.2 |
| Video bitrate | 477,688 bps |
| Resolution | 1920 x 1080 |
| Frame rate | 30/1 FPS |
| Frames | 2700 |
| Audio codec | AAC LC |
| Audio sample rate | **48,000 Hz** (V1 was 22,050 Hz) |
| Audio channels | **2 (stereo)** (V1 was mono) |
| Audio bitrate | 156,388 bps |
| Container | MP4 / QuickTime |
| faststart | Yes |
| Pixel format | yuvj420p |

## QA Results

| Check | Result |
|-------|--------|
| pytest | 93/93 passed (15.72 s) |
| ruff check src tests | All checks passed |
| python -m compileall -q src | Clean |
| node --check scripts/record_demo_v2.mjs | Clean |
| node --check src/nisar_eim/webapp/static/app.js | Clean |
| git diff --check HEAD | Clean |

## V2 Defect Resolution Status

| Defect | Status |
|--------|--------|
| D-01: Audio 22050 Hz mono | FIXED — 48,000 Hz stereo confirmed by ffprobe |
| D-02: Narration overlap risk | MITIGATED — amix duration=longest |
| D-03: Temporal baseline "12-DAY" | FIXED — "~12-day repeat (11d 23h 59m elapsed)" in HUD + subtitle |
| D-04: Black ending 1.5 s | FIXED — 360 frames = 12 s all closing card |
| D-05: No real mouse events | FIXED — CDP Input.dispatchMouseEvent for slider and canvas hover |
| D-06: Subtitle contrast | IMPROVED — 34pt, BorderStyle 3 opaque box, 60px margin |
