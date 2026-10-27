import { spawn } from 'node:child_process';
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const BASE_URL = process.argv[2] || 'http://127.0.0.1:8011';
const CHROME_PATH = process.env.CHROME_PATH || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';

const profile = mkdtempSync(join(tmpdir(), 'chrome-rotating-earth-'));
const child = spawn(CHROME_PATH, [
  '--headless=new',
  '--remote-debugging-port=9346',
  '--user-data-dir=' + profile,
  'about:blank'
]);

await new Promise((r) => setTimeout(r, 2000));
const list = await (await fetch('http://127.0.0.1:9346/json/list')).json();
const page = list.find((t) => t.type === 'page');
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((r) => { ws.onopen = r; });

let id = 0;
const send = (method, params = {}) => new Promise((resolve, reject) => {
  const cur = ++id;
  const handler = (e) => {
    const m = JSON.parse(e.data);
    if (m.id === cur) {
      ws.removeEventListener('message', handler);
      if (m.error) reject(new Error(m.error.message));
      else resolve(m.result);
    }
  };
  ws.addEventListener('message', handler);
  ws.send(JSON.stringify({ id: cur, method, params }));
});

const evaluate = async (expr) => {
  const res = await send('Runtime.evaluate', {
    expression: expr,
    awaitPromise: true,
    returnByValue: true,
  });
  return res.result?.value;
};

const assert = (condition, msg) => {
  if (!condition) {
    console.error('FAIL:', msg);
    throw new Error(msg);
  }
  console.log('PASS:', msg);
};

