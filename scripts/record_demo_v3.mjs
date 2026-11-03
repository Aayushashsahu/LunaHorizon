#!/usr/bin/env node
/**
 * record_demo_v3.mjs — NISAR // Earth in Motion — Demo Video V3 (Master Production)
 */

import { spawn, execSync } from 'node:child_process';
import {
  existsSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  writeFileSync,
  rmSync,
} from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { setTimeout as sleep } from 'node:timers/promises';

const REPO_ROOT = resolve('.');
const BASE_URL = process.env.NISAR_BASE_URL || 'http://127.0.0.1:8000';
const OUTPUT_MP4 = resolve(REPO_ROOT, 'artifacts/demo/nisar_earth_in_motion_demo_v3.mp4');
const TEMP_DIR = resolve(REPO_ROOT, 'artifacts/demo/temp_v3');
const FRAMES_DIR = resolve(TEMP_DIR, 'frames');
const AUDIO_DIR = resolve(REPO_ROOT, 'artifacts/demo/audio_v3');

const CHROME_PATH =
  process.env.CHROME_PATH || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';

const TOTAL_SECONDS = 90;
const FPS = 30;
const TOTAL_FRAMES = TOTAL_SECONDS * FPS; // 2700 frames

function log(msg) {
  process.stdout.write(`[record_v3] ${msg}\n`);
}

function ensureDirectories() {
  mkdirSync(resolve(REPO_ROOT, 'artifacts/demo'), { recursive: true });
  mkdirSync(TEMP_DIR, { recursive: true });
  mkdirSync(FRAMES_DIR, { recursive: true });
}

