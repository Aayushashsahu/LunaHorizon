import { spawn } from "node:child_process";
import { readFileSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { setTimeout as sleep } from "node:timers/promises";

const BASE_URL = "http://127.0.0.1:8000";
const CHROME_PATH = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";

async function runBenchmark() {
  const profile = mkdtempSync(join(tmpdir(), "bench-"));
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
  for (let i = 0; i < 150 && !endpoint; i++) {
    try {
      const lines = readFileSync(portFile, "utf-8").split(/\r?\n/);
      if (lines[0]) endpoint = Number(lines[0]);
    } catch {}
    if (!endpoint) await sleep(100);
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
    return res.result?.value;
  };

  await send("Page.enable");
  await send("Runtime.enable");

  const results = {};

  // 1. Dashboard Usable + Navigation
  const tNavStart = performance.now();
  await send("Page.navigate", { url: BASE_URL + "/" });

  // Wait for DOMContentLoaded and app init
  let connectedTime = null;
  let cardsTime = null;
  for (let i = 0; i < 100; i++) {
    const status = await evaluate(`(() => {
      const s = document.getElementById("server-status");
      const isConnected = s && s.classList.contains("connected");
      const cards = document.querySelectorAll("#observation-cards .card");
      return { connected: isConnected, cardCount: cards.length };
    })()`);
    if (status.connected && connectedTime === null) {
      connectedTime = performance.now() - tNavStart;
    }
    if (status.cardCount > 0 && cardsTime === null) {
      cardsTime = performance.now() - tNavStart;
    }
    if (connectedTime !== null && cardsTime !== null) break;
    await sleep(25);
  }
  const dashboardUsable = cardsTime;

  results["Dashboard usable"] = `${Math.round(dashboardUsable)} ms`;
  results["Server connected"] = `${Math.round(connectedTime)} ms`;
  results["Observation cards populated"] = `${Math.round(cardsTime)} ms`;

  // 4. Explorer Opening
  const tExpStart = performance.now();
  await evaluate(`(async () => {
    showView("explorer");
    await openObservation("venezuela");
  })()`);
  const expOpening = performance.now() - tExpStart;
  results["Explorer opening"] = `${Math.round(expOpening)} ms`;

  // 5. Phase Rendering
  const tPhaseStart = performance.now();
  const phasePainted = await evaluate(`(() => {
    const canvas = document.getElementById("map-canvas");
    if (!canvas) return false;
    const ctx = canvas.getContext("2d");
    const data = ctx.getImageData(canvas.width / 2, canvas.height / 2, 1, 1).data;
    return data[3] > 0;
  })()`);
  const phaseRendering = performance.now() - tPhaseStart;
  results["Phase rendering"] = `${Math.round(phaseRendering)} ms (painted: ${phasePainted})`;

  // 6. Coherence Switching
  const tCohStart = performance.now();
  await evaluate(`(() => {
    const tab = document.querySelector('#layer-tabs [data-layer="coherence"]');
    if (tab) tab.click();
  })()`);
  await sleep(50);
  const cohSwitching = performance.now() - tCohStart;
  results["Coherence switching"] = `${Math.round(cohSwitching)} ms`;

  // 7. Slider Input Latency
  const tSliderStart = performance.now();
  await evaluate(`(() => {
    const slider = document.getElementById("threshold-slider");
    if (slider) {
      slider.value = "0.5";
      slider.dispatchEvent(new Event("input", { bubbles: true }));
      slider.dispatchEvent(new Event("change", { bubbles: true }));
    }
  })()`);
  const sliderLatency = performance.now() - tSliderStart;
  results["Slider input"] = `${Math.round(sliderLatency)} ms`;

  // 8. Pixel Tooltip Latency
  const tTooltipStart = performance.now();
  await send("Input.dispatchMouseEvent", { type: "mouseMoved", x: 660, y: 525, modifiers: 0 });
  await sleep(30);
  const tooltipLatency = performance.now() - tTooltipStart;
  results["Pixel tooltip"] = `${Math.round(tooltipLatency)} ms`;

  // 9. Export Initiation
  const tExportStart = performance.now();
  await evaluate(`(() => {
    const btn = document.querySelector('[data-download-json]');
    if (btn) btn.click();
  })()`);
  const exportLatency = performance.now() - tExportStart;
  results["Export initiation"] = `${Math.round(exportLatency)} ms`;

  child.kill();
  try { rmSync(profile, { recursive: true, force: true }); } catch {}

  console.log(JSON.stringify(results, null, 2));
}

runBenchmark().catch((err) => {
  console.error("Benchmark error:", err);
  process.exit(1);
});
