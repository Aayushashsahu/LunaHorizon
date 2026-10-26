#!/usr/bin/env node
/**
 * Browser smoke test for NISAR // Earth in Motion.
 *
 * Launches a headless Chrome against the running local server and exercises the
 * real controls over the Chrome DevTools Protocol — no frameworks, no npm
 * install. Three scenarios:
 *
 *   A. healthy boot  — connection state, observation cards, Dashboard <-> Explorer
 *      navigation (mouse and keyboard), layer switching, coherence threshold,
 *      exports, limitations, canvas actually painting pixels.
 *   B. API outage    — /api/index is forced to fail: the indicator must reach an
 *      "unavailable" state (never stuck on "connecting"), the dashboard must show
 *      an actionable message, navigation must still work, and the retry button
 *      must recover once the API returns.
 *   C. bad observation — opening a non-existent observation must surface an
 *      understandable error instead of doing nothing.
 *
 * Usage:
 *   node scripts/browser_smoke.mjs http://127.0.0.1:8000 [screenshot.png]
 *
 * Environment:
 *   CHROME_PATH  explicit Chrome/Chromium executable (auto-detected otherwise)
 *
 * Exit code: 0 = every check passed, 1 = failures, 2 = browser unavailable.
 */

import { spawn } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { setTimeout as sleep } from "node:timers/promises";

const BASE = (process.argv[2] || "http://127.0.0.1:8000").replace(/\/$/, "");
const SCREENSHOT = process.argv[3] || null;

const CHROME_CANDIDATES = [
  process.env.CHROME_PATH,
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
  "/usr/bin/google-chrome",
  "/usr/bin/chromium",
  "/usr/bin/chromium-browser",
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
].filter(Boolean);

const results = [];
const pageErrors = [];
let consoleErrors = [];
let badResponses = [];
let scenario = "setup";

function check(name, ok, detail = "") {
  results.push({ scenario, name, ok: Boolean(ok), detail: String(detail) });
  if (!ok) process.stdout.write(`FAIL  [${scenario}] ${name}${detail ? ` — ${detail}` : ""}\n`);
}

function findChrome() {
  // Deliberately no `--version` probe: some Windows Chrome builds ignore it and
  // open a real browser window instead. An existing executable is good enough.
  for (const candidate of CHROME_CANDIDATES) {
    if (existsSync(candidate)) return candidate;
  }
  return null;
}

const FETCH_OVERRIDE = `
  window.__nisarFailIndex = true;
  if (!window.__nisarPatched) {
    window.__nisarPatched = true;
    const originalFetch = window.fetch.bind(window);
    window.fetch = (input, init) => {
      const url = typeof input === "string" ? input : (input && input.url) || "";
      if (window.__nisarFailIndex && url.indexOf("/api/index") !== -1) {
        return Promise.reject(new TypeError("simulated /api/index outage (test)"));
      }
      return originalFetch(input, init);
    };
  }
`;

