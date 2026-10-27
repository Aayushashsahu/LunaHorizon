import { spawn } from 'node:child_process';
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const BASE_URL = process.argv[2] || 'http://127.0.0.1:8011';
const CHROME_PATH = process.env.CHROME_PATH || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';

const profile = mkdtempSync(join(tmpdir(), 'chrome-mission-exp-'));
const child = spawn(CHROME_PATH, [
  '--headless=new',
  '--remote-debugging-port=9348',
  '--user-data-dir=' + profile,
  'about:blank'
]);

await new Promise((r) => setTimeout(r, 2000));
const list = await (await fetch('http://127.0.0.1:9348/json/list')).json();
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

  console.log('=== 1. VERIFY BOOT & 3D ORBIT/SATELLITE SVG INITIALIZATION ===');
  await send('Page.navigate', { url: BASE_URL + '/' });
  await new Promise((r) => setTimeout(r, 2500)); // wait for boot and texture load

  const orbitInit = await evaluate(`(() => {
    const frontTrack = document.getElementById('orbit-track-front');
    const backTrack = document.getElementById('orbit-track-back');
    const spacecraft = document.getElementById('hud-spacecraft');
    const statusText = document.getElementById('hud-status-text');
    const replayBtn = document.getElementById('replay-acquisition');

    return {
      frontTrackFound: !!frontTrack,
      frontTrackDLength: frontTrack ? frontTrack.getAttribute('d')?.length : 0,
      backTrackFound: !!backTrack,
      backTrackDLength: backTrack ? backTrack.getAttribute('d')?.length : 0,
      spacecraftFound: !!spacecraft,
      spacecraftTransform: spacecraft ? spacecraft.getAttribute('transform') : null,
      statusText: statusText ? statusText.textContent : '',
      replayBtnFound: !!replayBtn
    };
  })()`);

  console.log('Orbit Init State:', orbitInit);
  assert(orbitInit.frontTrackFound && orbitInit.frontTrackDLength > 50, '3D front orbit track initialized with valid SVG path data');
  assert(orbitInit.backTrackFound && orbitInit.backTrackDLength > 50, '3D back orbit track initialized with valid SVG path data');
  assert(orbitInit.spacecraftFound, 'Spacecraft satellite group found');
  assert(orbitInit.replayBtnFound, 'Replay acquisition control button found');

  console.log('\n=== 2. VERIFY SATELLITE CONTINUOUS MOVEMENT & ROTATION ===');
  const getSatTransform = () => evaluate(`(() => {
    const el = document.getElementById('hud-spacecraft');
    return el ? { transform: el.getAttribute('transform'), opacity: window.getComputedStyle(el).opacity } : null;
  })()`);

  const t0 = await getSatTransform();
  console.log('Satellite state at t=0s:', t0);
  await new Promise((r) => setTimeout(r, 1500));
  const t1 = await getSatTransform();
  console.log('Satellite state at t=1.5s:', t1);
  await new Promise((r) => setTimeout(r, 1500));
  const t2 = await getSatTransform();
  console.log('Satellite state at t=3.0s:', t2);

  assert(t0.transform !== t1.transform && t1.transform !== t2.transform, 'Satellite transform changes smoothly over time');

  // Capture frame of orbit & spacecraft
  const shotOrbit = await send('Page.captureScreenshot', { format: 'png' });
  writeFileSync('data/processed/_validation/venezuela/mission2_orbit_cruise.png', Buffer.from(shotOrbit.data, 'base64'));
  console.log('Saved screenshot -> data/processed/_validation/venezuela/mission2_orbit_cruise.png');

  console.log('\n=== 3. VERIFY RADAR ACQUISITION SWEEP & REPLAY CONTROL ===');
  // Trigger acquisition sweep via replay control
  await evaluate(`document.getElementById('replay-acquisition').click()`);
  await new Promise((r) => setTimeout(r, 800)); // Inside sweep window (orbitTime ~ 1.3s)

  const sweepState = await evaluate(`(() => {
    const beam = document.getElementById('radar-beam');
    const swathBase = document.getElementById('radar-swath-base');
    const swathFringes = document.getElementById('radar-swath-fringes');
    const statusText = document.getElementById('hud-status-text');
    const statusDot = document.getElementById('hud-status-dot');

    return {
      beamOpacity: beam ? parseFloat(window.getComputedStyle(beam).opacity) : 0,
      swathBaseOpacity: swathBase ? parseFloat(window.getComputedStyle(swathBase).opacity) : 0,
      swathFringesOpacity: swathFringes ? parseFloat(window.getComputedStyle(swathFringes).opacity) : 0,
      statusText: statusText ? statusText.textContent : '',
      isAcquiring: statusDot ? statusDot.classList.contains('is-acquiring') : false
    };
  })()`);

  console.log('Sweep state during acquisition pass:', sweepState);
  assert(sweepState.beamOpacity > 0.1, 'Radar beam is actively illuminated during acquisition');
  assert(sweepState.swathBaseOpacity > 0.1, 'Surface ground swath is actively illuminated');
  assert(sweepState.isAcquiring, 'HUD status dot indicates active acquisition');
  assert(sweepState.statusText.includes('ACQUISITION'), 'HUD text indicates radar acquisition');

  // Capture screenshot of radar acquisition sweep
  const shotSweep = await send('Page.captureScreenshot', { format: 'png' });
  writeFileSync('data/processed/_validation/venezuela/mission2_radar_sweep.png', Buffer.from(shotSweep.data, 'base64'));
  console.log('Saved screenshot -> data/processed/_validation/venezuela/mission2_radar_sweep.png');

  console.log('\n=== 4. VERIFY CINEMATIC TRANSITION TO REAL NISAR OBSERVATION ===');
  // Click primary CTA: EXPLORE OBSERVATIONS
  await evaluate(`document.getElementById('open-explorer').click()`);

  // Inspect transition state immediately during the 500ms wipe
  await new Promise((r) => setTimeout(r, 200));
  const transitioningState = await evaluate(`(() => {
    const btn = document.getElementById('open-explorer');
    const overlay = document.getElementById('mission-transition-overlay');
    const targetRing = document.getElementById('target-pulse-ring');
    return {
      btnDisabled: btn ? btn.disabled : false,
      btnText: btn ? btn.textContent : '',
      isTransitioning: btn ? btn.classList.contains('is-transitioning') : false,
      overlayActive: overlay ? overlay.classList.contains('is-active') : false,
      targetLocked: targetRing ? targetRing.classList.contains('is-locked') : false
    };
  })()`);

  console.log('Transition state at t=200ms:', transitioningState);
  assert(transitioningState.btnDisabled, 'CTA button disabled during transition to prevent duplicate clicks');
  assert(transitioningState.overlayActive, 'Holographic radar transition overlay is active');
  assert(transitioningState.targetLocked, 'Target swath reticle enters locked focus pulse');

  const shotTransition = await send('Page.captureScreenshot', { format: 'png' });
  writeFileSync('data/processed/_validation/venezuela/mission2_transition_wipe.png', Buffer.from(shotTransition.data, 'base64'));
  console.log('Saved screenshot -> data/processed/_validation/venezuela/mission2_transition_wipe.png');

  // Wait for transition to complete and explorer to render real observation
  await new Promise((r) => setTimeout(r, 1200));

  const explorerState = await evaluate(`(() => {
    const dash = document.getElementById('view-dashboard');
    const exp = document.getElementById('view-explorer');
    const overlay = document.getElementById('mission-transition-overlay');
    const obsSelect = document.getElementById('observation-select');
    const metaGranule = document.querySelector('.meta-granule-val');
    const mapCanvas = document.getElementById('map-canvas');

    return {
      dashHidden: dash ? dash.hidden : false,
      expHidden: exp ? exp.hidden : true,
      overlayActive: overlay ? overlay.classList.contains('is-active') : true,
      selectedObservation: obsSelect ? obsSelect.value : '',
      granuleText: metaGranule ? metaGranule.textContent : '',
      canvasWidth: mapCanvas ? mapCanvas.width : 0,
      canvasHeight: mapCanvas ? mapCanvas.height : 0
    };
  })()`);

  console.log('Explorer state post-transition:', explorerState);
  assert(explorerState.dashHidden === true, 'Dashboard view is cleanly hidden');
  assert(explorerState.expHidden === false, 'Observation Explorer view is active and visible');
  assert(explorerState.overlayActive === false, 'Transition overlay has cleanly cleared and unfrozen interaction');
  assert(explorerState.selectedObservation === 'venezuela', 'Explorer loaded real NISAR observation "venezuela"');
  assert(explorerState.granuleText.includes('NISAR_L2_PR_GUNW'), 'Real Level-2 GUNW granule metadata is displayed');
  assert(explorerState.canvasWidth > 0 && explorerState.canvasHeight > 0, 'Map canvas has rendered valid raster dimensions');

  const shotExplorer = await send('Page.captureScreenshot', { format: 'png' });
  writeFileSync('data/processed/_validation/venezuela/mission2_real_explorer.png', Buffer.from(shotExplorer.data, 'base64'));
  console.log('Saved screenshot -> data/processed/_validation/venezuela/mission2_real_explorer.png');

  console.log('\n=== 5. VERIFY NAVIGATION BACK TO DASHBOARD & PERSISTENCE ===');
  // Return to Dashboard via tab
  await evaluate(`document.querySelector('.view-tab[data-view="dashboard"]').click()`);
  await new Promise((r) => setTimeout(r, 600));

  const returnDashState = await evaluate(`(() => {
    const dash = document.getElementById('view-dashboard');
    const sphere = document.querySelector('.earth-sphere');
    const sat = document.getElementById('hud-spacecraft');
    return {
      dashHidden: dash ? dash.hidden : true,
      hasWebgl: sphere ? sphere.classList.contains('has-webgl') : false,
      satFound: !!sat
    };
  })()`);
  assert(returnDashState.dashHidden === false, 'Dashboard view restored');
  assert(returnDashState.hasWebgl === true, 'WebGL rotating Earth restored without context leak');
  assert(returnDashState.satFound === true, 'Satellite orbit restored');

  console.log('\n=== 6. VERIFY PREFERS-REDUCED-MOTION SUPPORT ===');
  await send('Emulation.setEmulatedMedia', {
    media: 'screen',
    features: [{ name: 'prefers-reduced-motion', value: 'reduce' }]
  });
  await new Promise((r) => setTimeout(r, 500));

  // In reduced motion, clicking open-explorer should immediately open explorer without delay
  await evaluate(`document.getElementById('open-explorer').click()`);
  const reducedMotionNav = await evaluate(`(() => {
    return {
      expHidden: document.getElementById('view-explorer').hidden,
      overlayActive: document.getElementById('mission-transition-overlay').classList.contains('is-active')
    };
  })()`);
  console.log('Reduced motion instant navigation state:', reducedMotionNav);
  assert(reducedMotionNav.expHidden === false, 'Explorer opened immediately under prefers-reduced-motion');
  assert(reducedMotionNav.overlayActive === false, 'Transition overlay was skipped under prefers-reduced-motion');

  // Reset emulation and return to dashboard
  await send('Emulation.setEmulatedMedia', { media: 'screen', features: [] });
  await evaluate(`document.querySelector('.view-tab[data-view="dashboard"]').click()`);
  await new Promise((r) => setTimeout(r, 500));

  console.log('\n=== 7. VERIFY RESPONSIVE LAYOUT ACROSS VIEWPORTS ===');
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
      const sat = document.getElementById('hud-spacecraft');
      const cta = document.getElementById('open-explorer');
      return {
        docW,
        scrollW,
        hasHorizontalOverflow: scrollW > docW,
        sphereVisible: !!sphere && sphere.offsetWidth > 0,
        satVisible: !!sat,
        ctaClickable: !!cta && !cta.disabled
      };
    })()`);

    console.log(`Viewport ${vp.name} (${vp.width}x${vp.height}):`, metrics);
    assert(!metrics.hasHorizontalOverflow, `Viewport ${vp.name} has no horizontal overflow`);
    assert(metrics.sphereVisible, `Viewport ${vp.name} displays Earth`);
    assert(metrics.satVisible, `Viewport ${vp.name} displays satellite`);
    assert(metrics.ctaClickable, `Viewport ${vp.name} CTA is accessible`);

    const vpShot = await send('Page.captureScreenshot', { format: 'png' });
    writeFileSync(`data/processed/_validation/venezuela/mission2_${vp.name}.png`, Buffer.from(vpShot.data, 'base64'));
  }

  console.log('\n========================================');
  console.log('ALL MISSION EXPERIENCE 2.0 CHECKS PASSED!');
  console.log('========================================');

} finally {
  child.kill();
  try { rmSync(profile, { recursive: true, force: true }); } catch {}
}