try {
  await send('Page.enable');
  await send('Runtime.enable');
  await send('Emulation.setDeviceMetricsOverride', {
    width: 1440,
    height: 900,
    deviceScaleFactor: 1,
    mobile: false,
  });

  console.log('=== TEST 1: APP BOOT & WEBGL INITIALIZATION ===');
  await send('Page.navigate', { url: BASE_URL + '/' });
  await new Promise((r) => setTimeout(r, 2500)); // wait for texture load and boot

  const sphereState = await evaluate(`(() => {
    const sphere = document.querySelector('.earth-sphere');
    const canvas = document.querySelector('#earth-canvas');
    const fallback = document.querySelector('.earth-fallback');
    return {
      sphereFound: !!sphere,
      hasWebglClass: sphere ? sphere.classList.contains('has-webgl') : false,
      canvasFound: !!canvas,
      canvasDisplay: canvas ? window.getComputedStyle(canvas).display : 'none',
      fallbackDisplay: fallback ? window.getComputedStyle(fallback).display : 'none',
      canvasWidth: canvas ? canvas.width : 0,
      canvasHeight: canvas ? canvas.height : 0
    };
  })()`);

  console.log('Sphere & Canvas State:', sphereState);
  assert(sphereState.sphereFound, 'Earth sphere element found');
  assert(sphereState.hasWebglClass, '.earth-sphere has .has-webgl class');
  assert(sphereState.canvasDisplay === 'block', '#earth-canvas computed display is block');
  assert(sphereState.fallbackDisplay === 'none', '.earth-fallback computed display is none (ZERO duplicate globe)');

  console.log('\n=== TEST 2: PIXEL SAMPLING ACROSS ACTIVE ROTATION ===');
  // Sample canvas pixel data over time to verify rotation is actively rendering
  const getCanvasPixelSample = async () => {
    return evaluate(`(() => {
      const canvas = document.querySelector('#earth-canvas');
      const gl = canvas.getContext('webgl');
      if (!gl) return null;
      const pixels = new Uint8Array(4 * 5);
      // Sample 5 points across horizontal center line (p_x = -0.6, -0.3, 0.0, 0.3, 0.6)
      const cy = Math.floor(canvas.height / 2);
      const xs = [-0.6, -0.3, 0.0, 0.3, 0.6].map(fx => Math.floor(canvas.width * (0.5 + fx * 0.5)));
      const sample = xs.map(x => {
        const p = new Uint8Array(4);
        gl.readPixels(x, cy, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, p);
        return Array.from(p);
      });
      return sample;
    })()`);
  };

  const sampleT0 = await getCanvasPixelSample();
  console.log('Pixel samples at t=0s:', JSON.stringify(sampleT0));
  await new Promise((r) => setTimeout(r, 2000));
  const sampleT2 = await getCanvasPixelSample();
  console.log('Pixel samples at t=2s:', JSON.stringify(sampleT2));

  const samplesDiffer = JSON.stringify(sampleT0) !== JSON.stringify(sampleT2);
  assert(samplesDiffer, 'Canvas pixels change over time (active continuous GPU rendering)');

  console.log('\n=== TEST 3: CHECKPOINTS ACROSS ROTATION CYCLE & LOOP ===');
  // Test accelerated rotation positions to verify:
  // 0% (start), 25% (quarter), 50% (half), 75% (three-quarter), 100% (loop boundary), 150% (>1 cycle)
  const checkpoints = [
    { name: '0pct_start', fraction: 0.0 },
    { name: '25pct', fraction: 0.25 },
    { name: '50pct', fraction: 0.50 },
    { name: '75pct', fraction: 0.75 },
    { name: '100pct_loop_boundary', fraction: 1.00 },
    { name: '150pct_cycle2', fraction: 1.50 }
  ];

  for (const cp of checkpoints) {
    const angle = 1.187 + cp.fraction * 2 * Math.PI;
    await evaluate(`(() => {
      const canvas = document.querySelector('#earth-canvas');
      const gl = canvas.getContext('webgl');
      // Set rotation angle directly via uniform for deterministic checkpoint testing
      const prog = gl.getParameter(gl.CURRENT_PROGRAM);
      // Get u_rotation uniform location or trigger render
      // app.js has its internal state, let's inject checkpoint angle into u_rotation
      // and draw
      const uRot = gl.getUniformLocation(prog, 'u_rotation');
      if (uRot) {
        gl.uniform1f(uRot, ${angle});
        gl.drawArrays(gl.TRIANGLES, 0, 6);
      }
    })()`);

    const shot = await send('Page.captureScreenshot', { format: 'png' });
    const filename = `data/processed/_validation/venezuela/rot_${cp.name}.png`;
    writeFileSync(filename, Buffer.from(shot.data, 'base64'));
    console.log(`Saved screenshot -> ${filename}`);

    // Verify center pixel is not black/empty/transparent
    const centerPix = await evaluate(`(() => {
      const canvas = document.querySelector('#earth-canvas');
      const gl = canvas.getContext('webgl');
      const p = new Uint8Array(4);
      gl.readPixels(canvas.width / 2, canvas.height / 2, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, p);
      return Array.from(p);
    })()`);
    assert(centerPix[3] > 200, `Checkpoint ${cp.name} has solid opacity at center (alpha=${centerPix[3]})`);
    assert(centerPix[0] + centerPix[1] + centerPix[2] > 20, `Checkpoint ${cp.name} is lit and has color at center`);
  }

  console.log('\n=== TEST 4: SEAMLESS LOOP EQUIVALENCE ===');
  // Verify that 0% and 100% have identical center and limb pixels (zero seam, exact loop)
  const diffBetween0And100 = await evaluate(`(() => {
    const canvas = document.querySelector('#earth-canvas');
    const gl = canvas.getContext('webgl');
    const prog = gl.getParameter(gl.CURRENT_PROGRAM);
    const uRot = gl.getUniformLocation(prog, 'u_rotation');

    // Draw at 0%
    gl.uniform1f(uRot, 1.187);
    gl.drawArrays(gl.TRIANGLES, 0, 6);
    const pix0 = new Uint8Array(canvas.width * 4);
    gl.readPixels(0, canvas.height / 2, canvas.width, 1, gl.RGBA, gl.UNSIGNED_BYTE, pix0);

    // Draw at 100% (exactly 2*PI later)
    gl.uniform1f(uRot, 1.187 + 2 * Math.PI);
    gl.drawArrays(gl.TRIANGLES, 0, 6);
    const pix100 = new Uint8Array(canvas.width * 4);
    gl.readPixels(0, canvas.height / 2, canvas.width, 1, gl.RGBA, gl.UNSIGNED_BYTE, pix100);

    let maxDiff = 0;
    for (let i = 0; i < pix0.length; i++) {
      const d = Math.abs(pix0[i] - pix100[i]);
      if (d > maxDiff) maxDiff = d;
    }
    return maxDiff;
  })()`);
  console.log('Max pixel difference between 0% and 100% (loop boundary):', diffBetween0And100);
  assert(diffBetween0And100 <= 1, 'Loop boundary has zero pixel difference (exact mathematical seamless wrap)');

  console.log('\n=== TEST 5: NAVIGATION PERSISTENCE (DASHBOARD <-> EXPLORER) ===');
  // Click open-explorer button
  await evaluate(`document.querySelector('#open-explorer').click()`);
  await new Promise((r) => setTimeout(r, 600));

  const explorerState = await evaluate(`(() => {
    return {
      dashHidden: document.querySelector('#view-dashboard').hidden,
      expHidden: document.querySelector('#view-explorer').hidden
    };
  })()`);
  assert(explorerState.dashHidden === true, 'Dashboard is hidden in explorer view');
  assert(explorerState.expHidden === false, 'Explorer is visible');

  // Navigate back to Dashboard
  await evaluate(`document.querySelector('.view-tab[data-view="dashboard"]').click()`);
  await new Promise((r) => setTimeout(r, 600));

  const dashReturnedState = await evaluate(`(() => {
    return {
      dashHidden: document.querySelector('#view-dashboard').hidden,
      hasWebglClass: document.querySelector('.earth-sphere').classList.contains('has-webgl'),
      canvasDisplay: window.getComputedStyle(document.querySelector('#earth-canvas')).display
    };
  })()`);
  assert(dashReturnedState.dashHidden === false, 'Dashboard view restored');
  assert(dashReturnedState.hasWebglClass === true, 'WebGL class intact after view switch');
  assert(dashReturnedState.canvasDisplay === 'block', 'Canvas display remains block');

  console.log('\n=== TEST 6: PREFERS-REDUCED-MOTION SUPPORT ===');
  // Emulate reduced motion
  await send('Emulation.setEmulatedMedia', {
    media: 'screen',
    features: [{ name: 'prefers-reduced-motion', value: 'reduce' }]
  });
  await new Promise((r) => setTimeout(r, 500));

  const reducedMotionState = await evaluate(`(() => {
    const canvas = document.querySelector('#earth-canvas');
    const fallback = document.querySelector('.earth-fallback');
    return {
      canvasDisplay: window.getComputedStyle(canvas).display,
      fallbackDisplay: window.getComputedStyle(fallback).display
    };
  })()`);
  console.log('Reduced motion display state:', reducedMotionState);
  assert(reducedMotionState.canvasDisplay === 'none', 'Canvas is hidden under prefers-reduced-motion');
  assert(reducedMotionState.fallbackDisplay === 'block', 'Static fallback picture is displayed under prefers-reduced-motion');

  const shotReduced = await send('Page.captureScreenshot', { format: 'png' });
  writeFileSync('data/processed/_validation/venezuela/rot_reduced_motion.png', Buffer.from(shotReduced.data, 'base64'));
  console.log('Saved screenshot -> data/processed/_validation/venezuela/rot_reduced_motion.png');

  // Reset emulation to normal motion
  await send('Emulation.setEmulatedMedia', { media: 'screen', features: [] });
  await new Promise((r) => setTimeout(r, 500));

  console.log('\n=== TEST 7: RESPONSIVE VIEWPORT INTEGRITY ===');
  const viewports = [
    { name: 'desktop_1440', width: 1440, height: 900 },
    { name: 'laptop_1280', width: 1280, height: 720 },
    { name: 'tablet_768', width: 768, height: 1024 },
    { name: 'mobile_390', width: 390, height: 844 },
  ];

  for (const vp of viewports) {
    await send('Emulation.setDeviceMetricsOverride', {
      width: vp.width,
      height: vp.height,
      deviceScaleFactor: 1,
      mobile: vp.width < 600,
    });
    await new Promise((r) => setTimeout(r, 400));

    const metrics = await evaluate(`(() => {
      const docW = document.documentElement.clientWidth;
      const scrollW = document.documentElement.scrollWidth;
      const sphere = document.querySelector('.earth-sphere');
      const sphereRect = sphere ? sphere.getBoundingClientRect() : null;
      return {
        docW,
        scrollW,
        hasHorizontalOverflow: scrollW > docW,
        sphereWidth: sphereRect ? Math.round(sphereRect.width) : 0,
        sphereHeight: sphereRect ? Math.round(sphereRect.height) : 0
      };
    })()`);

    console.log(`Viewport ${vp.name} (${vp.width}x${vp.height}):`, metrics);
    assert(!metrics.hasHorizontalOverflow, `Viewport ${vp.name} has no horizontal overflow`);
    assert(metrics.sphereWidth > 0, `Viewport ${vp.name} renders Earth sphere`);
  }

  console.log('\n========================================');
  console.log('ALL ROTATING EARTH VERIFICATION CHECKS PASSED!');
  console.log('========================================');

} finally {
  child.kill();
  try { rmSync(profile, { recursive: true, force: true }); } catch {}
}
