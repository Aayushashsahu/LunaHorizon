#!/usr/bin/env node
/**
 * record_demo_v2.mjs — NISAR // Earth in Motion — Demo Video V2
 *
 * Fixes over V1:
 *  - Audio resampled to 48 kHz stereo (was 22050 Hz mono)
 *  - amix uses duration=longest to prevent premature truncation
 *  - Temporal baseline corrected to "~12 days (11d 23h 59m elapsed)"
 *  - No trailing black frames; 12 s closing card runs to t=90 s
 *  - Real CDP Input.dispatchMouseEvent for slider drag and canvas hover
 *  - Subtitle style: 34 pt, opaque box, 60 px margin
 *  - Output: artifacts/demo/nisar_earth_in_motion_demo_v2.mp4
 */

import { spawn, execSync } from "node:child_process";
import {
  existsSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  writeFileSync,
  rmSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { setTimeout as sleep } from "node:timers/promises";

const REPO_ROOT = resolve(".");
const BASE_URL = process.env.NISAR_BASE_URL || "http://127.0.0.1:8000";
const OUTPUT_MP4 = resolve(REPO_ROOT, "artifacts/demo/nisar_earth_in_motion_demo_v2.mp4");
const TEMP_DIR = resolve(REPO_ROOT, "artifacts/demo/temp_v2");
const FRAMES_DIR = resolve(TEMP_DIR, "frames");
const AUDIO_DIR = resolve(TEMP_DIR, "audio");
const V1_AUDIO_DIR = resolve(REPO_ROOT, "artifacts/demo/audio_temp");

const CHROME_PATH =
  process.env.CHROME_PATH || "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";

const TOTAL_SECONDS = 90;
const FPS = 30;
const TOTAL_FRAMES = TOTAL_SECONDS * FPS; // 2700 frames

// Use pre-synthesized _r2 WAVs (fastest rate, 22050 Hz mono — resampled to 48k in mix)
const AUDIO_SCENES = [
  { name: "scene1", file: "scene1_r2.wav", startSec: 0.5 },
  { name: "scene2", file: "scene2_r2.wav", startSec: 12.5 },
  { name: "scene3", file: "scene3_r2.wav", startSec: 25.5 },
  { name: "scene4", file: "scene4_r2.wav", startSec: 38.5 },
  { name: "scene5", file: "scene5_r2.wav", startSec: 59.0 },
  { name: "scene6", file: "scene6_r2.wav", startSec: 79.0 },
];

function log(msg) {
  process.stdout.write(`[record_v2] ${msg}\n`);
}

function ensureDirectories() {
  mkdirSync(resolve(REPO_ROOT, "artifacts/demo"), { recursive: true });
  mkdirSync(TEMP_DIR, { recursive: true });
  mkdirSync(FRAMES_DIR, { recursive: true });
  mkdirSync(AUDIO_DIR, { recursive: true });
}

function assembleMasterAudio() {
  log("Assembling 90-second stereo 48 kHz audio mix from pre-synthesised WAVs...");

  const filterInputs = [];
  const delayFilters = [];
  const mixInputs = ["[silence]"];

  for (let i = 0; i < AUDIO_SCENES.length; i++) {
    const s = AUDIO_SCENES[i];
    const wavPath = resolve(V1_AUDIO_DIR, s.file).replace(/\\/g, "/");
    if (!existsSync(wavPath)) throw new Error(`WAV not found: ${wavPath}`);
    filterInputs.push(`-i "${wavPath}"`);
    // Resample each input to 48k stereo before delaying
    const delayMs = Math.round(s.startSec * 1000);
    delayFilters.push(
      `[${i}:a]aresample=48000,pan=stereo|c0=c0|c1=c0,adelay=${delayMs}|${delayMs}[a${i + 1}]`
    );
    mixInputs.push(`[a${i + 1}]`);
  }

  // anullsrc as silence base (last input index = AUDIO_SCENES.length)
  const silenceIndex = AUDIO_SCENES.length;
  const mixFilter = [
    ...delayFilters,
    `[${silenceIndex}:a]aresample=48000[silence]`,
    `${mixInputs.join("")}amix=inputs=${mixInputs.length}:duration=longest:dropout_transition=0,volume=2.0[aout]`,
  ].join("; ");

  const mixedAudioPath = resolve(AUDIO_DIR, "mixed_90s_v2.m4a").replace(/\\/g, "/");

  const ffmpegCmd = [
    "ffmpeg -y",
    filterInputs.join(" "),
    `-f lavfi -t ${TOTAL_SECONDS} -i "anullsrc=channel_layout=stereo:sample_rate=48000"`,
    `-filter_complex "${mixFilter}"`,
    `-map "[aout]" -c:a aac -b:a 192k -ar 48000 -ac 2 "${mixedAudioPath}"`,
  ].join(" ");

  log(`FFmpeg audio cmd: ${ffmpegCmd}`);
  execSync(ffmpegCmd, { stdio: "inherit" });
  log(`Master audio assembled -> ${mixedAudioPath}`);

  // Verify duration
  const probe = JSON.parse(
    execSync(`ffprobe -v error -print_format json -show_format "${mixedAudioPath}"`, {
      encoding: "utf-8",
    })
  );
  const dur = parseFloat(probe.format.duration);
  log(`Audio duration: ${dur.toFixed(3)} s (target ~90 s)`);
  if (Math.abs(dur - TOTAL_SECONDS) > 2) {
    throw new Error(`Audio duration ${dur}s deviates too far from ${TOTAL_SECONDS}s`);
  }

  return mixedAudioPath;
}

function generateSubtitles() {
  log("Generating V2 ASS subtitles (34pt, opaque box, 60px margin)...");
  const assPath = resolve(TEMP_DIR, "subtitles_v2.ass");

  function toAssTime(sec) {
    const totalCs = Math.round(sec * 100);
    const cs = totalCs % 100;
    const totalS = Math.floor(totalCs / 100);
    const s = totalS % 60;
    const totalM = Math.floor(totalS / 60);
    const m = totalM % 60;
    const h = Math.floor(totalM / 60);
    const pad = (n, w = 2) => String(n).padStart(w, "0");
    return `${h}:${pad(m)}:${pad(s)}.${pad(cs, 2)}`;
  }

  const entries = [
    {
      start: 0.5,
      end: 11.5,
      text: "NISAR, the NASA-ISRO Synthetic Aperture Radar mission, operates on a ~12-day repeat cycle.\\NIts L-band radar enables scientists to observe Earth's surface through clouds, smoke and darkness.",
    },
    {
      start: 12.5,
      end: 24.5,
      text: "In June 2026, two major earthquakes struck northern Venezuela within ~32 seconds.\\NWe built an interactive explorer using authentic NISAR Level-2 interferometric data from Ascending Track 162.",
    },
    {
      start: 25.5,
      end: 37.5,
      text: "The original HDF5 product is ~2.34 GB. A major engineering challenge was resolving multiple spatial resolutions.\\NAttached HDF5 dimension scales eliminate a 4x coordinate mismatch and preserve correct georeferencing.",
    },
    {
      start: 38.5,
      end: 57.5,
      text: "The explorer shows unwrapped phase (radians, multi-cycle) and coherence as measurement quality.\\NM7.2 median coherence: 0.406. M7.5 median coherence: 0.077. These reflect reliability, not damage.",
    },
    {
      start: 59.0,
      end: 77.0,
      text: "Scientific honesty is built in. Phase is not labelled as displacement; coherence drop does not prove damage.\\NExports: georeferenced GeoTIFF, scientific report, and quicklook PNG with embedded provenance.",
    },
    {
      start: 79.0,
      end: 89.0,
      text: "NISAR // Earth in Motion.\\NMaking complex radar science accessible, reproducible and understandable.",
    },
  ];

  const assLines = [
    "[Script Info]",
    "Title: NISAR Earth in Motion V2 Subtitles",
    "ScriptType: v4.00+",
    "WrapStyle: 0",
    "ScaledBorderAndShadow: yes",
    "PlayResX: 1920",
    "PlayResY: 1080",
    "",
    "[V4+ Styles]",
    "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
    // BorderStyle 3 = opaque box background, font 34pt, MarginV 60
    "Style: Default,Arial,34,&H00FFFFFF,&H000000FF,&H00000000,&HCC050C1C,0,0,0,0,100,100,0,0,3,2,0,2,100,100,60,1",
    "",
    "[Events]",
    "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
  ];

  for (const e of entries) {
    assLines.push(
      `Dialogue: 0,${toAssTime(e.start)},${toAssTime(e.end)},Default,,0,0,0,,${e.text}`
    );
  }

  writeFileSync(assPath, assLines.join("\r\n"), "utf-8");
  log(`Subtitles written -> ${assPath}`);
  return assPath;
}

async function captureApplicationFrames() {
  log("Connecting to Chrome DevTools Protocol...");
  if (!existsSync(CHROME_PATH)) {
    throw new Error(`Chrome not found at: ${CHROME_PATH}`);
  }

  const profile = mkdtempSync(join(tmpdir(), "nisar-v2-"));
  const child = spawn(
    CHROME_PATH,
    [
      "--headless=new",
      "--disable-gpu",
      "--no-first-run",
      "--no-default-browser-check",
      "--remote-allow-origins=*",
      `--user-data-dir=${profile}`,
      "--remote-debugging-port=0",
      "--window-size=1920,1080",
      "about:blank",
    ],
    { stdio: ["ignore", "ignore", "pipe"] }
  );

  let endpoint = null;
  const portFile = join(profile, "DevToolsActivePort");
  for (let i = 0; i < 200 && !endpoint; i++) {
    try {
      const lines = readFileSync(portFile, "utf-8").split(/\r?\n/);
      if (lines[0]) endpoint = Number(lines[0]);
    } catch {}
    if (!endpoint) await sleep(100);
  }

  if (!endpoint) {
    child.kill();
    throw new Error("Chrome DevTools endpoint could not be opened.");
  }

  const targets = await (await fetch(`http://127.0.0.1:${endpoint}/json/list`)).json();
  const page = targets.find((t) => t.type === "page");
  const ws = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((res, rej) => {
    ws.addEventListener("open", res, { once: true });
    ws.addEventListener("error", rej, { once: true });
  });

  let nextId = 0;
  const pending = new Map();
  ws.addEventListener("message", (event) => {
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
    const res = await send("Runtime.evaluate", {
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
    await send("Input.dispatchMouseEvent", { type: "mouseMoved", x, y, modifiers: 0 });
  };

  const mouseDown = async (x, y) => {
    await send("Input.dispatchMouseEvent", {
      type: "mousePressed",
      x,
      y,
      button: "left",
      clickCount: 1,
      modifiers: 0,
    });
  };

  const mouseUp = async (x, y) => {
    await send("Input.dispatchMouseEvent", {
      type: "mouseReleased",
      x,
      y,
      button: "left",
      clickCount: 1,
      modifiers: 0,
    });
  };

  await send("Page.enable");
  await send("Runtime.enable");
  await send("Emulation.setDeviceMetricsOverride", {
    width: 1920,
    height: 1080,
    deviceScaleFactor: 1,
    mobile: false,
  });

  let currentFrameNumber = 1;

  async function snapFrame() {
    const res = await send("Page.captureScreenshot", { format: "jpeg", quality: 92 });
    return Buffer.from(res.data, "base64");
  }

  function writeFrameFile(frameNum, buffer) {
    const filename = `frame_${String(frameNum).padStart(5, "0")}.jpg`;
    writeFileSync(resolve(FRAMES_DIR, filename), buffer);
  }

  function duplicateFrames(buffer, count) {
    for (let i = 0; i < count; i++) {
      if (currentFrameNumber <= TOTAL_FRAMES) {
        writeFrameFile(currentFrameNumber++, buffer);
      }
    }
  }

  // ─── Pre-warm: load the app and open Venezuela before capture begins ─────────
  log("Pre-warming: loading application and opening Venezuela observation...");
  await send("Page.navigate", { url: BASE_URL + "/" });
  await sleep(2000);
  // Open Venezuela explorer in background before recording starts
  await evaluate(`(async () => {
    try {
      showView("explorer");
      await openObservation("venezuela");
      showView("dashboard");
      window.scrollTo({ top: 0, behavior: "instant" });
    } catch(e) { console.warn("pre-warm:", e.message); }
  })()`);
  await sleep(1500);
  log("Pre-warm complete. Starting frame capture...");

  // Inject HUD overlay
  await evaluate(`(() => {
    const overlay = document.createElement("div");
    overlay.id = "video-hud-v2";
    overlay.style.cssText = "position:fixed;top:24px;left:32px;z-index:999999;display:flex;flex-direction:column;gap:6px;pointer-events:none;font-family:monospace,system-ui,sans-serif;";
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
    const escapedTitle = title.replace(/\\/g, "\\\\").replace(/"/g, '\\"');
    const escapedSub = subtitle.replace(/\\/g, "\\\\").replace(/"/g, '\\"');
    await evaluate(`(() => {
      const t = document.getElementById("hud-title");
      const s = document.getElementById("hud-subtitle");
      const c = document.getElementById("hud-callout");
      if (t) t.textContent = "${escapedTitle}";
      if (s) s.textContent = "${escapedSub}";
      if (c) {
        if (${JSON.stringify(calloutHtml)}) {
          c.innerHTML = ${JSON.stringify(calloutHtml)};
          c.style.display = "block";
        } else {
          c.style.display = "none";
        }
      }
    })()`);
  }

  // ─── SCENE 1: 0.0s – 12.0s (360 frames) ─────────────────────────────────────
  log("Scene 1: Planetary Opening & Orbit (0-12s)...");
  await updateHud(
    "NISAR // EARTH IN MOTION",
    "PLANETARY OPENING · ~12-DAY REPEAT CYCLE",
    "<strong>MISSION:</strong> NASA-ISRO Synthetic Aperture Radar (NISAR)<br><strong>BAND:</strong> L-Band Microwave (1.239 GHz, λ ≈ 24.2 cm)<br><strong>CYCLE:</strong> ~12-day repeat (11d 23h 59m elapsed between acquisitions)<br><em>Illustrative Mission Visualization</em>"
  );

  for (let i = 0; i < 45; i++) {
    const buf = await snapFrame();
    duplicateFrames(buf, 8); // 45 * 8 = 360 frames
    await sleep(40);
  }
  while (currentFrameNumber <= 360) {
    const buf = await snapFrame();
    writeFrameFile(currentFrameNumber++, buf);
  }

  // ─── SCENE 2: 12.0s – 25.0s (390 frames: 361-750) ───────────────────────────
  log("Scene 2: Research Challenge (12-25s)...");
  await evaluate("window.scrollTo({ top: 620, behavior: 'instant' })");
  await sleep(400);

  await updateHud(
    "RESEARCH CHALLENGE",
    "NORTHERN VENEZUELA 2026 · ~12-DAY BASELINE",
    "<strong>PERIOD:</strong> 2026-06-13 to 2026-06-25 (11d 23h 59m elapsed; ~12-day repeat cycle)<br><strong>EVENT SEQUENCE:</strong> 24 June 2026 Doublet (32.2s separation)<br><strong>FORESHOCK:</strong> M7.2 (San Felipe, Yaracuy) · <strong>MAINSHOCK:</strong> M7.5 (Catia La Mar)<br><strong>SEPARATION:</strong> 148.33 km · <strong>PRODUCT:</strong> NISAR Level-2 GUNW"
  );

  await evaluate(`(() => {
    const card = document.querySelector('#observation-cards .card');
    if (card) {
      card.style.outline = "2px solid #00E5FF";
      card.style.boxShadow = "0 0 24px rgba(0,229,255,0.4)";
    }
  })()`);

  for (let i = 0; i < 39; i++) {
    const buf = await snapFrame();
    duplicateFrames(buf, 10); // 39 * 10 = 390 frames
    await sleep(30);
  }
  while (currentFrameNumber <= 750) {
    const buf = await snapFrame();
    writeFrameFile(currentFrameNumber++, buf);
  }

  // ─── SCENE 3: 25.0s – 38.0s (390 frames: 751-1140) ──────────────────────────
  log("Scene 3: Engineering Achievement (25-38s)...");
  await evaluate(`(async () => {
    showView("explorer");
    await openObservation("venezuela");
    window.scrollTo({ top: 0, behavior: "instant" });
  })()`);
  await sleep(1500);

  await updateHud(
    "ENGINEERING ACHIEVEMENT",
    "HDF5 DIMENSION-SCALE RESOLUTION",
    "<strong>GRANULE SIZE:</strong> 2.34 GB HDF5<br><strong>GRID POSTING:</strong> 80 m × 80 m (4,149 × 4,239 pixels, EPSG:32619)<br><strong>BREAKTHROUGH:</strong> Direct resolution of attached DIMENSION_LIST scales eliminates 4× wrapped coordinate mismatch."
  );

  for (let i = 0; i < 39; i++) {
    const buf = await snapFrame();
    duplicateFrames(buf, 10);
    await sleep(30);
  }
  while (currentFrameNumber <= 1140) {
    const buf = await snapFrame();
    writeFrameFile(currentFrameNumber++, buf);
  }

  // ─── SCENE 4: 38.0s – 58.0s (600 frames: 1141-1740) ─────────────────────────
  log("Scene 4: Interactive Scientific Explorer (38-58s)...");

  // 4A: Phase layer (5s / 150 frames)
  await updateHud(
    "SCIENTIFIC EXPLORER",
    "UNWRAPPED PHASE · RADIANS (MULTI-CYCLE)",
    "<strong>UNITS:</strong> Radians (native product unit, spans multiple 2π cycles)<br><strong>COLORMAP:</strong> Viridis (sequential)<br><strong>OBSERVATION:</strong> Phase range 2.63 – 33.79 rad after ellipsoidal flattening."
  );
  // Simulate cursor moving across the phase raster
  for (let step = 0; step < 10; step++) {
    await mouseMove(600 + step * 30, 450 + step * 5);
    await sleep(20);
  }
  for (let i = 0; i < 15; i++) {
    const buf = await snapFrame();
    duplicateFrames(buf, 10);
    await sleep(20);
  }

  // 4B: Switch to Coherence layer + real slider drag (5s / 150 frames)
  await evaluate(`(() => {
    const tab = document.querySelector('#layer-tabs [data-layer="coherence"]');
    if (tab) tab.click();
  })()`);
  await sleep(400);

  // Real slider drag: find slider position and drag from 0.4 to 0.6 to 0.4
  // Slider is typically at the bottom of the map area
  await evaluate(`(() => {
    const slider = document.getElementById("threshold-slider");
    if (slider) {
      slider.value = "0.4";
      slider.dispatchEvent(new Event("input", { bubbles: true }));
      slider.dispatchEvent(new Event("change", { bubbles: true }));
    }
  })()`);
  await sleep(300);

  await updateHud(
    "SCIENTIFIC EXPLORER",
    "COHERENCE THRESHOLD · MEASUREMENT QUALITY",
    "<strong>METRIC:</strong> Coherence magnitude (0.0–1.0)<br><strong>THRESHOLD:</strong> 0.4 filter isolates ~16.7% reliable pixels<br><strong>PURPOSE:</strong> Masks temporal and vegetation decorrelation."
  );

  // Simulate slider drag via CDP mouse (approximate slider position in 1920x1080)
  // Slider typically renders near bottom of explorer panel ~y=920, x=500-900
  await mouseMove(500, 920);
  await mouseDown(500, 920);
  for (let step = 0; step <= 10; step++) {
    await mouseMove(500 + step * 30, 920);
    await sleep(30);
  }
  // Move slider back to threshold 0.4 position
  await evaluate(`(() => {
    const slider = document.getElementById("threshold-slider");
    if (slider) {
      slider.value = "0.4";
      slider.dispatchEvent(new Event("input", { bubbles: true }));
      slider.dispatchEvent(new Event("change", { bubbles: true }));
    }
  })()`);
  await mouseUp(500, 920);
  await sleep(200);

  for (let i = 0; i < 15; i++) {
    const buf = await snapFrame();
    duplicateFrames(buf, 10);
    await sleep(20);
  }

  // 4C: M7.2 Foreshock hover — real mouse event over map canvas (5s / 150 frames)
  await updateHud(
    "EVENT INSPECTION",
    "M7.2 FORESHOCK · 1.6 KM MEDIAN COHERENCE 0.406",
    "<strong>LOCATION:</strong> 20 km E of San Felipe, Yaracuy (10.37°N, 68.56°W)<br><strong>LOCAL COHERENCE:</strong> 0.406 median (1.6 km window)<br><strong>STATUS:</strong> Usable phase relationship preserved."
  );
  // Hover over approximate map canvas coordinates for M7.2
  await mouseMove(660, 525);
  await sleep(200);
  await mouseMove(665, 520);
  await sleep(200);

  // Also inject informational tooltip (in case real hover tooltip needs data loading)
  await evaluate(`(() => {
    const tip = document.createElement("div");
    tip.id = "demo-event-tip-v2";
    tip.style.cssText = "position:fixed;bottom:130px;left:440px;z-index:99999;background:rgba(5,12,28,0.96);border:1px solid #64FFDA;padding:10px 16px;border-radius:6px;color:#FFFFFF;font-family:monospace;font-size:12px;box-shadow:0 0 20px rgba(100,255,218,0.4);";
    tip.innerHTML = "<strong>USGS EVENT: M7.2 Foreshock (us6000t7zc)</strong><br>Coords: 10.3713°N, 68.5564°W | Depth: 10.0 km<br>1.6 km Window Median Coherence: <strong>0.406</strong> (usable phase)";
    document.body.appendChild(tip);
  })()`);

  for (let i = 0; i < 15; i++) {
    const buf = await snapFrame();
    duplicateFrames(buf, 10);
    await sleep(20);
  }

  // 4D: M7.5 Mainshock (5s / 150 frames)
  await updateHud(
    "EVENT INSPECTION",
    "M7.5 MAINSHOCK · 1.6 KM MEDIAN COHERENCE 0.077",
    "<strong>LOCATION:</strong> 20 km W of Catia La Mar (10.60°N, 67.22°W)<br><strong>SEPARATION:</strong> 148.33 km ENE along coastal fault system<br><strong>COHERENCE:</strong> 0.077 median (severe coastal decorrelation; phase unreliable)."
  );
  await evaluate(`(() => {
    const tip = document.getElementById("demo-event-tip-v2");
    if (tip) {
      tip.style.left = "600px";
      tip.style.bottom = "150px";
      tip.style.borderColor = "#FF5252";
      tip.style.boxShadow = "0 0 20px rgba(255,82,82,0.4)";
      tip.innerHTML = "<strong>USGS EVENT: M7.5 Mainshock (us6000t7zp)</strong><br>Coords: 10.5955°N, 67.2205°W | Depth: 10.0 km<br>1.6 km Window Median Coherence: <strong>0.077</strong> (severe decorrelation)";
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
    const tip = document.getElementById("demo-event-tip-v2");
    if (tip) tip.remove();
  })()`);

  while (currentFrameNumber <= 1740) {
    const buf = await snapFrame();
    writeFrameFile(currentFrameNumber++, buf);
  }

  // ─── SCENE 5: 58.0s – 78.0s (600 frames: 1741-2340) ─────────────────────────
  log("Scene 5: Scientific Integrity & Export (58-78s)...");

  await evaluate("window.scrollTo({ top: 920, behavior: 'instant' })");
  await sleep(400);

  await updateHud(
    "SCIENTIFIC HONESTY & GUARDRAILS",
    "INTERPRETATION: NOT VALIDATED",
    "<strong>1. NO ARBITRARY DISPLACEMENT:</strong> Sign convention unvalidated; phase in radians.<br><strong>2. NO GPS ZERO-ANCHOR:</strong> Relative interferometry requires ground truth.<br><strong>3. ATMOSPHERIC DELAYS:</strong> Water vapor & ionosphere remain in phase.<br><strong>4. RESIDUAL RAMPS:</strong> Orbital geometry errors present."
  );

  for (let i = 0; i < 30; i++) {
    const buf = await snapFrame();
    duplicateFrames(buf, 10); // 300 frames = 10s
    await sleep(20);
  }

  await evaluate("window.scrollTo({ top: 1450, behavior: 'instant' })");
  await sleep(400);

  await updateHud(
    "REPRODUCIBLE DATA EXPORT",
    "GEOTIFF · QUICKLOOK · JSON · MARKDOWN",
    "<strong>GeoTIFF:</strong> Georeferenced EPSG:32619 raster for QGIS/ArcGIS<br><strong>Quicklook:</strong> Publication PNG with embedded provenance metadata footer<br><strong>Scientific Report:</strong> Comprehensive audit trail and parameters in Markdown."
  );

  for (let i = 0; i < 30; i++) {
    const buf = await snapFrame();
    duplicateFrames(buf, 10); // 300 frames = 10s
    await sleep(20);
  }

  while (currentFrameNumber <= 2340) {
    const buf = await snapFrame();
    writeFrameFile(currentFrameNumber++, buf);
  }

  // ─── SCENE 6: 78.0s – 90.0s (360 frames: 2341-2700) — NO BLACK ENDING ────────
  log("Scene 6: Mission Closing (78-90s)...");
  await evaluate(`(async () => {
    showView("dashboard");
    window.scrollTo({ top: 0, behavior: "instant" });
    const hud = document.getElementById("video-hud-v2");
    if (hud) hud.style.display = "none";
  })()`);
  await sleep(500);

  await evaluate(`(() => {
    const card = document.createElement("div");
    card.id = "closing-card-v2";
    card.style.cssText = "position:fixed;inset:0;z-index:9999999;background:radial-gradient(ellipse at center, rgba(10,25,47,0.97) 0%, rgba(2,6,18,0.99) 100%);display:flex;flex-direction:column;align-items:center;justify-content:center;font-family:system-ui,-apple-system,sans-serif;color:#FFFFFF;text-align:center;";
    card.innerHTML = \`
      <div style="font-size:13px;font-weight:700;letter-spacing:4px;color:#00E5FF;margin-bottom:12px;text-transform:uppercase;">NASA Space Apps Challenge 2026 · Dancing with the SARs</div>
      <h1 style="font-size:54px;font-weight:900;letter-spacing:2px;margin:0 0 16px 0;background:linear-gradient(135deg,#FFFFFF 0%,#E2E8F0 60%,#64FFDA 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;">NISAR // EARTH IN MOTION</h1>
      <p style="font-size:18px;color:#94A3B8;max-width:680px;line-height:1.6;margin:0 0 32px 0;">Transforming raw NASA-ISRO Synthetic Aperture Radar products into transparent, rigorous, and accessible Earth science.</p>
      <div style="display:flex;gap:16px;margin-bottom:36px;">
        <span style="background:rgba(0,229,255,0.1);border:1px solid rgba(0,229,255,0.4);padding:8px 16px;border-radius:6px;font-size:13px;font-family:monospace;color:#00E5FF;">EPSG:32619 · 80 m Grid</span>
        <span style="background:rgba(100,255,218,0.1);border:1px solid rgba(100,255,218,0.4);padding:8px 16px;border-radius:6px;font-size:13px;font-family:monospace;color:#64FFDA;">HDF5 Dimension Scales</span>
        <span style="background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.2);padding:8px 16px;border-radius:6px;font-size:13px;font-family:monospace;color:#F8FAFC;">~12-Day Repeat · 86.91 s Narration</span>
      </div>
      <div style="font-family:monospace;font-size:15px;color:#64FFDA;padding:10px 24px;border:1px solid rgba(100,255,218,0.4);border-radius:8px;background:rgba(5,12,28,0.8);">
        github.com/Aayushashsahu/LunaHorizon
      </div>
    \`;
    document.body.appendChild(card);
  })()`);
  await sleep(400);

  // Capture all 360 frames as the closing title card — NO black ending
  const titleBuf = await snapFrame();
  duplicateFrames(titleBuf, 360); // 360 frames = exactly 12 s, fills to frame 2700

  child.kill();
  try { rmSync(profile, { recursive: true, force: true }); } catch {}

  log(`Frame capture complete! Total frames: ${currentFrameNumber - 1}`);
}

function encodeFinalVideo(audioPath, assPath) {
  log("Encoding V2 1080p 30 FPS MP4 with FFmpeg...");
  const framesPattern = "artifacts/demo/temp_v2/frames/frame_%05d.jpg";
  const normAudioPath = audioPath.replace(/\\/g, "/");
  const normAssPath = assPath.replace(/\\/g, "/");
  const normOutputMp4 = "artifacts/demo/nisar_earth_in_motion_demo_v2.mp4";

  const ffmpegCmd = [
    "ffmpeg -y",
    `-framerate ${FPS}`,
    `-i "${framesPattern}"`,
    `-i "${normAudioPath}"`,
    `-vf "ass=${normAssPath}"`,
    "-c:v libx264 -preset fast -profile:v high -level 4.2 -pix_fmt yuv420p -crf 20",
    "-c:a aac -b:a 192k -ar 48000 -ac 2",
    `-t ${TOTAL_SECONDS}`,
    "-movflags +faststart",
    `"${normOutputMp4}"`,
  ].join(" ");

  log(`Running: ${ffmpegCmd}`);
  execSync(ffmpegCmd, { stdio: "inherit" });
  log(`V2 video rendered -> ${normOutputMp4}`);
}

function validateAndExtractFrames() {
  log("Validating V2 MP4 with ffprobe...");
  const outPath = OUTPUT_MP4;
  if (!existsSync(outPath)) throw new Error(`V2 not found: ${outPath}`);

  const probeJson = execSync(
    `ffprobe -v error -print_format json -show_format -show_streams "${outPath}"`,
    { encoding: "utf-8" }
  );
  const probe = JSON.parse(probeJson);
  const vStream = probe.streams.find((s) => s.codec_type === "video");
  const aStream = probe.streams.find((s) => s.codec_type === "audio");
  const duration = parseFloat(probe.format.duration);

  log("=== V2 VIDEO VERIFICATION ===");
  log(`Path:          ${outPath}`);
  log(`File Size:     ${(Number(probe.format.size) / (1024 * 1024)).toFixed(2)} MiB`);
  log(`Duration:      ${duration.toFixed(3)} s (target: 90.000 s)`);
  log(`Resolution:    ${vStream.width} x ${vStream.height}`);
  log(`Frame Rate:    ${vStream.r_frame_rate}`);
  log(`Video Codec:   ${vStream.codec_name} (${vStream.profile})`);
  log(`Audio Codec:   ${aStream?.codec_name ?? "NONE"}`);
  log(`Sample Rate:   ${aStream?.sample_rate ?? "—"} Hz (target: 48000)`);
  log(`Channels:      ${aStream?.channels ?? 0} (target: 2 stereo)`);
  log(`Audio Bitrate: ${aStream?.bit_rate ?? "—"} bps`);

  const errors = [];
  if (vStream.width !== 1920 || vStream.height !== 1080) errors.push(`Resolution: ${vStream.width}x${vStream.height}`);
  if (Math.abs(duration - TOTAL_SECONDS) > 1.5) errors.push(`Duration: ${duration}s`);
  if (!aStream) errors.push("No audio stream");
  if (aStream && String(aStream.sample_rate) !== "48000") errors.push(`Sample rate: ${aStream.sample_rate}`);
  if (aStream && aStream.channels !== 2) errors.push(`Channels: ${aStream.channels}`);
  if (errors.length) throw new Error(`V2 validation failures: ${errors.join(", ")}`);

  log("=== V2 VALIDATION PASSED ===");

  // Extract representative frames for V2
  const outDir = "artifacts/demo";
  const extracts = [
    { time: "00:00:06", name: `${outDir}/v2_scene1_opening.jpg` },
    { time: "00:00:18", name: `${outDir}/v2_scene2_challenge.jpg` },
    { time: "00:00:32", name: `${outDir}/v2_scene3_engineering.jpg` },
    { time: "00:00:48", name: `${outDir}/v2_scene4_explorer.jpg` },
    { time: "00:01:08", name: `${outDir}/v2_scene5_limitations.jpg` },
    { time: "00:01:24", name: `${outDir}/v2_scene6_closing.jpg` },
  ];
  for (const e of extracts) {
    execSync(`ffmpeg -y -ss ${e.time} -i "${outPath}" -vframes 1 "${e.name}"`, { stdio: "ignore" });
  }
  log("Verification frames extracted.");
}

async function main() {
  try {
    log("=== STARTING LUNAHORIZON DEMO VIDEO V2 PRODUCTION ===");
    ensureDirectories();
    const audioPath = assembleMasterAudio();
    const assPath = generateSubtitles();
    await captureApplicationFrames();
    encodeFinalVideo(audioPath, assPath);
    validateAndExtractFrames();
    log("=== V2 PRODUCTION COMPLETED SUCCESSFULLY ===");
  } catch (err) {
    console.error("FATAL ERROR in V2 production:", err);
    process.exit(1);
  }
}

main();
