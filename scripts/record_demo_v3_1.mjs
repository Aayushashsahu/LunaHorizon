#!/usr/bin/env node
/**
 * record_demo_v3_1.mjs — NISAR // Earth in Motion — Demo Video V3.1 (Final Submission Production)
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

const REPO_ROOT = resolve('D:/Nasa hackton');
const BASE_URL = process.env.NISAR_BASE_URL || 'http://127.0.0.1:8000';
const OUTPUT_MP4 = resolve(REPO_ROOT, 'artifacts/demo/nisar_earth_in_motion_demo_v3_1.mp4');
const TEMP_DIR = resolve(REPO_ROOT, 'artifacts/demo/temp_v3_1');
const FRAMES_DIR = resolve(TEMP_DIR, 'frames');
const AUDIO_DIR = resolve(REPO_ROOT, 'artifacts/demo/audio_v3_1');
const MASTER_AUDIO = resolve(AUDIO_DIR, 'master_audio_v3_1.m4a');
const SUBTITLES_ASS = resolve(REPO_ROOT, 'submission', 'video', 'subtitles_v3_1.ass');

const CHROME_PATH =
  process.env.CHROME_PATH || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';

const TOTAL_SECONDS = 90;
const FPS = 30;
const TOTAL_FRAMES = TOTAL_SECONDS * FPS; // 2700 frames

function log(msg) {
  process.stdout.write(`[record_v3_1] ${msg}\n`);
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

  const profile = mkdtempSync(join(tmpdir(), 'nisar-v3-1-'));
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
    overlay.id = 'video-hud-v3-1';
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

  // SCENE 1: 0.0s – 11.7s (351 frames: 1 to 351)
  log('Scene 1: Planetary Opening & Orbit (0-11.7s, 351 frames)...');
  await updateHud(
    'NISAR // EARTH IN MOTION',
    'PLANETARY OPENING · ~12-DAY REPEAT CYCLE',
    '<strong>MISSION:</strong> NASA-ISRO Synthetic Aperture Radar (NISAR)<br><strong>BAND:</strong> L-Band Microwave (1.239 GHz, λ ≈ 24.2 cm)<br><strong>CYCLE:</strong> ~12-day repeat (11d 23h 59m elapsed between acquisitions)<br><em>Illustrative Mission Visualization</em>'
  );
  for (let i = 0; i < 44; i++) {
    const buf = await snapFrame();
    duplicateFrames(buf, 8);
    await sleep(40);
  }
  while (currentFrameNumber <= 351) {
    const buf = await snapFrame();
    writeFrameFile(currentFrameNumber++, buf);
  }

  // SCENE 2: 11.7s – 25.3s (408 frames: 352 to 759)
  log('Scene 2: Research Challenge (11.7-25.3s, 408 frames)...');
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

  // Move cursor towards the Venezuela observation card and CTA button
  for (let s = 0; s < 12; s++) {
    await mouseMove(960 + s * 12, 500 + s * 14);
    await sleep(20);
  }

  for (let i = 0; i < 40; i++) {
    const buf = await snapFrame();
    duplicateFrames(buf, 10);
    await sleep(25);
  }

  // Click CTA to trigger transition
  await evaluate(`(() => {
    const cta = document.querySelector('#observation-cards [data-open="venezuela"]') || document.getElementById('open-explorer');
    if (cta) cta.click();
  })()`);
  await sleep(300);

  while (currentFrameNumber <= 759) {
    const buf = await snapFrame();
    writeFrameFile(currentFrameNumber++, buf);
  }

  // SCENE 3: 25.3s – 38.6s (399 frames: 760 to 1158)
  log('Scene 3: Engineering Achievement (25.3-38.6s, 399 frames)...');
  await evaluate(`(async () => {
    showView('explorer');
    await openObservation('venezuela');
    window.scrollTo({ top: 0, behavior: 'instant' });
  })()`);
  await sleep(1500);
  await updateHud(
    'ENGINEERING ACHIEVEMENT',
    'HDF5 DIMENSION-SCALE RESOLUTION',
    '<strong>GRANULE SIZE:</strong> 2.34 GB HDF5<br><strong>GRID POSTING:</strong> 80 m × 80 m (4,149 × 4,239 pixels, EPSG:32619)<br><strong>BASELINE:</strong> ~12 days (11d 23h 59m elapsed)<br><strong>BREAKTHROUGH:</strong> Direct resolution of attached DIMENSION_LIST scales eliminates 4× wrapped coordinate mismatch.'
  );

  for (let i = 0; i < 40; i++) {
    const buf = await snapFrame();
    duplicateFrames(buf, 10);
    await sleep(25);
  }
  while (currentFrameNumber <= 1158) {
    const buf = await snapFrame();
    writeFrameFile(currentFrameNumber++, buf);
  }

  // SCENE 4: 38.6s – 58.6s (600 frames: 1159 to 1758)
  log('Scene 4: Interactive Scientific Explorer (38.6-58.6s, 600 frames)...');

  // 4A: Phase Pixel Inspection (38.6-44.0s: 162 frames)
  await updateHud(
    'SCIENTIFIC EXPLORER',
    'UNWRAPPED PHASE · RADIANS (MULTI-CYCLE)',
    '<strong>UNITS:</strong> Radians (native product unit, spans multiple 2π cycles)<br><strong>COLORMAP:</strong> Viridis (sequential)<br><strong>PIXEL INSPECTION:</strong> Real-time full-resolution Float32 coordinate & phase sampling.'
  );
  // Real mouse movement triggering live sampleAt
  for (let step = 0; step < 16; step++) {
    const mx = 520 + step * 20;
    const my = 420 + step * 6;
    await mouseMove(mx, my);
    await sleep(25);
  }
  for (let i = 0; i < 16; i++) {
    const buf = await snapFrame();
    duplicateFrames(buf, 10);
    await sleep(20);
  }

  // 4B: Coherence Layer Switch & Slider Drag (44.0-49.5s: 165 frames)
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
  for (let i = 0; i < 16; i++) {
    const buf = await snapFrame();
    duplicateFrames(buf, 10);
    await sleep(20);
  }

  // 4C: M7.2 Foreshock Inspection (49.5-54.0s: 135 frames)
  await updateHud(
    'EVENT INSPECTION',
    'M7.2 FORESHOCK · 1.6 KM MEDIAN COHERENCE 0.406',
    '<strong>LOCATION:</strong> 20 km E of San Felipe, Yaracuy (10.37°N, 68.56°W)<br><strong>LOCAL COHERENCE:</strong> 0.406 median (1.6 km window)<br><strong>STATUS:</strong> Usable phase relationship preserved.'
  );
  // Trigger real locateEvent(0) in application
  await evaluate(`(() => {
    if (typeof locateEvent === 'function') locateEvent(0);
    const item = document.querySelector('#event-list .case-card, #event-list .event-item');
    if (item) item.classList.add('is-active');
  })()`);
  await mouseMove(660, 525);
  await sleep(250);
  for (let i = 0; i < 13; i++) {
    const buf = await snapFrame();
    duplicateFrames(buf, 10);
    await sleep(20);
  }

  // 4D: M7.5 Mainshock Inspection (54.0-58.6s: 138 frames)
  await updateHud(
    'EVENT INSPECTION',
    'M7.5 MAINSHOCK · 1.6 KM MEDIAN COHERENCE 0.077',
    '<strong>LOCATION:</strong> 20 km W of Catia La Mar (10.60°N, 67.22°W)<br><strong>SEPARATION:</strong> 148.33 km ENE along coastal fault system<br><strong>COHERENCE:</strong> 0.077 median (severe coastal decorrelation; phase unreliable).'
  );
  // Trigger real locateEvent(1) in application
  await evaluate(`(() => {
    if (typeof locateEvent === 'function') locateEvent(1);
    const items = document.querySelectorAll('#event-list .case-card, #event-list .event-item');
    if (items.length > 1) items[1].classList.add('is-active');
  })()`);
  await mouseMove(820, 510);
  await sleep(250);
  for (let i = 0; i < 14; i++) {
    const buf = await snapFrame();
    duplicateFrames(buf, 10);
    await sleep(20);
  }
  while (currentFrameNumber <= 1758) {
    const buf = await snapFrame();
    writeFrameFile(currentFrameNumber++, buf);
  }

  // SCENE 5: 58.6s – 74.0s (462 frames: 1759 to 2220)
  log('Scene 5: Scientific Integrity & Real Export (58.6-74.0s, 462 frames)...');
  await evaluate("window.scrollTo({ top: 920, behavior: 'instant' })");
  await sleep(400);
  await updateHud(
    'SCIENTIFIC HONESTY & GUARDRAILS',
    'INTERPRETATION: NOT VALIDATED',
    '<strong>1. NO ARBITRARY DISPLACEMENT:</strong> Sign convention unvalidated; phase in radians.<br><strong>2. NO GPS ZERO-ANCHOR:</strong> Relative interferometry requires ground truth.<br><strong>3. ATMOSPHERIC DELAYS:</strong> Water vapor & ionosphere remain in phase.<br><strong>4. RESIDUAL RAMPS:</strong> Orbital geometry errors present.'
  );
  for (let i = 0; i < 28; i++) {
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
  await sleep(250);

  for (let i = 0; i < 18; i++) {
    const buf = await snapFrame();
    duplicateFrames(buf, 10);
    await sleep(20);
  }
  while (currentFrameNumber <= 2220) {
    const buf = await snapFrame();
    writeFrameFile(currentFrameNumber++, buf);
  }

  // SCENE 6: 74.0s – 90.0s (480 frames: 2221 to 2700)
  log('Scene 6: Mission Closing (74.0-90.0s, 480 frames, clean card, 0.5s fade)...');
  await evaluate(`(() => {
    const oldHud = document.getElementById('video-hud-v3-1');
    if (oldHud) oldHud.remove();

    const card = document.createElement('div');
    card.id = 'closing-card-v3-1';
    card.style.cssText = 'position:fixed;inset:0;background:#050C1C;z-index:9999999;display:flex;flex-direction:column;align-items:center;justify-content:center;font-family:system-ui,-apple-system,sans-serif;text-align:center;color:#FFFFFF;padding:40px;opacity:1;transition:opacity 0.5s ease;';
    card.innerHTML = \`
      <div style="font-size:13px;letter-spacing:4px;color:#00E5FF;font-weight:700;margin-bottom:14px;text-transform:uppercase;">NASA Space Apps Challenge 2026 · Dancing with the SARs</div>
      <h1 style="font-size:46px;font-weight:800;letter-spacing:1px;margin:0 0 14px 0;background:linear-gradient(135deg, #FFFFFF 0%, #64FFDA 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;">NISAR // EARTH IN MOTION</h1>
      <p style="font-size:17px;color:#94A3B8;max-width:720px;line-height:1.6;margin:0 0 28px 0;">Interactive, Scientifically Defensible Analysis of NASA-ISRO Synthetic Aperture Radar Level-2 Geocoded Unwrapped Interferograms</p>
      
      <div style="display:flex;gap:16px;margin-bottom:32px;">
        <span style="background:rgba(0,229,255,0.12);border:1px solid rgba(0,229,255,0.3);padding:8px 18px;border-radius:6px;font-size:12px;color:#64FFDA;font-family:monospace;">EPSG:32619 · 80 m Grid</span>
        <span style="background:rgba(0,229,255,0.12);border:1px solid rgba(0,229,255,0.3);padding:8px 18px;border-radius:6px;font-size:12px;color:#64FFDA;font-family:monospace;">HDF5 Dimension Scales</span>
        <span style="background:rgba(0,229,255,0.12);border:1px solid rgba(0,229,255,0.3);padding:8px 18px;border-radius:6px;font-size:12px;color:#64FFDA;font-family:monospace;">~12-Day Repeat</span>
        <span style="background:rgba(0,229,255,0.12);border:1px solid rgba(0,229,255,0.3);padding:8px 18px;border-radius:6px;font-size:12px;color:#64FFDA;font-family:monospace;">100% Offline Capable</span>
      </div>

      <div style="background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.15);padding:14px 32px;border-radius:8px;">
        <span style="color:#94A3B8;font-size:13px;margin-right:12px;">REPOSITORY:</span>
        <span style="color:#FFFFFF;font-family:monospace;font-size:15px;font-weight:600;">github.com/Aayushashsahu/LunaHorizon</span>
      </div>
    \`;
    document.body.appendChild(card);
  })()`);

  // Hold card at 100% opacity for frames 2221 to 2685 (89.5s)
  const cardHoldBuf = await snapFrame();
  const holdCount = 2685 - currentFrameNumber + 1;
  duplicateFrames(cardHoldBuf, holdCount);

  // Fade out to black in final 15 frames (89.5s to 90.0s)
  log('Triggering 0.5s fade to black...');
  await evaluate(`(() => {
    const card = document.getElementById('closing-card-v3-1');
    if (card) card.style.opacity = '0';
  })()`);
  await sleep(100);

  for (let f = 0; f < 15; f++) {
    if (currentFrameNumber <= TOTAL_FRAMES) {
      const buf = await snapFrame();
      writeFrameFile(currentFrameNumber++, buf);
      await sleep(30);
    }
  }

  log(`Frame capture complete. Generated ${currentFrameNumber - 1} frames.`);

  child.kill();
  try {
    rmSync(profile, { recursive: true, force: true });
  } catch {}
}

function renderMasterVideo() {
  log('Encoding Master Video V3.1 with FFmpeg...');

  // Using -pix_fmt yuv420p for universal compatibility, CRF 18 for pristine scientific text, BT.709 metadata
  const subEscaped = SUBTITLES_ASS.replace(/\\/g, '/').replace(/:/g, '\\:');
  const cmd = `ffmpeg -y -framerate 30 -i "${FRAMES_DIR.replace(/\\/g, '/')}/frame_%05d.jpg" -i "${MASTER_AUDIO.replace(/\\/g, '/')}" -vf "ass='${subEscaped}',scale=out_color_matrix=bt709:out_range=tv,format=yuv420p" -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p -color_range tv -colorspace bt709 -color_primaries bt709 -color_trc bt709 -c:a copy -movflags +faststart "${OUTPUT_MP4.replace(/\\/g, '/')}"`;

  log(`Executing: ${cmd}`);
  execSync(cmd, { stdio: 'inherit' });
  log(`Master Video V3.1 rendered successfully: ${OUTPUT_MP4}`);
}

async function main() {
  ensureDirectories();
  await captureApplicationFrames();
  renderMasterVideo();
}

main().catch((err) => {
  console.error('[record_v3_1] FATAL:', err);
  process.exit(1);
});
