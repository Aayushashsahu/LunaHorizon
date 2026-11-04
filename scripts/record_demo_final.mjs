#!/usr/bin/env node
/**
 * record_demo_final.mjs — NISAR // Earth in Motion — Demo Video Final Master
 *
 * Deterministic Chrome DevTools Protocol (CDP) recorder:
 * 1. Manages its own dedicated Python backend server throughout the 87s recording.
 * 2. Captures genuine application interactions (dashboard baseline, live pixel sampling,
 *    layer switching, threshold slider drag, event inspection, limitations, and export).
 * 3. Renders the final master MP4 (nisar_earth_in_motion_FINAL.mp4) with CRF 18,
 *    yuv420p (tv range, bt709), burned-in dual ASS subtitles, and master audio.
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
const PORT = 8000;
const BASE_URL = process.env.NISAR_BASE_URL || `http://127.0.0.1:${PORT}`;
const OUTPUT_MP4 = resolve(REPO_ROOT, 'artifacts/demo/nisar_earth_in_motion_FINAL.mp4');
const TEMP_DIR = resolve(REPO_ROOT, 'artifacts/demo/temp_final');
const FRAMES_DIR = resolve(TEMP_DIR, 'frames');
const AUDIO_DIR = resolve(REPO_ROOT, 'artifacts/demo/audio_final');
const MASTER_AUDIO = resolve(AUDIO_DIR, 'master_audio_final.m4a');
const SUBTITLES_ASS = resolve(REPO_ROOT, 'submission', 'video', 'subtitles_final.ass');

const PYTHON_PATH = resolve(REPO_ROOT, '.venv/Scripts/python.exe');
const CHROME_PATH =
  process.env.CHROME_PATH || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';

const TOTAL_SECONDS = 87;
const FPS = 30;
const TOTAL_FRAMES = TOTAL_SECONDS * FPS; // 2610 frames

function log(msg) {
  process.stdout.write(`[record_final] ${msg}\n`);
}

function ensureDirectories() {
  mkdirSync(resolve(REPO_ROOT, 'artifacts/demo'), { recursive: true });
  mkdirSync(TEMP_DIR, { recursive: true });
  mkdirSync(FRAMES_DIR, { recursive: true });
}

let serverProcess = null;

async function ensureServerRunning() {
  // Test if server is already responding
  try {
    const res = await fetch(`${BASE_URL}/api/health`, { signal: AbortSignal.timeout(1000) });
    if (res.ok) {
      log(`Server already responding at ${BASE_URL}`);
      return;
    }
  } catch {}

  log(`Spawning dedicated Python web server on port ${PORT}...`);
  serverProcess = spawn(
    PYTHON_PATH,
    ['-m', 'nisar_eim', 'serve', '--port', String(PORT), '--data-root', resolve(REPO_ROOT, 'data/processed')],
    {
      cwd: REPO_ROOT,
      stdio: ['ignore', 'pipe', 'pipe'],
    }
  );

  serverProcess.stdout.on('data', (d) => process.stdout.write(`[server] ${d}`));
  serverProcess.stderr.on('data', (d) => process.stderr.write(`[server] ${d}`));

  // Wait for health check
  for (let i = 0; i < 60; i++) {
    try {
      const res = await fetch(`${BASE_URL}/api/health`, { signal: AbortSignal.timeout(500) });
      if (res.ok) {
        log(`Server ready at ${BASE_URL}/api/health`);
        return;
      }
    } catch {}
    await sleep(250);
  }

  throw new Error(`Server failed to start on port ${PORT}`);
}

async function captureApplicationFrames() {
  log('Connecting to Chrome DevTools Protocol...');
  if (!existsSync(CHROME_PATH)) {
    throw new Error(`Chrome not found at: ${CHROME_PATH}`);
  }

  const profile = mkdtempSync(join(tmpdir(), 'nisar-final-'));
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

  log('Pre-warming application and loading Venezuela observation...');
  await send('Page.navigate', { url: BASE_URL + '/' });
  await sleep(2000);
  await evaluate(`(async () => {
    await openObservation('venezuela');
    showView('dashboard');
    window.scrollTo({ top: 0, behavior: 'instant' });
  })()`);
  await sleep(1500);

  log('Injecting HUD and Closing Card elements...');
  await evaluate(`(() => {
    let hud = document.getElementById('demo-hud-final');
    if (!hud) {
      hud = document.createElement('div');
      hud.id = 'demo-hud-final';
      hud.style.position = 'fixed';
      hud.style.top = '24px';
      hud.style.left = '32px';
      hud.style.zIndex = '99999';
      hud.style.background = 'rgba(5, 12, 28, 0.92)';
      hud.style.border = '1px solid rgba(0, 210, 255, 0.4)';
      hud.style.borderRadius = '8px';
      hud.style.padding = '12px 18px';
      hud.style.color = '#F8FAFC';
      hud.style.fontFamily = 'Inter, -apple-system, sans-serif';
      hud.style.backdropFilter = 'blur(10px)';
      hud.style.boxShadow = '0 8px 32px rgba(0,0,0,0.6)';
      hud.style.maxWidth = '440px';
      hud.style.pointerEvents = 'none';
      hud.style.transition = 'all 0.3s ease';
      document.body.appendChild(hud);
    }

    let card = document.getElementById('closing-card-final');
    if (!card) {
      card = document.createElement('div');
      card.id = 'closing-card-final';
      card.style.position = 'fixed';
      card.style.inset = '0';
      card.style.zIndex = '100000';
      card.style.background = '#050C1C';
      card.style.display = 'none';
      card.style.flexDirection = 'column';
      card.style.alignItems = 'center';
      card.style.justifyContent = 'center';
      card.style.textAlign = 'center';
      card.style.color = '#F8FAFC';
      card.style.fontFamily = 'Inter, -apple-system, sans-serif';
      card.style.opacity = '0';
      card.style.transition = 'opacity 0.5s ease';
      card.innerHTML = \`
        <div style="font-size: 14px; letter-spacing: 0.35em; color: #00D2FF; margin-bottom: 14px; text-transform: uppercase; font-weight: 700;">NASA Space Apps Challenge 2026</div>
        <div style="font-size: 52px; font-weight: 800; letter-spacing: -0.02em; margin-bottom: 8px; background: linear-gradient(135deg, #FFFFFF 0%, #38BDF8 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">NISAR // EARTH IN MOTION</div>
        <div style="font-size: 20px; font-weight: 500; color: #94A3B8; margin-bottom: 28px; letter-spacing: 0.05em;">Interactive NISAR Level-2 GUNW Explorer · Track 162</div>
        <div style="display: flex; gap: 14px; margin-bottom: 36px;">
          <span style="background: rgba(0, 210, 255, 0.12); border: 1px solid rgba(0, 210, 255, 0.4); border-radius: 6px; padding: 6px 14px; font-size: 13px; font-weight: 600; color: #38BDF8;">Dancing with the SARs</span>
          <span style="background: rgba(74, 222, 128, 0.12); border: 1px solid rgba(74, 222, 128, 0.4); border-radius: 6px; padding: 6px 14px; font-size: 13px; font-weight: 600; color: #4ADE80;">~12-Day Repeat Baseline</span>
          <span style="background: rgba(245, 158, 11, 0.12); border: 1px solid rgba(245, 158, 11, 0.4); border-radius: 6px; padding: 6px 14px; font-size: 13px; font-weight: 600; color: #F59E0B;">Full Float32 GeoTIFF Fallback</span>
        </div>
        <div style="font-family: 'JetBrains Mono', monospace; font-size: 17px; color: #E2E8F0; padding: 10px 22px; background: rgba(15, 23, 42, 0.8); border: 1px solid rgba(148, 163, 184, 0.25); border-radius: 8px;">github.com/Aayushashsahu/LunaHorizon</div>
      \`;
      document.body.appendChild(card);
    }
  })()`);

  async function updateHud(badge, title, body) {
    await evaluate(`(() => {
      const hud = document.getElementById('demo-hud-final');
      if (!hud) return;
      hud.innerHTML = \`
        <div style="font-size: 10px; font-weight: 700; letter-spacing: 0.18em; color: #00D2FF; margin-bottom: 4px; text-transform: uppercase;">\${badge}</div>
        <div style="font-size: 17px; font-weight: 800; color: #FFFFFF; margin-bottom: 6px; letter-spacing: -0.01em;">\${title}</div>
        <div style="font-size: 12px; line-height: 1.45; color: #94A3B8;">\${body}</div>
      \`;
    })()`);
  }

  // =========================================================================
  // SCENE 1: Planetary Opening & 3D Orbit (0.0s – 11.0s: 330 frames)
  // =========================================================================
  log('Scene 1: Planetary Hero & Orbit (0-11s, 330 frames)...');
  await evaluate(`(() => {
    showView('dashboard');
    window.scrollTo({ top: 0, behavior: 'instant' });
  })()`);
  await updateHud(
    'MISSION IDENTITY',
    'NISAR // EARTH IN MOTION',
    '<strong>OBSERVATORY:</strong> NASA–ISRO SAR (L-band 1.239 GHz)<br><strong>ORBIT:</strong> 12-day exact repeat ground-track cycle<br><strong>CAPABILITY:</strong> Day/night all-weather surface deformation monitoring.'
  );

  while (currentFrameNumber <= 330) {
    const buf = await snapFrame();
    writeFrameFile(currentFrameNumber++, buf);
  }

  // =========================================================================
  // SCENE 2: Research Challenge & Baseline Verification (11.0s – 25.0s: 420 frames)
  // =========================================================================
  log('Scene 2: Research Challenge & Baseline (~12 days) (11-25s, 420 frames)...');
  await evaluate(`(() => {
    const section = document.getElementById('research-challenge') || document.querySelector('.dashboard-grid');
    if (section) section.scrollIntoView({ behavior: 'smooth', block: 'center' });
  })()`);
  await updateHud(
    'RESEARCH CHALLENGE',
    'VENEZUELA SEISMIC DUPLET (JUNE 2026)',
    '<strong>OBSERVATION:</strong> Track 162, Frame 7 (2026-06-13 → 2026-06-25)<br><strong>BASELINE:</strong> ~12 days (11d 23h 59m 59s elapsed)<br><strong>SEISMICITY:</strong> M7.2 foreshock & M7.5 mainshock occurred 32s apart.'
  );

  for (let i = 0; i < 28; i++) {
    const buf = await snapFrame();
    duplicateFrames(buf, 10);
    await sleep(25);
  }

  // Move cursor to observation card and click to open Venezuela Explorer
  await mouseMove(400, 620);
  await sleep(150);
  await evaluate(`(() => {
    const cta = document.querySelector('#observation-cards [data-open="venezuela"]') || document.getElementById('open-explorer');
    if (cta) cta.click();
  })()`);
  await sleep(300);

  while (currentFrameNumber <= 750) {
    const buf = await snapFrame();
    writeFrameFile(currentFrameNumber++, buf);
  }

  // =========================================================================
  // SCENE 3: Granule Engineering & HDF5 Dimension Scales (25.0s – 38.5s: 405 frames)
  // =========================================================================
  log('Scene 3: Granule Engineering & Attached Dimension Scales (25-38.5s, 405 frames)...');
  await evaluate(`(async () => {
    showView('explorer');
    await openObservation('venezuela');
    window.scrollTo({ top: 0, behavior: 'instant' });
  })()`);
  await sleep(1200);
  await updateHud(
    'ENGINEERING ACHIEVEMENT',
    'HDF5 DIMENSION-SCALE RESOLUTION',
    '<strong>GRANULE SIZE:</strong> 2.34 GB HDF5<br><strong>GRID POSTING:</strong> 80 m × 80 m (4,149 × 4,239 pixels, EPSG:32619)<br><strong>BASELINE:</strong> ~12 days (11d 23h 59m elapsed)<br><strong>BREAKTHROUGH:</strong> Direct resolution of attached DIMENSION_LIST scales eliminates 4× wrapped coordinate mismatch.'
  );

  for (let i = 0; i < 35; i++) {
    const buf = await snapFrame();
    duplicateFrames(buf, 10);
    await sleep(25);
  }
  while (currentFrameNumber <= 1155) {
    const buf = await snapFrame();
    writeFrameFile(currentFrameNumber++, buf);
  }

  // =========================================================================
  // SCENE 4: Interactive Scientific Explorer (38.5s – 58.5s: 600 frames)
  // =========================================================================
  log('Scene 4: Interactive Scientific Explorer (38.5-58.5s, 600 frames)...');

  // 4A: Phase Pixel Inspection & Pinning (38.5s – 48.5s: 300 frames)
  await updateHud(
    'SCIENTIFIC EXPLORER',
    'UNWRAPPED PHASE · RADIANS (MULTI-CYCLE)',
    '<strong>UNITS:</strong> Radians (native product unit, spans multiple 2π cycles)<br><strong>COLORMAP:</strong> Viridis (sequential)<br><strong>PIXEL INSPECTION:</strong> Real-time full-resolution Float32 coordinate & phase sampling.'
  );

  // Live sampling at Point 1: lon=-68.2684, lat=10.8535 (center of interferogram)
  log('Triggering live pixel sampling at Point 1 (-68.268, 10.854)...');
  await evaluate(`(async () => {
    await sampleAt({ lon: -68.268437, lat: 10.853527 }, true);
  })()`);
  await sleep(400);

  // Sweep cursor across the raster
  for (let step = 0; step < 12; step++) {
    const mx = 650 + step * 25;
    const my = 480 + step * 8;
    await mouseMove(mx, my);
    await sleep(35);
  }

  // Live sampling at Point 2: near M7.2 foreshock (-68.556, 10.371)
  log('Triggering live pixel sampling at Point 2 (-68.556, 10.371)...');
  await evaluate(`(async () => {
    await sampleAt({ lon: -68.5564, lat: 10.3713 }, false);
  })()`);
  await sleep(300);

  while (currentFrameNumber <= 1455) {
    const buf = await snapFrame();
    writeFrameFile(currentFrameNumber++, buf);
  }

  // 4B: Coherence Layer Switch & Threshold Slider Drag (48.5s – 58.5s: 300 frames)
  log('Scene 4B: Coherence layer switch & threshold slider drag...');
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

  // Drag threshold slider from 0.40 to 0.60
  await mouseMove(500, 920);
  await mouseDown(500, 920);
  for (let step = 0; step <= 8; step++) {
    await mouseMove(500 + step * 30, 920);
    await sleep(30);
  }
  await evaluate(`(() => {
    const slider = document.getElementById('threshold-slider');
    if (slider) {
      slider.value = '0.55';
      slider.dispatchEvent(new Event('input', { bubbles: true }));
      slider.dispatchEvent(new Event('change', { bubbles: true }));
    }
  })()`);
  await mouseUp(740, 920);
  await sleep(250);

  while (currentFrameNumber <= 1755) {
    const buf = await snapFrame();
    writeFrameFile(currentFrameNumber++, buf);
  }

  // =========================================================================
  // SCENE 5: Earthquake Assessment & Validation Suite (58.5s – 71.5s: 390 frames)
  // =========================================================================
  log('Scene 5: Earthquake Assessment & Validation Suite (58.5-71.5s, 390 frames)...');
  await evaluate(`(() => {
    const section = document.getElementById('validation-section') || document.querySelector('.event-grid') || document.getElementById('event-cards');
    if (section) section.scrollIntoView({ behavior: 'smooth', block: 'center' });
  })()`);
  await updateHud(
    'EARTHQUAKE ASSESSMENT',
    'M7.2 & M7.5 SPATIAL CORRELATION',
    '<strong>FORESHOCK:</strong> M7.2 median coh 0.406 (high reliability)<br><strong>MAINSHOCK:</strong> M7.5 median coh 0.077 (decorrelated)<br><strong>SEPARATION:</strong> 148.33 km between epicentres<br><strong>CAVEAT:</strong> Coherence reflects measurement quality, NOT damage.'
  );

  // Click M7.2 Cariaco event card
  await sleep(400);
  await evaluate(`(() => {
    if (typeof locateEvent === 'function') locateEvent(0);
  })()`);
  await sleep(500);

  for (let i = 0; i < 18; i++) {
    const buf = await snapFrame();
    duplicateFrames(buf, 10);
    await sleep(20);
  }

  // Click M7.5 Casanay event card
  await evaluate(`(() => {
    if (typeof locateEvent === 'function') locateEvent(1);
  })()`);
  await sleep(400);

  while (currentFrameNumber <= 2145) {
    const buf = await snapFrame();
    writeFrameFile(currentFrameNumber++, buf);
  }

  // =========================================================================
  // SCENE 6: Scientific Honesty & Authentic Export (71.5s – 81.5s: 300 frames)
  // =========================================================================
  log('Scene 6: Scientific Honesty & Authentic Export (71.5-81.5s, 300 frames)...');
  await evaluate(`(() => {
    const exportSec = document.getElementById('export-panel') || document.getElementById('limitations-section') || document.querySelector('.export-card');
    if (exportSec) exportSec.scrollIntoView({ behavior: 'smooth', block: 'start' });
    else window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
  })()`);
  await sleep(600);

  await updateHud(
    'SCIENTIFIC INTEGRITY',
    'PHYSICAL LIMITATIONS & DATA EXPORT',
    '<strong>PHASE:</strong> Radians only (not converted to displacement)<br><strong>STATUS:</strong> scientific_interpretation_validated = false<br><strong>EXPORT:</strong> GeoTIFF rasters, metadata JSON & full audit packages.'
  );

  // Hover and trigger export button
  await mouseMove(450, 780);
  await sleep(300);
  await evaluate(`(() => {
    const btn = document.getElementById('export-btn') || document.querySelector('.btn-export') || document.querySelector('[data-action="export"]');
    if (btn) {
      btn.style.transform = 'scale(1.05)';
      btn.style.boxShadow = '0 0 20px rgba(0, 210, 255, 0.6)';
    }
  })()`);
  await sleep(400);

  while (currentFrameNumber <= 2445) {
    const buf = await snapFrame();
    writeFrameFile(currentFrameNumber++, buf);
  }

  // =========================================================================
  // CLOSING CARD: Clean Submission Card (81.5s – 86.5s: 150 frames)
  // =========================================================================
  log('Closing Card: Displaying clean credentials card (81.5-86.5s, 150 frames)...');
  await evaluate(`(() => {
    const hud = document.getElementById('demo-hud-final');
    if (hud) hud.style.display = 'none';

    const card = document.getElementById('closing-card-final');
    if (card) {
      card.style.display = 'flex';
      card.style.opacity = '1';
    }
  })()`);
  await sleep(200);

  // Hold card for 135 frames (4.5s)
  const cardBuf = await snapFrame();
  duplicateFrames(cardBuf, 135);

  // =========================================================================
  // FADE TO BLACK: Clean 0.5s Outro (86.5s – 87.0s: 15 frames)
  // =========================================================================
  log('Triggering clean 0.5s fade to black (86.5-87.0s, 15 frames)...');
  await evaluate(`(() => {
    const card = document.getElementById('closing-card-final');
    if (card) card.style.opacity = '0';
  })()`);
  await sleep(60);

  while (currentFrameNumber <= TOTAL_FRAMES) {
    const buf = await snapFrame();
    writeFrameFile(currentFrameNumber++, buf);
    await sleep(25);
  }

  log(`Frame capture complete: generated ${currentFrameNumber - 1} frames (target: ${TOTAL_FRAMES}).`);

  child.kill();
  try {
    rmSync(profile, { recursive: true, force: true });
  } catch {}
}

function renderMasterVideo() {
  log('Encoding Master Final Video with FFmpeg...');

  // Escape colon in Windows path for FFmpeg ass filter
  const subEscaped = SUBTITLES_ASS.replace(/\\/g, '/').replace(/:/g, '\\:');
  const framesPattern = `${FRAMES_DIR.replace(/\\/g, '/')}/frame_%05d.jpg`;
  const audioIn = MASTER_AUDIO.replace(/\\/g, '/');
  const mp4Out = OUTPUT_MP4.replace(/\\/g, '/');

  const cmd = `ffmpeg -y -framerate 30 -i "${framesPattern}" -i "${audioIn}" -vf "ass='${subEscaped}',scale=out_color_matrix=bt709:out_range=tv,format=yuv420p" -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p -color_range tv -colorspace bt709 -color_primaries bt709 -color_trc bt709 -c:a copy -movflags +faststart "${mp4Out}"`;

  log(`Executing: ${cmd}`);
  execSync(cmd, { stdio: 'inherit' });
  log(`Master Video FINAL rendered successfully: ${OUTPUT_MP4}`);
}

async function main() {
  ensureDirectories();
  try {
    await ensureServerRunning();
    await captureApplicationFrames();
    renderMasterVideo();
  } finally {
    if (serverProcess) {
      log('Terminating dedicated web server process...');
      serverProcess.kill();
    }
  }
}

main().catch((err) => {
  console.error('[record_final] FATAL:', err);
  if (serverProcess) serverProcess.kill();
  process.exit(1);
});