async function main() {
  const chrome = findChrome();
  if (!chrome) {
    console.error("SKIP: no Chrome/Chromium found; set CHROME_PATH to run browser checks.");
    process.exit(2);
  }

  const profile = mkdtempSync(join(tmpdir(), "nisar-eim-chrome-"));
  const child = spawn(
    chrome,
    [
      "--headless=new",
      "--disable-gpu",
      "--no-first-run",
      "--no-default-browser-check",
      "--remote-allow-origins=*",
      `--user-data-dir=${profile}`,
      "--remote-debugging-port=0",
      "about:blank",
    ],
    { stdio: ["ignore", "ignore", "pipe"] },
  );
  child.stderr.on("data", () => {});

  let endpoint = null;
  const portFile = join(profile, "DevToolsActivePort");
  for (let i = 0; i < 120 && !endpoint; i += 1) {
    try {
      const lines = readFileSync(portFile, "utf-8").split(/\r?\n/);
      if (lines[0]) endpoint = Number(lines[0]);
    } catch {
      /* not written yet */
    }
    if (!endpoint) await sleep(100);
  }
  if (!endpoint) {
    child.kill();
    console.error("FAIL: Chrome did not expose a DevTools endpoint.");
    process.exit(1);
  }

  const targets = await (await fetch(`http://127.0.0.1:${endpoint}/json/list`)).json();
  const page = targets.find((t) => t.type === "page");
  const ws = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {
    ws.addEventListener("open", resolve, { once: true });
    ws.addEventListener("error", reject, { once: true });
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
      return;
    }
    if (msg.method === "Runtime.consoleAPICalled" && msg.params.type === "error") {
      consoleErrors.push(msg.params.args.map((a) => a.value ?? a.description ?? "").join(" "));
    }
    if (msg.method === "Runtime.exceptionThrown") {
      const d = msg.params.exceptionDetails;
      pageErrors.push(`[${scenario}] ${d.text} ${d.exception?.description ?? ""}`.trim());
    }
    if (msg.method === "Network.responseReceived" && msg.params.response.status >= 400) {
      badResponses.push(`[${scenario}] ${msg.params.response.status} ${msg.params.response.url}`);
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
      throw new Error(
        `evaluate failed: ${res.exceptionDetails.text} ${res.exceptionDetails.exception?.description ?? ""}`,
      );
    }
    return res.result.value;
  };
  const waitFor = async (expression, timeoutMs = 8000) => {
    const started = Date.now();
    let last = null;
    while (Date.now() - started < timeoutMs) {
      try {
        last = await evaluate(expression);
        if (last) return last;
      } catch {
        /* keep polling */
      }
      await sleep(200);
    }
    return last;
  };
  const statusState = () => evaluate("document.getElementById('server-status')?.dataset.state ?? 'missing'");
  const statusText = () => evaluate("document.getElementById('server-status')?.textContent.trim() ?? ''");
  const explorerTabClick = () =>
    evaluate(`(() => { const b = document.querySelector('.view-tab[data-view="explorer"]'); b && b.click(); return Boolean(b); })()`);
  const dashboardTabClick = () =>
    evaluate(`(() => { const b = document.querySelector('.view-tab[data-view="dashboard"]'); b && b.click(); return Boolean(b); })()`);
  const layerChecksum = () => evaluate(`(() => {
    const c = document.getElementById('map-canvas');
    if (!c || !c.width) return -1;
    const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
    let sum = 0, opaque = 0;
    for (let i = 0; i < d.length; i += 4 * 331) {
      sum = (sum + d[i] * 3 + d[i + 1] * 5 + d[i + 2] * 7 + d[i + 3]) % 1e9;
      if (d[i + 3] > 0) opaque += 1;
    }
    return opaque > 5 ? sum : -opaque;
  })()`);

  await send("Runtime.enable");
  await send("Page.enable");
  await send("Log.enable");
  await send("Network.enable");

  /* ================================================================== A */
  scenario = "healthy";
  await send("Page.navigate", { url: BASE + "/" });
  await waitFor("document.readyState === 'complete'");
  await sleep(600);

  check(
    "dashboard route loads",
    (await evaluate("document.title")).includes("NISAR // Earth in Motion") &&
      (await evaluate("!document.getElementById('view-dashboard').hidden")),
    await evaluate("document.title"),
  );

  const reachedConnected = await waitFor("document.getElementById('server-status').dataset.state === 'connected'", 8000);
  check("connection indicator reaches 'connected'", reachedConnected, `state=${await statusState()} text="${await statusText()}"`);

  const cards = await waitFor("document.querySelectorAll('#observation-cards .card').length", 8000);
  check("available observations populate", cards >= 2, `count=${cards}`);

  const hasBadges = await evaluate(`(() => {
    const badges = [...document.querySelectorAll('#observation-cards .badge')].map(b => b.textContent.trim());
    return badges.includes("REAL NISAR") && badges.includes("SAMPLE DATA");
  })()`);
  check("observation cards render REAL and SAMPLE badges distinctly", hasBadges);

  const copyButtons = await evaluate(`document.querySelectorAll('#observation-cards .btn-copy').length`);
  check("observation cards have Copy ID buttons", copyButtons >= 2, `count=${copyButtons}`);

  const copyResult = await evaluate(`(() => {
    const btn = document.querySelector('#observation-cards .btn-copy');
    if (!btn) return false;
    btn.click();
    return btn.dataset.copyGranule && btn.dataset.copyGranule.length > 20;
  })()`);
  check("Copy ID button triggers with valid granule ID", copyResult);

  const selectOptions = await evaluate(
    "[...document.querySelectorAll('#observation-select option')].map((o) => o.value)",
  );
  check(
    "both real and sample observations listed",
    Array.isArray(selectOptions) && selectOptions.includes("venezuela") && selectOptions.includes("sample_demo"),
    `options=${JSON.stringify(selectOptions)}`,
  );

  /* --- CTA opens the explorer ---------------------------------------- */
  await evaluate(`(() => { document.getElementById('open-explorer').click(); return true; })()`);
  await sleep(250);
  check("CTA opens the explorer", await evaluate("!document.getElementById('view-explorer').hidden"));
  check(
    "explorer tab becomes active",
    await evaluate(`document.querySelector('.view-tab[data-view="explorer"]').classList.contains('is-active') &&
      document.querySelector('.view-tab[data-view="explorer"]').getAttribute('aria-selected') === 'true'`),
  );

  const hint = await waitFor(
    `(() => {
      const h = document.getElementById('map-hint');
      if (!h) return null;
      if (h.hidden) return 'loaded';
      const text = h.textContent.trim();
      return /loading/i.test(text) ? null : (text || null);
    })()`,
    30000,
  );
  check("explorer loads an observation", hint === "loaded", `hint=${hint}`);

  const layerTabs = await waitFor("document.querySelectorAll('#layer-tabs [data-layer]').length", 30000);
  check("layer tabs rendered", layerTabs >= 2, `count=${layerTabs}`);

  await waitFor("document.getElementById('map-canvas').width > 10 && document.getElementById('map-canvas').height > 10", 30000);
  await sleep(500);
  const painted = await layerChecksum();
  check("phase layer paints the canvas", painted > 0, `checksum=${painted}`);

  const beforeCoherence = painted;
  await evaluate(`(() => {
    const tabs = [...document.querySelectorAll('#layer-tabs [data-layer]')];
    const target = tabs.find((t) => t.dataset.layer === 'coherence');
    if (target) target.click();
    return Boolean(target);
  })()`);
  await sleep(600);
  const afterCoherence = await layerChecksum();
  const legend = await evaluate("document.getElementById('legend').textContent.trim()");
  check(
    "coherence layer renders and legend updates",
    /coherence/i.test(legend) && afterCoherence !== beforeCoherence && afterCoherence > 0,
    `legend="${legend.slice(0, 50)}", checksum changed=${afterCoherence !== beforeCoherence}`,
  );

  const statsBefore = await evaluate("document.getElementById('threshold-stats').textContent.trim()");
  await evaluate(`(() => { const el = document.getElementById('threshold'); el.value = '0.6';
    el.dispatchEvent(new Event('input', { bubbles: true })); return true; })()`);
  await sleep(800);
  check(
    "coherence threshold control updates value and statistics",
    (await evaluate("document.getElementById('threshold-value').textContent.trim()")) === "0.60" &&
      (await evaluate("document.getElementById('threshold-stats').textContent.trim()")) !== statsBefore,
    `value=${await evaluate("document.getElementById('threshold-value').textContent.trim()")}`,
  );

  check(
    "export links rendered",
    (await evaluate("[...document.querySelectorAll('#export-grid a')].map((a) => a.getAttribute('href'))"))
      .some((h) => h && h.endsWith("phase.tif")),
    `${await evaluate("document.querySelectorAll('#export-grid a').length")} links`,
  );
  check(
    "scientific limitations rendered",
    (await evaluate("document.querySelectorAll('#explorer-limitations li').length")) >= 1,
  );
  check(
    "epicentre markers listed for the real observation",
    (await evaluate("document.querySelectorAll('#event-list .event').length")) >= 1,
    `${await evaluate("document.querySelectorAll('#event-list .event').length")} events`,
  );

  if (SCREENSHOT) {
    const shot = await send("Page.captureScreenshot", { format: "png" });
    writeFileSync(SCREENSHOT, Buffer.from(shot.data, "base64"));
    process.stdout.write(`screenshot (explorer) -> ${SCREENSHOT}\n`);
  }

  /* --- keyboard: back to dashboard ------------------------------------ */
  await evaluate(`(() => { document.querySelector('.view-tab[data-view="dashboard"]').focus(); return true; })()`);
  await send("Input.dispatchKeyEvent", {
    type: "keyDown", key: "Enter", code: "Enter", windowsVirtualKeyCode: 13, nativeVirtualKeyCode: 13, text: "\r",
  });
  await send("Input.dispatchKeyEvent", {
    type: "keyUp", key: "Enter", code: "Enter", windowsVirtualKeyCode: 13, nativeVirtualKeyCode: 13,
  });
  await sleep(400);
  check("keyboard activates the Dashboard tab", await evaluate("!document.getElementById('view-dashboard').hidden"));
  check(
    "dashboard tab reflects active view",
    await evaluate(`document.querySelector('.view-tab[data-view="dashboard"]').getAttribute('aria-selected') === 'true'`),
  );

  await explorerTabClick();
  await sleep(250);
  check("Dashboard -> Explorer tab navigation works", await evaluate("!document.getElementById('view-explorer').hidden"));
  await dashboardTabClick();
  await sleep(250);
  check("Explorer -> Dashboard tab navigation works", await evaluate("!document.getElementById('view-dashboard').hidden"));

  if (SCREENSHOT) {
    const shot = await send("Page.captureScreenshot", { format: "png" });
    const dashboardPath = SCREENSHOT.replace(/\.png$/i, "_dashboard.png");
    writeFileSync(dashboardPath, Buffer.from(shot.data, "base64"));
    process.stdout.write(`screenshot (dashboard) -> ${dashboardPath}\n`);
  }

  check("healthy scenario: no uncaught page errors", pageErrors.length === 0, pageErrors.join(" | ").slice(0, 300));
  check("healthy scenario: no console errors", consoleErrors.length === 0, consoleErrors.join(" | ").slice(0, 300));
  check("healthy scenario: no HTTP responses >= 400", badResponses.length === 0, badResponses.join(" | ").slice(0, 300));

  /* ================================================================== B */
  scenario = "api-outage";
  consoleErrors = [];
  badResponses = [];
  await send("Page.addScriptToEvaluateOnNewDocument", { source: FETCH_OVERRIDE });
  await send("Page.navigate", { url: BASE + "/" });
  await waitFor("document.readyState === 'complete'");

  const stuckState = await waitFor(
    `['connected', 'unavailable'].includes(document.getElementById('server-status').dataset.state)`,
    6000,
  );
  check(
    "failed /api/index leaves an explicit state, never stuck on connecting",
    Boolean(stuckState),
    `state=${await statusState()} text="${await statusText()}"`,
  );
  check("indicator reports unavailable", (await statusState()) === "unavailable", await statusText());
  check(
    "dashboard shows an actionable message",
    await evaluate("!document.getElementById('dashboard-empty').hidden && /unavailable/i.test(document.getElementById('dashboard-empty').textContent)"),
    (await evaluate("document.getElementById('dashboard-empty').textContent.trim()")).slice(0, 120),
  );
  check(
    "retry control offered",
    await evaluate("Boolean(document.querySelector('#dashboard-empty [data-retry]'))"),
  );

  await explorerTabClick();
  await sleep(250);
  check("navigation still works while the API is unavailable", await evaluate("!document.getElementById('view-explorer').hidden"));
  await dashboardTabClick();
  await sleep(150);

  /* recover */
  await evaluate("(() => { window.__nisarFailIndex = false; return true; })()");
  await evaluate(`(() => { document.querySelector('#dashboard-empty [data-retry]').click(); return true; })()`);
  const recovered = await waitFor("document.getElementById('server-status').dataset.state === 'connected'", 8000);
  check("retry recovers to 'connected'", Boolean(recovered), `state=${await statusState()}`);
  check(
    "observations return after recovery",
    (await waitFor("document.querySelectorAll('#observation-cards .card').length", 8000)) >= 2,
    `count=${await evaluate("document.querySelectorAll('#observation-cards .card').length")}`,
  );
  check(
    "retry button removed once healthy",
    await evaluate("!document.querySelector('#dashboard-empty [data-retry]')"),
  );
  check("outage scenario: no uncaught page errors", pageErrors.length === 0, pageErrors.join(" | ").slice(0, 300));

  /* ================================================================== C */
  scenario = "invalid-observation";
  consoleErrors = [];
  badResponses = [];
  await explorerTabClick();
  await evaluate("(() => { if (typeof openObservation === 'function') openObservation('does-not-exist'); return true; })()");
  const missingHint = await waitFor(
    `/Could not open/.test(document.getElementById('map-hint').textContent)`,
    8000,
  );
  check("missing observation produces an understandable error", Boolean(missingHint),
    (await evaluate("document.getElementById('map-hint').textContent.trim()")).slice(0, 160));
  check("application stays usable after the error", await evaluate("!document.getElementById('view-explorer').hidden"));

  /* recover the explorer for the user */
  await evaluate(`(() => { const s = document.getElementById('observation-select');
    if (s && s.value) openObservation(s.value); return true; })()`);
  const restored = await waitFor(
    `document.getElementById('map-hint').hidden === true`,
    15000,
  );
  check("explorer recovers with a valid observation", Boolean(restored));

  ws.close();
  child.kill();
  try {
    rmSync(profile, { recursive: true, force: true });
  } catch {
    /* best effort */
  }

  const failures = results.filter((r) => !r.ok);
  process.stdout.write(`\n${results.length - failures.length}/${results.length} checks passed\n`);
  if (failures.length) {
    process.stdout.write(failures.map((f) => ` - [${f.scenario}] ${f.name}: ${f.detail}`).join("\n") + "\n");
  }
  process.exit(failures.length === 0 ? 0 : 1);
}

main().catch((error) => {
  console.error("FAIL:", error);
  process.exit(1);
});