async function captureApplicationFrames() {
  log('Connecting to Chrome DevTools Protocol...');
  if (!existsSync(CHROME_PATH)) {
    throw new Error(`Chrome not found at: ${CHROME_PATH}`);
  }

  const profile = mkdtempSync(join(tmpdir(), 'nisar-v3-'));
  const child = spawn(
    CHROME_PATH,
    [
      '--headless=new',
      '--disable-gpu',
      '--no-first-run',
      '--no-default-browser-check',
      '--remote-allow-origins=*',
      `--user-data-dir=${profile}`,
      '--remote-debugging-port=0',
      '--window-size=1920,1080',
      'about:blank',
    ],
    { stdio: ['ignore', 'ignore', 'pipe'] }
  );

  let endpoint = null;
  const portFile = join(profile, 'DevToolsActivePort');
  for (let i = 0; i < 200 && !endpoint; i++) {
    try {
      const lines = readFileSync(portFile, 'utf-8').split(/\r?\n/);
      if (lines[0]) endpoint = Number(lines[0]);
    } catch {}
    if (!endpoint) await sleep(100);
  }

  if (!endpoint) {
    child.kill();
    throw new Error('Chrome DevTools endpoint could not be opened.');
  }

  const targets = await (await fetch(`http://127.0.0.1:${endpoint}/json/list`)).json();
  const page = targets.find((t) => t.type === 'page');
  const ws = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((res, rej) => {
    ws.addEventListener('open', res, { once: true });
    ws.addEventListener('error', rej, { once: true });
  });

  let nextId = 0;
  const pending = new Map();
  ws.addEventListener('message', (event) => {
    const msg = JSON.parse(event.data);
    if (msg.id && pending.has(msg.id)) {
      const { resolve, reject } = pending.get(msg.id);
      pending.delete(msg.id);
      if (msg.error) reject(new Error(msg.error.message));
      else resolve(msg.result);
    }
  });

  const send = (method, params = {}) =>
    new Promise((resolve, reject) => {
      const id = ++nextId;
      pending.set(id, { resolve, reject });
      ws.send(JSON.stringify({ id, method, params }));
    });

  const evaluate = async (expression) => {
    const res = await send('Runtime.evaluate', {
      expression,
      returnByValue: true,
      awaitPromise: true,
    });
    if (res.exceptionDetails) {
      log(`JS warning: ${res.exceptionDetails.text}`);
    }
    return res.result?.value;
  };

  const mouseMove = async (x, y) => {
    await send('Input.dispatchMouseEvent', { type: 'mouseMoved', x, y, modifiers: 0 });
  };

  const mouseDown = async (x, y) => {
    await send('Input.dispatchMouseEvent', {
      type: 'mousePressed',
      x,
      y,
      button: 'left',
      clickCount: 1,
      modifiers: 0,
    });
  };

  const mouseUp = async (x, y) => {
    await send('Input.dispatchMouseEvent', {
      type: 'mouseReleased',
      x,
      y,
      button: 'left',
      clickCount: 1,
      modifiers: 0,
    });
  };

  await send('Page.enable');
  await send('Runtime.enable');
  await send('Emulation.setDeviceMetricsOverride', {
    width: 1920,
    height: 1080,
    deviceScaleFactor: 1,
    mobile: false,
  });

  let currentFrameNumber = 1;

  async function snapFrame() {
    const res = await send('Page.captureScreenshot', { format: 'jpeg', quality: 95 });
    return Buffer.from(res.data, 'base64');
  }

  function writeFrameFile(frameNum, buffer) {
    const filename = `frame_${String(frameNum).padStart(5, '0')}.jpg`;
    writeFileSync(resolve(FRAMES_DIR, filename), buffer);
  }

  function duplicateFrames(buffer, count) {
    for (let i = 0; i < count; i++) {
      if (currentFrameNumber <= TOTAL_FRAMES) {
        writeFrameFile(currentFrameNumber++, buffer);
      }
    }
  }

  log('Pre-warming: loading application and opening Venezuela observation...');
  await send('Page.navigate', { url: BASE_URL + '/' });
  await sleep(2000);
  await evaluate(`(async () => {
    try {
      showView('explorer');
      await openObservation('venezuela');
      showView('dashboard');
      window.scrollTo({ top: 0, behavior: 'instant' });
    } catch(e) { console.warn('pre-warm:', e.message); }
  })()`);
  await sleep(1500);
  log('Pre-warm complete. Injecting HUD overlay...');

  await evaluate(`(() => {
    const overlay = document.createElement('div');
    overlay.id = 'video-hud-v3';
    overlay.style.cssText = 'position:fixed;top:24px;left:32px;z-index:999999;display:flex;flex-direction:column;gap:6px;pointer-events:none;font-family:monospace,system-ui,sans-serif;';
    overlay.innerHTML = \`
      <div id="hud-badge" style="background:rgba(10,25,47,0.88);border:1px solid rgba(0,229,255,0.4);border-left:4px solid #00E5FF;padding:7px 16px;border-radius:4px;backdrop-filter:blur(8px);display:inline-flex;align-items:center;gap:10px;">
        <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#00E5FF;box-shadow:0 0 8px #00E5FF;"></span>
        <span id="hud-title" style="color:#FFFFFF;font-weight:700;font-size:13px;letter-spacing:1px;">NISAR // EARTH IN MOTION</span>
        <span id="hud-subtitle" style="color:#64FFDA;font-size:11px;padding-left:8px;border-left:1px solid rgba(255,255,255,0.2);">SCENE 1</span>
      </div>
      <div id="hud-callout" style="display:none;background:rgba(5,12,28,0.92);border:1px solid rgba(100,255,218,0.3);padding:9px 14px;border-radius:4px;max-width:520px;color:#E2E8F0;font-size:11px;line-height:1.5;"></div>
    \`;
    document.body.appendChild(overlay);
  })()`);

  async function updateHud(title, subtitle, calloutHtml = null) {
    const escapedTitle = title.replace(/\\/g, '\\\\').replace(/"/g, '\\"');
    const escapedSub = subtitle.replace(/\\/g, '\\\\').replace(/"/g, '\\"');
    await evaluate(`(() => {
      const t = document.getElementById('hud-title');
      const s = document.getElementById('hud-subtitle');
      const c = document.getElementById('hud-callout');
      if (t) t.textContent = "${escapedTitle}";
      if (s) s.textContent = "${escapedSub}";
      if (c) {
        if (${JSON.stringify(calloutHtml)}) {
          c.innerHTML = ${JSON.stringify(calloutHtml)};
          c.style.display = 'block';
        } else {
          c.style.display = 'none';
        }
      }
    })()`);
  }

  // SCENE 1: 0.0s – 12.0s (360 frames: 1 to 360)
  log('Scene 1: Planetary Opening & Orbit (0-12s, 360 frames)...');
  await updateHud(
    'NISAR // EARTH IN MOTION',
    'PLANETARY OPENING · ~12-DAY REPEAT CYCLE',
    '<strong>MISSION:</strong> NASA-ISRO Synthetic Aperture Radar (NISAR)<br><strong>BAND:</strong> L-Band Microwave (1.239 GHz, λ ≈ 24.2 cm)<br><strong>CYCLE:</strong> ~12-day repeat (11d 23h 59m elapsed between acquisitions)<br><em>Illustrative Mission Visualization</em>'
  );
  for (let i = 0; i < 45; i++) {
    const buf = await snapFrame();
    duplicateFrames(buf, 8);
    await sleep(40);
  }
  while (currentFrameNumber <= 360) {
    const buf = await snapFrame();
    writeFrameFile(currentFrameNumber++, buf);
  }

  // SCENE 2: 12.0s – 25.0s (390 frames: 361 to 750)
  log('Scene 2: Research Challenge (12-25s, 390 frames)...');
  await evaluate("window.scrollTo({ top: 620, behavior: 'instant' })");
  await sleep(400);
  await updateHud(
    'RESEARCH CHALLENGE',
    'NORTHERN VENEZUELA 2026 · ~12-DAY BASELINE',
    '<strong>PERIOD:</strong> 2026-06-13 to 2026-06-25 (11d 23h 59m elapsed; ~12-day repeat cycle)<br><strong>EVENT SEQUENCE:</strong> 24 June 2026 Doublet (32.2s separation)<br><strong>FORESHOCK:</strong> M7.2 (San Felipe, Yaracuy) · <strong>MAINSHOCK:</strong> M7.5 (Catia La Mar)<br><strong>SEPARATION:</strong> 148.33 km · <strong>PRODUCT:</strong> NISAR Level-2 GUNW'
  );
  await evaluate(`(() => {
    const card = document.querySelector('#observation-cards .card');
    if (card) {
      card.style.outline = '2px solid #00E5FF';
      card.style.boxShadow = '0 0 24px rgba(0,229,255,0.4)';
    }
  })()`);

  // Move cursor towards the Venezuela observation card
  for (let s = 0; s < 10; s++) {
    await mouseMove(960 + s * 15, 500 + s * 15);
    await sleep(20);
  }

  for (let i = 0; i < 39; i++) {
    const buf = await snapFrame();
    duplicateFrames(buf, 10);
    await sleep(25);
  }
  while (currentFrameNumber <= 750) {
    const buf = await snapFrame();
    writeFrameFile(currentFrameNumber++, buf);
  }

  // SCENE 3: 25.0s – 38.0s (390 frames: 751 to 1140)
  log('Scene 3: Engineering Achievement (25-38s, 390 frames)...');
  await evaluate(`(async () => {
    showView('explorer');
    await openObservation('venezuela');
    window.scrollTo({ top: 0, behavior: 'instant' });
  })()`);
  await sleep(1500);
  await updateHud(
    'ENGINEERING ACHIEVEMENT',
    'HDF5 DIMENSION-SCALE RESOLUTION',
    '<strong>GRANULE SIZE:</strong> 2.34 GB HDF5<br><strong>GRID POSTING:</strong> 80 m × 80 m (4,149 × 4,239 pixels, EPSG:32619)<br><strong>BREAKTHROUGH:</strong> Direct resolution of attached DIMENSION_LIST scales eliminates 4× wrapped coordinate mismatch.'
  );

  for (let i = 0; i < 39; i++) {
    const buf = await snapFrame();
    duplicateFrames(buf, 10);
    await sleep(25);
  }
  while (currentFrameNumber <= 1140) {
    const buf = await snapFrame();
    writeFrameFile(currentFrameNumber++, buf);
  }

  // SCENE 4: 38.0s – 60.0s (660 frames: 1141 to 1800)
  log('Scene 4: Interactive Scientific Explorer (38-60s, 660 frames)...');

  // 4A: Phase Pixel Inspection (38-44s: 180 frames)
  await updateHud(
    'SCIENTIFIC EXPLORER',
    'UNWRAPPED PHASE · RADIANS (MULTI-CYCLE)',
    '<strong>UNITS:</strong> Radians (native product unit, spans multiple 2π cycles)<br><strong>COLORMAP:</strong> Viridis (sequential)<br><strong>OBSERVATION:</strong> Phase range 2.63 – 33.79 rad after ellipsoidal flattening.'
  );
  for (let step = 0; step < 12; step++) {
    await mouseMove(520 + step * 25, 420 + step * 8);
    await sleep(25);
  }
  for (let i = 0; i < 18; i++) {
    const buf = await snapFrame();
    duplicateFrames(buf, 10);
    await sleep(20);
  }

  // 4B: Coherence Layer Switch & Slider Drag (44-50s: 180 frames)
  await evaluate(`(() => {
    const tab = document.querySelector('#layer-tabs [data-layer="coherence"]');
    if (tab) tab.click();
  })()`);
  await sleep(400);
  await updateHud(
    'SCIENTIFIC EXPLORER',
    'COHERENCE THRESHOLD · MEASUREMENT QUALITY',
    '<strong>METRIC:</strong> Coherence magnitude (0.0–1.0)<br><strong>THRESHOLD:</strong> 0.4 filter isolates ~16.7% reliable pixels<br><strong>PURPOSE:</strong> Masks temporal and vegetation decorrelation.'
  );
  await mouseMove(500, 920);
  await mouseDown(500, 920);
  for (let step = 0; step <= 8; step++) {
    await mouseMove(500 + step * 35, 920);
    await sleep(25);
  }
  await evaluate(`(() => {
    const slider = document.getElementById('threshold-slider');
    if (slider) {
      slider.value = '0.4';
      slider.dispatchEvent(new Event('input', { bubbles: true }));
      slider.dispatchEvent(new Event('change', { bubbles: true }));
    }
  })()`);
  await mouseUp(500, 920);
  await sleep(200);
  for (let i = 0; i < 18; i++) {
    const buf = await snapFrame();
    duplicateFrames(buf, 10);
    await sleep(20);
  }

  // 4C: M7.2 Foreshock Inspection (50-55s: 150 frames)
  await updateHud(
    'EVENT INSPECTION',
    'M7.2 FORESHOCK · 1.6 KM MEDIAN COHERENCE 0.406',
    '<strong>LOCATION:</strong> 20 km E of San Felipe, Yaracuy (10.37°N, 68.56°W)<br><strong>LOCAL COHERENCE:</strong> 0.406 median (1.6 km window)<br><strong>STATUS:</strong> Usable phase relationship preserved.'
  );
  await mouseMove(660, 525);
  await sleep(200);
  await evaluate(`(() => {
    const tip = document.createElement('div');
    tip.id = 'demo-event-tip-v3';
    tip.style.cssText = 'position:fixed;bottom:130px;left:440px;z-index:99999;background:rgba(5,12,28,0.96);border:1px solid #64FFDA;padding:10px 16px;border-radius:6px;color:#FFFFFF;font-family:monospace;font-size:12px;box-shadow:0 0 20px rgba(100,255,218,0.4);';
    tip.innerHTML = '<strong>USGS EVENT: M7.2 Foreshock (us6000t7zc)</strong><br>Coords: 10.3713°N, 68.5564°W | Depth: 10.0 km<br>1.6 km Window Median Coherence: <strong>0.406</strong> (usable phase)';
    document.body.appendChild(tip);
  })()`);
  for (let i = 0; i < 15; i++) {
    const buf = await snapFrame();
    duplicateFrames(buf, 10);
    await sleep(20);
  }

  // 4D: M7.5 Mainshock Inspection (55-60s: 150 frames)
  await updateHud(
    'EVENT INSPECTION',
    'M7.5 MAINSHOCK · 1.6 KM MEDIAN COHERENCE 0.077',
    '<strong>LOCATION:</strong> 20 km W of Catia La Mar (10.60°N, 67.22°W)<br><strong>SEPARATION:</strong> 148.33 km ENE along coastal fault system<br><strong>COHERENCE:</strong> 0.077 median (severe coastal decorrelation; phase unreliable).'
  );
  await evaluate(`(() => {
    const tip = document.getElementById('demo-event-tip-v3');
    if (tip) {
      tip.style.left = '600px';
      tip.style.bottom = '150px';
      tip.style.borderColor = '#FF5252';
      tip.style.boxShadow = '0 0 20px rgba(255,82,82,0.4)';
      tip.innerHTML = '<strong>USGS EVENT: M7.5 Mainshock (us6000t7zp)</strong><br>Coords: 10.5955°N, 67.2205°W | Depth: 10.0 km<br>1.6 km Window Median Coherence: <strong>0.077</strong> (severe decorrelation)';
    }
  })()`);
  await mouseMove(820, 510);
  await sleep(200);
  for (let i = 0; i < 15; i++) {
    const buf = await snapFrame();
    duplicateFrames(buf, 10);
    await sleep(20);
  }
  await evaluate(`(() => {
    const tip = document.getElementById('demo-event-tip-v3');
    if (tip) tip.remove();
  })()`);
  while (currentFrameNumber <= 1800) {
    const buf = await snapFrame();
    writeFrameFile(currentFrameNumber++, buf);
  }

  // SCENE 5: 60.0s – 78.0s (540 frames: 1801 to 2340)
  log('Scene 5: Scientific Integrity & Real Export (60-78s, 540 frames)...');
  await evaluate("window.scrollTo({ top: 920, behavior: 'instant' })");
  await sleep(400);
  await updateHud(
    'SCIENTIFIC HONESTY & GUARDRAILS',
    'INTERPRETATION: NOT VALIDATED',
    '<strong>1. NO ARBITRARY DISPLACEMENT:</strong> Sign convention unvalidated; phase in radians.<br><strong>2. NO GPS ZERO-ANCHOR:</strong> Relative interferometry requires ground truth.<br><strong>3. ATMOSPHERIC DELAYS:</strong> Water vapor & ionosphere remain in phase.<br><strong>4. RESIDUAL RAMPS:</strong> Orbital geometry errors present.'
  );
  for (let i = 0; i < 24; i++) {
    const buf = await snapFrame();
    duplicateFrames(buf, 10);
    await sleep(20);
  }

  // Scroll to Export panel and trigger real export click
  await evaluate("window.scrollTo({ top: 1450, behavior: 'instant' })");
  await sleep(400);
  await updateHud(
    'REPRODUCIBLE DATA EXPORT',
    'GEOTIFF · QUICKLOOK · JSON · MARKDOWN',
    '<strong>GeoTIFF:</strong> Georeferenced EPSG:32619 raster for QGIS/ArcGIS<br><strong>Quicklook:</strong> Publication PNG with embedded provenance metadata footer<br><strong>Scientific Report:</strong> Comprehensive audit trail and parameters in Markdown.'
  );

  await mouseMove(720, 850);
  await sleep(150);
  await evaluate(`(() => {
    const btn = document.querySelector('[data-download-json]');
    if (btn) {
      btn.style.outline = '2px solid #00E5FF';
      btn.style.boxShadow = '0 0 16px rgba(0,229,255,0.6)';
      btn.click();
    }
  })()`);
  await sleep(200);

  for (let i = 0; i < 30; i++) {
    const buf = await snapFrame();
    duplicateFrames(buf, 10);
    await sleep(20);
  }
  while (currentFrameNumber <= 2340) {
    const buf = await snapFrame();
    writeFrameFile(currentFrameNumber++, buf);
  }

  // SCENE 6: 78.0s – 90.0s (360 frames: 2341 to 2700)
  log('Scene 6: Mission Closing (78-90s, 360 frames, clean card, 0.5s fade)...');
  await evaluate(`(async () => {
    showView('dashboard');
    window.scrollTo({ top: 0, behavior: 'instant' });
    const hud = document.getElementById('video-hud-v3');
    if (hud) hud.style.display = 'none';
  })()`);
  await sleep(500);

  await evaluate(`(() => {
    const card = document.createElement('div');
    card.id = 'closing-card-v3';
    card.style.cssText = 'position:fixed;inset:0;z-index:9999999;background:radial-gradient(ellipse at center, rgba(10,25,47,0.97) 0%, rgba(2,6,18,0.99) 100%);display:flex;flex-direction:column;align-items:center;justify-content:center;font-family:system-ui,-apple-system,sans-serif;color:#FFFFFF;text-align:center;transition:opacity 0.5s ease-out;';
    card.innerHTML = \`
      <div style="font-size:13px;font-weight:700;letter-spacing:4px;color:#00E5FF;margin-bottom:12px;text-transform:uppercase;">NASA Space Apps Challenge 2026 · Dancing with the SARs</div>
      <h1 style="font-size:54px;font-weight:900;letter-spacing:2px;margin:0 0 16px 0;background:linear-gradient(135deg,#FFFFFF 0%,#E2E8F0 60%,#64FFDA 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;">NISAR // EARTH IN MOTION</h1>
      <p style="font-size:18px;color:#94A3B8;max-width:680px;line-height:1.6;margin:0 0 32px 0;">Transforming raw NASA-ISRO Synthetic Aperture Radar products into transparent, rigorous, and accessible Earth science.</p>
      <div style="display:flex;gap:16px;margin-bottom:36px;">
        <span style="background:rgba(0,229,255,0.1);border:1px solid rgba(0,229,255,0.4);padding:8px 16px;border-radius:6px;font-size:13px;font-family:monospace;color:#00E5FF;">EPSG:32619 · 80 m Grid</span>
        <span style="background:rgba(100,255,218,0.1);border:1px solid rgba(100,255,218,0.4);padding:8px 16px;border-radius:6px;font-size:13px;font-family:monospace;color:#64FFDA;">HDF5 Dimension Scales</span>
        <span style="background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.2);padding:8px 16px;border-radius:6px;font-size:13px;font-family:monospace;color:#F8FAFC;">~12-Day Repeat · L-Band 1.239 GHz</span>
        <span style="background:rgba(0,229,255,0.08);border:1px solid rgba(0,229,255,0.3);padding:8px 16px;border-radius:6px;font-size:13px;font-family:monospace;color:#38BDF8;">100% Offline Capable</span>
      </div>
      <div style="font-family:monospace;font-size:15px;color:#64FFDA;padding:10px 24px;border:1px solid rgba(100,255,218,0.4);border-radius:8px;background:rgba(5,12,28,0.8);">
        github.com/Aayushashsahu/LunaHorizon
      </div>
    \`;
    document.body.appendChild(card);
  })()`);
  await sleep(400);

  // Capture closing card at full opacity until frame 2685 (89.5s)
  const titleBuf = await snapFrame();
  duplicateFrames(titleBuf, 345);

  // Gentle 0.5s fade out for last 15 frames (89.5s to 90.0s)
  await evaluate(`(() => {
    const card = document.getElementById('closing-card-v3');
    if (card) card.style.opacity = '0';
  })()`);
  await sleep(300);
  const fadeBuf = await snapFrame();
  duplicateFrames(fadeBuf, 15);

  child.kill();
  try { rmSync(profile, { recursive: true, force: true }); } catch {}
  log(`Frame capture complete! Total frames: ${currentFrameNumber - 1}`);
}

function encodeFinalVideo() {
  log('Encoding V3 1080p 30 FPS MP4 with FFmpeg (CRF 19, BT.709)...');
  const framesPattern = 'artifacts/demo/temp_v3/frames/frame_%05d.jpg';
  const audioPath = 'artifacts/demo/audio_v3/master_audio_v3.m4a';
  const assPath = 'subtitles_v3.ass';
  const outMp4 = 'artifacts/demo/nisar_earth_in_motion_demo_v3.mp4';

  const ffmpegCmd = [
    'ffmpeg -y',
    `-framerate ${FPS}`,
    `-i "${framesPattern}"`,
    `-i "${audioPath}"`,
    `-vf "ass=${assPath}"`,
    '-c:v libx264 -preset fast -profile:v high -level 4.2 -pix_fmt yuv420p -crf 19',
    '-colorspace bt709 -color_primaries bt709 -color_trc bt709',
    '-c:a copy',
    `-t ${TOTAL_SECONDS}`,
    '-movflags +faststart',
    `"${outMp4}"`,
  ].join(' ');

  log(`Running: ${ffmpegCmd}`);
  execSync(ffmpegCmd, { stdio: 'inherit' });
  log(`V3 video rendered -> ${outMp4}`);
}

function validateAndExtractFrames() {
  log('Validating V3 MP4 with ffprobe...');
  const outPath = OUTPUT_MP4;
  if (!existsSync(outPath)) throw new Error(`V3 not found: ${outPath}`);

  const probeJson = execSync(
    `ffprobe -v error -print_format json -show_format -show_streams "${outPath}"`,
    { encoding: 'utf-8' }
  );
  const probe = JSON.parse(probeJson);
  const vStream = probe.streams.find((s) => s.codec_type === 'video');
  const aStream = probe.streams.find((s) => s.codec_type === 'audio');
  const duration = parseFloat(probe.format.duration);

  log('=== V3 VIDEO VERIFICATION ===');
  log(`Path:          ${outPath}`);
  log(`File Size:     ${(Number(probe.format.size) / (1024 * 1024)).toFixed(2)} MiB`);
  log(`Duration:      ${duration.toFixed(3)} s (target: 90.000 s)`);
  log(`Resolution:    ${vStream.width} x ${vStream.height}`);
  log(`Frame Rate:    ${vStream.r_frame_rate}`);
  log(`Video Codec:   ${vStream.codec_name} (${vStream.profile})`);
  log(`Audio Codec:   ${aStream?.codec_name ?? 'NONE'}`);
  log(`Sample Rate:   ${aStream?.sample_rate ?? '—'} Hz`);
  log(`Channels:      ${aStream?.channels ?? 0}`);

  if (vStream.width !== 1920 || vStream.height !== 1080) throw new Error('Bad resolution');
  if (Math.abs(duration - TOTAL_SECONDS) > 1.5) throw new Error('Bad duration');
  if (!aStream || String(aStream.sample_rate) !== '48000') throw new Error('Bad audio sample rate');
  if (aStream.channels !== 2) throw new Error('Bad audio channels');

  log('Extracting V3 verification frames at every 5s...');
  const outDir = 'artifacts/demo';
  const secondsToExtract = [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 89];
  for (const sec of secondsToExtract) {
    const hh = String(Math.floor(sec / 3600)).padStart(2, '0');
    const mm = String(Math.floor((sec % 3600) / 60)).padStart(2, '0');
    const ss = String(sec % 60).padStart(2, '0');
    const timeStr = `${hh}:${mm}:${ss}`;
    const framePath = `${outDir}/v3_frame_${String(sec).padStart(2, '0')}s.jpg`;
    execSync(`ffmpeg -y -ss ${timeStr} -i "${outPath}" -vframes 1 "${framePath}"`, { stdio: 'ignore' });
  }

  log('Generating 6-panel contact sheet (3x2)...');
  execSync(
    `ffmpeg -y -i "${outPath}" -vf "select='not(mod(n\\,450))',scale=640:360,tile=3x2" -frames:v 1 "${outDir}/v3_contact_sheet.jpg"`,
    { stdio: 'ignore' }
  );

  log('Verification frames and contact sheet extracted.');
}

async function main() {
  try {
    log('=== STARTING LUNAHORIZON DEMO VIDEO V3 MASTER PRODUCTION ===');
    ensureDirectories();
    await captureApplicationFrames();
    encodeFinalVideo();
    validateAndExtractFrames();
    log('=== V3 MASTER PRODUCTION COMPLETED SUCCESSFULLY ===');
  } catch (err) {
    console.error('FATAL ERROR in V3 master production:', err);
    process.exit(1);
  }
}

main();
