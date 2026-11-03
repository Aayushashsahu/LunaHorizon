#!/usr/bin/env node
/**
 * Automated demo video production script for NISAR // Earth in Motion.
 *
 * Captures authentic 1080p footage from the running local web application
 * (http://127.0.0.1:8000), synthesizes narration audio via local System.Speech,
 * generates synchronized styled subtitles, and encodes a complete 90-second MP4 at 30 FPS
 * to artifacts/demo/nisar_earth_in_motion_demo.mp4.
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
const OUTPUT_MP4 = resolve(REPO_ROOT, "artifacts/demo/nisar_earth_in_motion_demo.mp4");
const TEMP_DIR = resolve(REPO_ROOT, "artifacts/demo/temp");
const FRAMES_DIR = resolve(TEMP_DIR, "frames");
const AUDIO_DIR = resolve(TEMP_DIR, "audio");

const CHROME_PATH =
  process.env.CHROME_PATH || "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";

const TOTAL_SECONDS = 90;
const FPS = 30;
const TOTAL_FRAMES = TOTAL_SECONDS * FPS; // 2700 frames

const NARRATION_SCENES = [
  {
    index: 1,
    name: "scene1",
    startSec: 0.0,
    endSec: 12.0,
    audioStartSec: 0.5,
    text: "NISAR, the NASA-ISRO Synthetic Aperture Radar mission, operates on a 12-day repeat cycle. Its L-band radar enables scientists to observe Earth's surface through clouds, smoke and darkness.",
  },
  {
    index: 2,
    name: "scene2",
    startSec: 12.0,
    endSec: 25.0,
    audioStartSec: 12.5,
    text: "In June 2026, two major earthquakes struck northern Venezuela within approximately 32 seconds. We built an interactive explorer using authentic NISAR Level-2 interferometric data from Ascending Track 162, covering June 13 to June 25.",
  },
  {
    index: 3,
    name: "scene3",
    startSec: 25.0,
    endSec: 38.0,
    audioStartSec: 25.5,
    text: "The original HDF5 product is approximately 2.34 gigabytes. A major engineering challenge was resolving its multiple spatial resolutions. By reading the coordinate scales attached to each raster, our pipeline avoids a four-times coordinate mismatch and preserves correct georeferencing.",
  },
  {
    index: 4,
    name: "scene4",
    startSec: 38.0,
    endSec: 58.0,
    audioStartSec: 38.5,
    text: "The explorer presents unwrapped interferometric phase in radians and coherence as a measurement-quality indicator. Around the M 7.2 event, the 1.6-kilometer median coherence is approximately 0.406. Around the M 7.5 event, it is approximately 0.077. The epicenters are about 148 kilometers apart. These differences describe measurement reliability, not proof of earthquake damage.",
  },
  {
    index: 5,
    name: "scene5",
    startSec: 58.0,
    endSec: 78.0,
    audioStartSec: 59.0,
    text: "Scientific honesty is built into the application. We do not label phase as centimeters of ground movement or claim that coherence loss proves damage. The system exports georeferenced GeoTIFFs, metadata and scientific reports for further investigation.",
  },
  {
    index: 6,
    name: "scene6",
    startSec: 78.0,
    endSec: 90.0,
    audioStartSec: 79.0,
    text: "NISAR: Earth in Motion. Making complex radar science more accessible, reproducible and understandable.",
  },
];

function log(msg) {
  process.stdout.write(`[record_demo] ${msg}\n`);
}

function ensureDirectories() {
  mkdirSync(resolve(REPO_ROOT, "artifacts/demo"), { recursive: true });
  mkdirSync(TEMP_DIR, { recursive: true });
  mkdirSync(FRAMES_DIR, { recursive: true });
  mkdirSync(AUDIO_DIR, { recursive: true });
}

function synthesizeAudio() {
  log("Synthesizing narration audio tracks via PowerShell System.Speech...");
  const psScriptPath = resolve(TEMP_DIR, "synth_narration.ps1");
  const scriptLines = [
    "Add-Type -AssemblyName System.Speech",
    "$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer",
    '$synth.SelectVoice("Microsoft David Desktop")',
    "$synth.Rate = 2",
    "",
  ];

  for (const s of NARRATION_SCENES) {
    const wavPath = resolve(AUDIO_DIR, `${s.name}.wav`).replace(/\\/g, "/");
    scriptLines.push(`$synth.SetOutputToWaveFile("${wavPath}")`);
    scriptLines.push(`$synth.Speak("${s.text.replace(/"/g, '`"')}")`);
  }
  scriptLines.push("$synth.Dispose()");

  writeFileSync(psScriptPath, scriptLines.join("\r\n"), "utf-8");
  execSync(`powershell -ExecutionPolicy Bypass -File "${psScriptPath}"`, { stdio: "inherit" });

  log("Assembling continuous 90-second audio mix with FFmpeg...");
  const filterInputs = [];
  const delayFilters = [];
  const mixInputs = ["[6:a]"];

  for (let i = 0; i < NARRATION_SCENES.length; i++) {
    const s = NARRATION_SCENES[i];
    const wavPath = resolve(AUDIO_DIR, `${s.name}.wav`).replace(/\\/g, "/");
    filterInputs.push(`-i "${wavPath}"`);
    const delayMs = Math.round(s.audioStartSec * 1000);
    delayFilters.push(`[${i}:a]adelay=${delayMs}|${delayMs}[a${i + 1}]`);
    mixInputs.push(`[a${i + 1}]`);
  }

  const mixFilter = `${delayFilters.join("; ")}; ${mixInputs.join("")}amix=inputs=${
    mixInputs.length
  }:duration=first:dropout_transition=0,volume=2.0[aout]`;
  const mixedAudioPath = resolve(AUDIO_DIR, "mixed_90s.m4a").replace(/\\/g, "/");

  const ffmpegCmd = [
    "ffmpeg -y",
    filterInputs.join(" "),
    `-f lavfi -t ${TOTAL_SECONDS} -i anullsrc=channel_layout=stereo:sample_rate=48000`,
    `-filter_complex "${mixFilter}"`,
    `-map "[aout]" -c:a aac -b:a 192k "${mixedAudioPath}"`,
  ].join(" ");

  execSync(ffmpegCmd, { stdio: "inherit" });
  log(`Master audio assembled -> ${mixedAudioPath}`);
  return mixedAudioPath;
}

function generateSubtitles() {
  log("Generating SubRip (.srt) and Advanced SubStation Alpha (.ass) subtitles...");
  const srtPath = resolve(TEMP_DIR, "subtitles.srt");
  const assPath = resolve(TEMP_DIR, "subtitles.ass");

  function toSrtTime(sec) {
    const totalMs = Math.round(sec * 1000);
    const ms = totalMs % 1000;
    const totalS = Math.floor(totalMs / 1000);
    const s = totalS % 60;
    const totalM = Math.floor(totalS / 60);
    const m = totalM % 60;
    const h = Math.floor(totalM / 60);
    const pad = (n, w = 2) => String(n).padStart(w, "0");
    return `${pad(h)}:${pad(m)}:${pad(s)},${pad(ms, 3)}`;
  }

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

  const srtEntries = [
    {
      index: 1,
      start: 0.5,
      end: 11.5,
      text: "NISAR, the NASA–ISRO Synthetic Aperture Radar mission, operates on a 12-day repeat cycle.\nIts L-band radar enables scientists to observe Earth's surface through clouds, smoke and darkness.",
    },
    {
      index: 2,
      start: 12.5,
      end: 24.5,
      text: "In June 2026, two major earthquakes struck northern Venezuela within approximately 32 seconds.\nWe built an interactive explorer using authentic NISAR Level-2 interferometric data from Ascending Track 162.",
    },
    {
      index: 3,
      start: 25.5,
      end: 37.5,
      text: "The original HDF5 product is approximately 2.34 gigabytes. A major engineering challenge was resolving its multiple spatial resolutions.\nBy reading attached coordinate scales, our pipeline avoids a 4× coordinate mismatch and preserves georeferencing.",
    },
    {
      index: 4,
      start: 38.5,
      end: 57.5,
      text: "The explorer presents unwrapped phase in radians and coherence as a measurement-quality indicator.\nM7.2 median coherence is 0.406; M7.5 is 0.077 (separated by 148 km). These differences describe measurement reliability, not damage.",
    },
    {
      index: 5,
      start: 59.0,
      end: 77.0,
      text: "Scientific honesty is built into the application. We do not label phase as centimetres or claim coherence loss proves damage.\nThe system exports georeferenced GeoTIFFs, metadata, and scientific reports for further investigation.",
    },
    {
      index: 6,
      start: 79.0,
      end: 89.0,
      text: "NISAR // Earth in Motion.\nMaking complex radar science more accessible, reproducible, and understandable.",
    },
  ];

  const srtContent = srtEntries
    .map((e) => `${e.index}\n${toSrtTime(e.start)} --> ${toSrtTime(e.end)}\n${e.text}\n`)
    .join("\n");
  writeFileSync(srtPath, srtContent, "utf-8");

  const assLines = [
    "[Script Info]",
    "Title: NISAR Earth in Motion Demo Subtitles",
    "ScriptType: v4.00+",
    "WrapStyle: 0",
    "ScaledBorderAndShadow: yes",
    "PlayResX: 1920",
    "PlayResY: 1080",
    "",
    "[V4+ Styles]",
    "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
    "Style: Default,Arial,30,&H00FFFFFF,&H000000FF,&H00000000,&H90050C1C,0,0,0,0,100,100,0,0,4,0,0,2,100,100,36,1",
    "",
    "[Events]",
    "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
  ];

  for (const e of srtEntries) {
    const formatted = e.text.replace(/\n/g, "\\N");
    assLines.push(`Dialogue: 0,${toAssTime(e.start)},${toAssTime(e.end)},Default,,0,0,0,,${formatted}`);
  }
  writeFileSync(assPath, assLines.join("\r\n"), "utf-8");

  log(`Subtitles written -> ${srtPath} and ${assPath}`);
  return assPath;
}

async function captureApplicationFrames() {
  log("Connecting to Chrome and capturing authentic application footage...");
  if (!existsSync(CHROME_PATH)) {
    throw new Error(`Chrome not found at: ${CHROME_PATH}`);
  }

  const profile = mkdtempSync(join(tmpdir(), "nisar-record-"));
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
    { stdio: ["ignore", "ignore", "pipe"] },
  );

  let endpoint = null;
  const portFile = join(profile, "DevToolsActivePort");
  for (let i = 0; i < 150 && !endpoint; i += 1) {
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
      throw new Error(`Eval error: ${res.exceptionDetails.text}`);
    }
    return res.result.value;
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

  log("Loading application at " + BASE_URL);
  await send("Page.navigate", { url: BASE_URL + "/" });
  await sleep(1500);

  // Style customization helper to add elegant aerospace captions
  await evaluate(`(() => {
    const overlay = document.createElement("div");
    overlay.id = "video-aerospace-hud";
    overlay.style.position = "fixed";
    overlay.style.top = "24px";
    overlay.style.left = "32px";
    overlay.style.zIndex = "999999";
    overlay.style.display = "flex";
    overlay.style.flexDirection = "column";
    overlay.style.gap = "6px";
    overlay.style.pointerEvents = "none";
    overlay.style.fontFamily = "monospace, system-ui, sans-serif";
    overlay.innerHTML = \`
      <div id="hud-badge" style="background: rgba(10, 25, 47, 0.85); border: 1px solid rgba(0, 229, 255, 0.4); border-left: 4px solid #00E5FF; padding: 6px 14px; border-radius: 4px; backdrop-filter: blur(8px); display: inline-flex; align-items: center; gap: 10px;">
        <span style="display:inline-block; width:8px; height:8px; border-radius:50%; background:#00E5FF; box-shadow:0 0 8px #00E5FF;"></span>
        <span id="hud-title" style="color: #FFFFFF; font-weight: 700; font-size: 13px; letter-spacing: 1px;">NISAR // EARTH IN MOTION</span>
        <span id="hud-subtitle" style="color: #64FFDA; font-size: 11px; padding-left: 8px; border-left: 1px solid rgba(255,255,255,0.2);">SCENE 1: PLANETARY ORBIT</span>
      </div>
      <div id="hud-callout" style="display:none; background: rgba(5, 12, 28, 0.9); border: 1px solid rgba(100, 255, 218, 0.3); padding: 8px 12px; border-radius: 4px; max-width: 480px; color: #E2E8F0; font-size: 11px; line-height: 1.4;">
      </div>
    \`;
    document.body.appendChild(overlay);
  })()`);

  async function updateHud(title, subtitle, calloutHtml = null) {
    await evaluate(`(() => {
      const t = document.getElementById("hud-title");
      const s = document.getElementById("hud-subtitle");
      const c = document.getElementById("hud-callout");
      if (t) t.textContent = "${title}";
      if (s) s.textContent = "${subtitle}";
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

  // ==========================================
  // SCENE 1: 0.0s - 12.0s (360 frames: 1 to 360)
  // Earth reveal, dual green tracking strokes, satellite orbit
  // ==========================================
  log("Capturing Scene 1: Planetary Opening & Orbit (0–12s)...");
  await updateHud(
    "NISAR // EARTH IN MOTION",
    "PLANETARY OPENING · 12-DAY REPEAT CYCLE",
    "<strong>MISSION:</strong> NASA-ISRO Synthetic Aperture Radar (NISAR)<br><strong>BAND:</strong> L-Band Microwave (1.239 GHz, λ ≈ 24.2 cm)<br><em>Illustrative Mission Visualization</em>",
  );

  for (let i = 0; i < 45; i++) {
    const buf = await snapFrame();
    duplicateFrames(buf, 8); // 45 * 8 = 360 frames = exactly 12.0s
    await sleep(40);
  }

  while (currentFrameNumber <= 360) {
    const buf = await snapFrame();
    writeFrameFile(currentFrameNumber++, buf);
  }

  // ==========================================
  // SCENE 2: 12.0s - 25.0s (390 frames: 361 to 750)
  // Dashboard & Northern Venezuela 2026 Case Study
  // ==========================================
  log("Capturing Scene 2: Research Challenge (12–25s)...");
  await evaluate("window.scrollTo({ top: 620, behavior: 'instant' })");
  await sleep(400);

  await updateHud(
    "RESEARCH CHALLENGE",
    "NORTHERN VENEZUELA 2026 · ASCENDING TRACK 162",
    "<strong>EVENT SEQUENCE:</strong> 24 June 2026 Doublet (32.2s separation)<br><strong>FORESHOCK:</strong> M7.2 (San Felipe, Yaracuy) · <strong>MAINSHOCK:</strong> M7.5 (Catia La Mar)<br><strong>SEPARATION:</strong> 148.33 km · <strong>PRODUCT:</strong> NISAR Level-2 GUNW",
  );

  await evaluate(`(() => {
    const card = document.querySelector('#observation-cards .card');
    if (card) {
      card.style.outline = "2px solid #00E5FF";
      card.style.boxShadow = "0 0 24px rgba(0, 229, 255, 0.4)";
    }
  })()`);

  for (let i = 0; i < 39; i++) {
    const buf = await snapFrame();
    duplicateFrames(buf, 10); // 39 * 10 = 390 frames = 13.0s
    await sleep(30);
  }

  while (currentFrameNumber <= 750) {
    const buf = await snapFrame();
    writeFrameFile(currentFrameNumber++, buf);
  }

  // ==========================================
  // SCENE 3: 25.0s - 38.0s (390 frames: 751 to 1140)
  // Engineering Achievement: HDF5 Dimension Scales
  // ==========================================
  log("Capturing Scene 3: Engineering Achievement (25–38s)...");
  await evaluate(`(async () => {
    showView("explorer");
    await openObservation("venezuela");
    window.scrollTo({ top: 0, behavior: 'instant' });
  })()`);
  await sleep(1500);

  await updateHud(
    "ENGINEERING ACHIEVEMENT",
    "HDF5 DIMENSION-SCALE RESOLUTION",
    "<strong>GRANULE SIZE:</strong> 2.34 GB HDF5<br><strong>GRID POSTING:</strong> 80 m × 80 m (4,149 × 4,239 pixels, EPSG:32619)<br><strong>BREAKTHROUGH:</strong> Direct resolution of attached DIMENSION_LIST scales eliminates 4× wrapped coordinate mismatch.",
  );

  for (let i = 0; i < 39; i++) {
    const buf = await snapFrame();
    duplicateFrames(buf, 10); // 39 * 10 = 390 frames = 13.0s
    await sleep(30);
  }

  while (currentFrameNumber <= 1140) {
    const buf = await snapFrame();
    writeFrameFile(currentFrameNumber++, buf);
  }

  // ==========================================
  // SCENE 4: 38.0s - 58.0s (600 frames: 1141 to 1740)
  // Interactive Scientific Explorer: Phase, Coherence, Markers
  // ==========================================
  log("Capturing Scene 4: Interactive Scientific Explorer (38–58s)...");

  // Subscene 4A: Phase layer in radians (5s / 150 frames)
  await updateHud(
    "SCIENTIFIC EXPLORER",
    "UNWRAPPED PHASE · RADIANS (MULTI-CYCLE)",
    "<strong>UNITS:</strong> Radians (native product unit)<br><strong>COLORMAP:</strong> Viridis (sequential, no false zero)<br><strong>OBSERVATION:</strong> Spans multiple 2π cycles after ellipsoidal flattening.",
  );
  for (let i = 0; i < 15; i++) {
    const buf = await snapFrame();
    duplicateFrames(buf, 10);
    await sleep(20);
  }

  // Subscene 4B: Switch to Coherence layer & Threshold slider (5s / 150 frames)
  await evaluate(`(() => {
    const tab = document.querySelector('#layer-tabs [data-layer="coherence"]');
    if (tab) tab.click();
    const slider = document.getElementById("threshold-slider");
    if (slider) {
      slider.value = "0.4";
      slider.dispatchEvent(new Event("input", { bubbles: true }));
      slider.dispatchEvent(new Event("change", { bubbles: true }));
    }
  })()`);
  await sleep(400);

  await updateHud(
    "SCIENTIFIC EXPLORER",
    "COHERENCE THRESHOLD · MEASUREMENT QUALITY",
    "<strong>METRIC:</strong> Coherence magnitude (0.0 to 1.0)<br><strong>THRESHOLD:</strong> 0.4 filter isolates 2.94M reliable pixels (16.7% coverage)<br><strong>PURPOSE:</strong> Masks temporal and vegetation decorrelation.",
  );
  for (let i = 0; i < 15; i++) {
    const buf = await snapFrame();
    duplicateFrames(buf, 10);
    await sleep(20);
  }

  // Subscene 4C: M7.2 Foreshock epicentre hover inspection (5s / 150 frames)
  await updateHud(
    "EVENT INSPECTION",
    "M7.2 FORESHOCK · 1.6 KM MEDIAN COHERENCE 0.406",
    "<strong>LOCATION:</strong> 20 km E of San Felipe, Yaracuy (10.37°N, 68.56°W)<br><strong>LOCAL COHERENCE:</strong> 0.406 median (1.6 km window) · 0.708 nearest pixel<br><strong>STATUS:</strong> Stable radar backscatter, phase relationship preserved.",
  );
  await evaluate(`(() => {
    const tip = document.getElementById("pixel-inspect-tooltip") || document.createElement("div");
    tip.id = "demo-event-tooltip";
    tip.style.position = "fixed";
    tip.style.bottom = "120px";
    tip.style.left = "420px";
    tip.style.zIndex = "99999";
    tip.style.background = "rgba(5, 12, 28, 0.95)";
    tip.style.border = "1px solid #64FFDA";
    tip.style.padding = "10px 16px";
    tip.style.borderRadius = "6px";
    tip.style.color = "#FFFFFF";
    tip.style.fontFamily = "monospace";
    tip.style.boxShadow = "0 0 20px rgba(100, 255, 218, 0.4)";
    tip.innerHTML = "<strong>USGS EVENT: M7.2 Foreshock (us6000t7zc)</strong><br>Coords: 10.3713°N, 68.5564°W | Depth: 10.0 km<br>1.6 km Window Median Coherence: <strong>0.406</strong> (usable phase)";
    document.body.appendChild(tip);
  })()`);

  for (let i = 0; i < 15; i++) {
    const buf = await snapFrame();
    duplicateFrames(buf, 10);
    await sleep(20);
  }

  // Subscene 4D: M7.5 Mainshock epicentre inspection (5s / 150 frames)
  await updateHud(
    "EVENT INSPECTION",
    "M7.5 MAINSHOCK · 1.6 KM MEDIAN COHERENCE 0.077",
    "<strong>LOCATION:</strong> 20 km W of Catia La Mar (10.60°N, 67.22°W)<br><strong>SEPARATION:</strong> 148.33 km ENE along coastal fault system<br><strong>COHERENCE:</strong> 0.077 median (severe coastal decorrelation; unreliable phase).",
  );
  await evaluate(`(() => {
    const tip = document.getElementById("demo-event-tooltip");
    if (tip) {
      tip.style.left = "580px";
      tip.style.bottom = "140px";
      tip.style.borderColor = "#FF5252";
      tip.style.boxShadow = "0 0 20px rgba(255, 82, 82, 0.4)";
      tip.innerHTML = "<strong>USGS EVENT: M7.5 Mainshock (us6000t7zp)</strong><br>Coords: 10.5955°N, 67.2205°W | Depth: 10.0 km<br>1.6 km Window Median Coherence: <strong>0.077</strong> (severe decorrelation)";
    }
  })()`);

  for (let i = 0; i < 15; i++) {
    const buf = await snapFrame();
    duplicateFrames(buf, 10);
    await sleep(20);
  }

  // Remove event tooltip
  await evaluate(`(() => {
    const tip = document.getElementById("demo-event-tooltip");
    if (tip) tip.remove();
  })()`);

  while (currentFrameNumber <= 1740) {
    const buf = await snapFrame();
    writeFrameFile(currentFrameNumber++, buf);
  }

  // ==========================================
  // SCENE 5: 58.0s - 78.0s (600 frames: 1741 to 2340)
  // Scientific Integrity & Data Export Suite
  // ==========================================
  log("Capturing Scene 5: Scientific Integrity & Export (58–78s)...");

  await evaluate("window.scrollTo({ top: 920, behavior: 'instant' })");
  await sleep(400);

  await updateHud(
    "SCIENTIFIC HONESTY & GUARDRAILS",
    "INTERPRETATION: NOT VALIDATED",
    "<strong>1. NO ARBITRARY DISPLACEMENT:</strong> Sign convention unvalidated; phase in radians.<br><strong>2. NO GPS ZERO-ANCHOR:</strong> Relative interferometry requires ground truth.<br><strong>3. ATMOSPHERIC DELAYS:</strong> Water vapor & ionosphere remain in phase.<br><strong>4. RESIDUAL RAMPS:</strong> Orbital geometry errors present.",
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
    "<strong>GeoTIFF:</strong> Georeferenced EPSG:32619 raster for QGIS/ArcGIS<br><strong>Quicklook:</strong> Publication PNG with embedded provenance metadata footer<br><strong>Scientific Report:</strong> Comprehensive audit trail and parameters in Markdown.",
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

  // ==========================================
  // SCENE 6: 78.0s - 90.0s (360 frames: 2341 to 2700)
  // Mission Closing & Open-Source Reproducibility
  // ==========================================
  log("Capturing Scene 6: Mission Closing (78–90s)...");
  await evaluate(`(async () => {
    showView("dashboard");
    window.scrollTo({ top: 0, behavior: 'instant' });
    const hud = document.getElementById("video-aerospace-hud");
    if (hud) hud.style.display = "none";
  })()`);
  await sleep(500);

  // Inject sleek aerospace closing card
  await evaluate(`(() => {
    const card = document.createElement("div");
    card.id = "closing-title-card";
    card.style.position = "fixed";
    card.style.inset = "0";
    card.style.zIndex = "9999999";
    card.style.background = "radial-gradient(ellipse at center, rgba(10, 25, 47, 0.95) 0%, rgba(2, 6, 18, 0.98) 100%)";
    card.style.display = "flex";
    card.style.flexDirection = "column";
    card.style.alignItems = "center";
    card.style.justifyContent = "center";
    card.style.fontFamily = "system-ui, -apple-system, sans-serif";
    card.style.color = "#FFFFFF";
    card.style.textAlign = "center";
    card.innerHTML = \`
      <div style="font-size: 13px; font-weight: 700; letter-spacing: 4px; color: #00E5FF; margin-bottom: 12px; text-transform: uppercase;">NASA Space Apps Challenge 2026 · Dancing with the SARs</div>
      <h1 style="font-size: 54px; font-weight: 900; letter-spacing: 2px; margin: 0 0 16px 0; background: linear-gradient(135deg, #FFFFFF 0%, #E2E8F0 60%, #64FFDA 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">NISAR // EARTH IN MOTION</h1>
      <p style="font-size: 19px; color: #94A3B8; max-width: 680px; line-height: 1.6; margin: 0 0 32px 0;">Transforming raw NASA-ISRO Synthetic Aperture Radar products into transparent, rigorous, and accessible Earth science.</p>
      <div style="display: flex; gap: 16px; margin-bottom: 36px;">
        <span style="background: rgba(0, 229, 255, 0.1); border: 1px solid rgba(0, 229, 255, 0.4); padding: 8px 16px; border-radius: 6px; font-size: 13px; font-family: monospace; color: #00E5FF;">EPSG:32619 · 80m Grid</span>
        <span style="background: rgba(100, 255, 218, 0.1); border: 1px solid rgba(100, 255, 218, 0.4); padding: 8px 16px; border-radius: 6px; font-size: 13px; font-family: monospace; color: #64FFDA;">HDF5 Dimension Scales</span>
        <span style="background: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.2); padding: 8px 16px; border-radius: 6px; font-size: 13px; font-family: monospace; color: #F8FAFC;">100% Offline Capable</span>
      </div>
      <div style="font-family: monospace; font-size: 15px; color: #64FFDA; padding: 10px 24px; border: 1px solid rgba(100, 255, 218, 0.4); border-radius: 8px; background: rgba(5, 12, 28, 0.8);">
        github.com/Aayushashsahu/LunaHorizon
      </div>
    \`;
    document.body.appendChild(card);
  })()`);
  await sleep(300);

  const titleBuf = await snapFrame();
  duplicateFrames(titleBuf, 315);

  await evaluate(`(() => {
    const card = document.getElementById("closing-title-card");
    if (card) {
      card.style.background = "#000000";
      card.style.opacity = "1";
      card.innerHTML = "";
    }
  })()`);
  await sleep(200);
  const blackBuf = await snapFrame();
  duplicateFrames(blackBuf, 45);

  child.kill();
  try {
    rmSync(profile, { recursive: true, force: true });
  } catch {}

  log(`Frame capture complete! Total frames generated: ${currentFrameNumber - 1}`);
}

function encodeFinalVideo(audioPath, assPath) {
  log("Encoding 1080p 30 FPS MP4 video with FFmpeg...");
  const framesPattern = "artifacts/demo/temp/frames/frame_%05d.jpg";
  const normAudioPath = "artifacts/demo/temp/audio/mixed_90s.m4a";
  const normAssPath = "artifacts/demo/temp/subtitles.ass";
  const normOutputMp4 = "artifacts/demo/nisar_earth_in_motion_demo.mp4";

  const ffmpegCmd = [
    "ffmpeg -y",
    `-framerate ${FPS}`,
    `-i "${framesPattern}"`,
    `-i "${normAudioPath}"`,
    `-vf "ass=${normAssPath}"`,
    "-c:v libx264 -preset fast -profile:v high -level 4.2 -pix_fmt yuv420p -crf 20",
    "-c:a aac -b:a 192k",
    `-t ${TOTAL_SECONDS}`,
    "-movflags +faststart",
    `"${normOutputMp4}"`,
  ].join(" ");

  log(`Running command: ${ffmpegCmd}`);
  execSync(ffmpegCmd, { stdio: "inherit" });
  log(`Final demonstration video rendered successfully -> ${OUTPUT_MP4}`);
}

function validateRenderedVideo() {
  log("Validating rendered MP4 with ffprobe...");
  if (!existsSync(OUTPUT_MP4)) {
    throw new Error(`Rendered video does not exist: ${OUTPUT_MP4}`);
  }

  const probeJson = execSync(
    `ffprobe -v error -print_format json -show_format -show_streams "${OUTPUT_MP4}"`,
    { encoding: "utf-8" },
  );
  const probe = JSON.parse(probeJson);

  const vStream = probe.streams.find((s) => s.codec_type === "video");
  const aStream = probe.streams.find((s) => s.codec_type === "audio");
  const duration = parseFloat(probe.format.duration);

  log(`=== VIDEO VERIFICATION METRICS ===`);
  log(`Path: ${OUTPUT_MP4}`);
  log(`File Size: ${(probe.format.size / (1024 * 1024)).toFixed(2)} MB`);
  log(`Duration: ${duration.toFixed(2)} seconds (Target: ${TOTAL_SECONDS}s)`);
  log(`Resolution: ${vStream.width} × ${vStream.height} (Target: 1920 × 1080)`);
  log(`Frame Rate: ${vStream.r_frame_rate} (Target: 30/1)`);
  log(`Video Codec: ${vStream.codec_name} (${vStream.profile})`);
  log(`Audio Codec: ${aStream ? aStream.codec_name : "none"} (${aStream ? aStream.sample_rate + " Hz" : ""})`);
  log(`Audio Channels: ${aStream ? aStream.channels : 0}`);

  if (vStream.width !== 1920 || vStream.height !== 1080) {
    throw new Error(`Invalid resolution: ${vStream.width}x${vStream.height}`);
  }
  if (Math.abs(duration - TOTAL_SECONDS) > 1.5) {
    throw new Error(`Video duration mismatch: expected ${TOTAL_SECONDS}s, got ${duration}s`);
  }
  if (!aStream) {
    throw new Error("No audio stream detected in MP4.");
  }

  log("Extracting representative frames for verification...");
  execSync(
    `ffmpeg -y -ss 00:00:06 -i "${OUTPUT_MP4}" -vframes 1 "artifacts/demo/scene1_opening.jpg"`,
    { stdio: "ignore" },
  );
  execSync(
    `ffmpeg -y -ss 00:00:18 -i "${OUTPUT_MP4}" -vframes 1 "artifacts/demo/scene2_challenge.jpg"`,
    { stdio: "ignore" },
  );
  execSync(
    `ffmpeg -y -ss 00:00:32 -i "${OUTPUT_MP4}" -vframes 1 "artifacts/demo/scene3_engineering.jpg"`,
    { stdio: "ignore" },
  );
  execSync(
    `ffmpeg -y -ss 00:00:48 -i "${OUTPUT_MP4}" -vframes 1 "artifacts/demo/scene4_explorer.jpg"`,
    { stdio: "ignore" },
  );
  execSync(
    `ffmpeg -y -ss 00:01:08 -i "${OUTPUT_MP4}" -vframes 1 "artifacts/demo/scene5_limitations.jpg"`,
    { stdio: "ignore" },
  );
  execSync(
    `ffmpeg -y -ss 00:01:24 -i "${OUTPUT_MP4}" -vframes 1 "artifacts/demo/scene6_closing.jpg"`,
    { stdio: "ignore" },
  );
  log("Verification frames extracted successfully.");
}

async function main() {
  try {
    log("=== STARTING LUNAHORIZON DEMO VIDEO PRODUCTION ===");
    ensureDirectories();
    const audioPath = synthesizeAudio();
    const assPath = generateSubtitles();
    await captureApplicationFrames();
    encodeFinalVideo(audioPath, assPath);
    validateRenderedVideo();
    log("=== VIDEO PRODUCTION COMPLETED SUCCESSFULLY ===");
  } catch (err) {
    console.error("FATAL ERROR in video production:", err);
    process.exit(1);
  }
}

main();
