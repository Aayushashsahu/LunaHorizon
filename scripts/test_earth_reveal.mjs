import { spawn } from 'node:child_process';
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const BASE_URL = process.argv[2] || 'http://127.0.0.1:8011';
const CHROME_PATH = process.env.CHROME_PATH || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';

const profile = mkdtempSync(join(tmpdir(), 'chrome-earth-reveal-'));
const child = spawn(CHROME_PATH, [
  '--headless=new',
  '--remote-debugging-port=9355',
  '--user-data-dir=' + profile,
  'about:blank'
]);

await new Promise((r) => setTimeout(r, 2000));
const list = await (await fetch('http://127.0.0.1:9355/json/list')).json();
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

  console.log('=== 1. VERIFY INITIAL REVEAL STATE (t=200ms) ===');
  await send('Page.navigate', { url: BASE_URL + '/' });
  await new Promise((r) => setTimeout(r, 200));

  const initialState = await evaluate(`(() => {
    const container = document.querySelector('.earth-container');
    const hero = document.querySelector('.hero');
    const revealGroup = document.getElementById('earth-reveal-group');
    const strokeLeft = document.getElementById('reveal-stroke-left');
    const strokeRight = document.getElementById('reveal-stroke-right');
    const canvas = document.getElementById('earth-canvas');

    const style = container ? window.getComputedStyle(container) : null;
    const transform = style ? style.transform : '';

    return {
      containerFound: !!container,
      hasRevealingClass: container ? container.classList.contains('is-revealing') : false,
      heroRevealing: hero ? hero.classList.contains('is-revealing') : false,
      transform,
      revealGroupFound: !!revealGroup,
      strokeLeftD: strokeLeft ? strokeLeft.getAttribute('d') : null,
      strokeRightD: strokeRight ? strokeRight.getAttribute('d') : null,
      canvasFound: !!canvas,
    };
  })()`);

  console.log('Initial State at t=200ms:', initialState);
  assert(initialState.containerFound, 'Earth container found in DOM');
  assert(initialState.hasRevealingClass, '.earth-container has .is-revealing class active at boot');
  assert(initialState.heroRevealing, '.hero has .is-revealing class active at boot');
  assert(initialState.revealGroupFound, 'Earth reveal SVG group found');
  assert(initialState.strokeLeftD && initialState.strokeLeftD.includes('A 272.5 272.5'), 'Left stroke has valid circular arc at R=272.5');
  assert(initialState.strokeRightD && initialState.strokeRightD.includes('A 272.5 272.5'), 'Right stroke has valid circular arc at R=272.5');

  // Verify mathematical curvature of both strokes: distance from (300, 300) must equal 272.5
  const curvatureCheck = await evaluate(`(() => {
    const strokeLeft = document.getElementById('reveal-stroke-left');
    const strokeRight = document.getElementById('reveal-stroke-right');
    const Cx = 300, Cy = 300;
    const targetR = 272.5;

    let maxErrorL = 0;
    let maxErrorR = 0;

    const samplePath = (path) => {
      const len = path.getTotalLength();
      let maxErr = 0;
      for (let i = 0; i <= 20; i++) {
        const pt = path.getPointAtLength((i / 20) * len);
        const dist = Math.hypot(pt.x - Cx, pt.y - Cy);
        const err = Math.abs(dist - targetR);
        if (err > maxErr) maxErr = err;
      }
      return maxErr;
    };

    return {
      maxErrorLeft: samplePath(strokeLeft),
      maxErrorRight: samplePath(strokeRight)
    };
  })()`);

  console.log('Curvature Radial Precision Check:', curvatureCheck);
  assert(curvatureCheck.maxErrorLeft < 0.5, `Left stroke radius stays within 0.5px of 272.5px silhouette contour (error=${curvatureCheck.maxErrorLeft.toFixed(3)}px)`);
  assert(curvatureCheck.maxErrorRight < 0.5, `Right stroke radius stays within 0.5px of 272.5px silhouette contour (error=${curvatureCheck.maxErrorRight.toFixed(3)}px)`);

  const shotInitial = await send('Page.captureScreenshot', { format: 'png' });
  writeFileSync('data/processed/_validation/venezuela/reveal_01_approach_initial.png', Buffer.from(shotInitial.data, 'base64'));
  console.log('Saved screenshot -> data/processed/_validation/venezuela/reveal_01_approach_initial.png');



  console.log('\n=== 2. VERIFY MID-FLIGHT SCALE-UP & DIAGONAL STROKE SWEEP (t=1100ms) ===');
  await new Promise((r) => setTimeout(r, 900));

  const midState = await evaluate(`(() => {
    const container = document.querySelector('.earth-container');
    const strokeL = document.getElementById('reveal-stroke-left');
    const strokeR = document.getElementById('reveal-stroke-right');
    const pipL = document.getElementById('reveal-pip-left');
    const pipR = document.getElementById('reveal-pip-right');

    const style = container ? window.getComputedStyle(container) : null;
    const styleL = strokeL ? window.getComputedStyle(strokeL) : null;
    const styleR = strokeR ? window.getComputedStyle(strokeR) : null;

    return {
      transform: style ? style.transform : '',
      strokeLeftOpacity: styleL ? parseFloat(styleL.opacity) : 0,
      strokeRightOpacity: styleR ? parseFloat(styleR.opacity) : 0,
      pipLTransform: pipL ? pipL.getAttribute('transform') : null,
      pipRTransform: pipR ? pipR.getAttribute('transform') : null,
      revealState: window.earthController?.getRevealState?.()
    };
  })()`);

  console.log('Mid-Flight State at t=1100ms:', midState);
  assert(midState.strokeLeftOpacity > 0.3, 'Left diagonal stroke is actively illuminated during reveal');
  assert(midState.strokeRightOpacity > 0.3, 'Right diagonal stroke is actively illuminated during reveal');
  assert(midState.pipLTransform && midState.pipLTransform !== 'translate(40.8, 215.8)', 'Left telemetry pip has actively advanced along the curved contour');
  assert(midState.pipRTransform && midState.pipRTransform !== 'translate(559.2, 215.8)', 'Right telemetry pip has actively advanced along the curved contour');

  const shotMid = await send('Page.captureScreenshot', { format: 'png' });
  writeFileSync('data/processed/_validation/venezuela/reveal_02_diagonal_strokes.png', Buffer.from(shotMid.data, 'base64'));
  console.log('Saved screenshot -> data/processed/_validation/venezuela/reveal_02_diagonal_strokes.png');

  console.log('\n=== 3. VERIFY FINAL DOCKED HERO STATE & HUD HANDOFF (t=2900ms) ===');
  await new Promise((r) => setTimeout(r, 1800));

  const dockedState = await evaluate(`(() => {
    const container = document.querySelector('.earth-container');
    const hero = document.querySelector('.hero');
    const revealGroup = document.getElementById('earth-reveal-group');
    const frontTrack = document.getElementById('orbit-track-front');
    const sat = document.getElementById('hud-spacecraft');

    const style = container ? window.getComputedStyle(container) : null;
    const satStyle = sat ? window.getComputedStyle(sat) : null;
    const frontStyle = frontTrack ? window.getComputedStyle(frontTrack) : null;
    const groupStyle = revealGroup ? window.getComputedStyle(revealGroup) : null;

    return {
      hasRevealing: container ? container.classList.contains('is-revealing') : false,
      hasCompleted: container ? container.classList.contains('reveal-completed') : false,
      heroCompleted: hero ? hero.classList.contains('reveal-completed') : false,
      revealGroupDisplay: groupStyle ? groupStyle.display : '',
      orbitOpacity: frontStyle ? parseFloat(frontStyle.opacity) : 0,
      satOpacity: satStyle ? parseFloat(satStyle.opacity) : 0,
      satTransform: sat ? sat.getAttribute('transform') : null,
      revealState: window.earthController?.getRevealState?.()
    };
  })()`);

  console.log('Docked Hero State at t=2900ms:', dockedState);
  assert(!dockedState.hasRevealing, '.is-revealing class cleanly removed after reveal duration');
  assert(dockedState.hasCompleted, '.reveal-completed class added to .earth-container');
  assert(dockedState.revealGroupDisplay === 'none', 'Reveal strokes group cleanly dissolved / hidden after reveal');
  assert(dockedState.orbitOpacity >= 0.9, 'HUD orbit tracks have reached full visibility');
  assert(dockedState.satTransform !== null, 'Satellite spacecraft is active and positioned');

  const shotDocked = await send('Page.captureScreenshot', { format: 'png' });
  writeFileSync('data/processed/_validation/venezuela/reveal_03_hero_docked.png', Buffer.from(shotDocked.data, 'base64'));
  console.log('Saved screenshot -> data/processed/_validation/venezuela/reveal_03_hero_docked.png');

  console.log('\n=== 4. VERIFY REPLAY & PROGRAMMATIC TRIGGER ===');
  await evaluate(`window.earthController?.triggerReveal?.()`);
  await new Promise((r) => setTimeout(r, 300));

  const replaying = await evaluate(`(() => {
    const container = document.querySelector('.earth-container');
    const revealGroup = document.getElementById('earth-reveal-group');
    return {
      isRevealing: container ? container.classList.contains('is-revealing') : false,
      groupDisplay: revealGroup ? window.getComputedStyle(revealGroup).display : ''
    };
  })()`);
  console.log('Replay Trigger State:', replaying);
  assert(replaying.isRevealing, 'triggerReveal() successfully restarted reveal cycle');
  assert(replaying.groupDisplay !== 'none', 'Reveal strokes group re-illuminated on replay');

  // Let replay finish
  await new Promise((r) => setTimeout(r, 2600));

  console.log('\n=== 5. VERIFY PREFERS-REDUCED-MOTION COMPLIANCE ===');
  await send('Emulation.setEmulatedMedia', {
    features: [{ name: 'prefers-reduced-motion', value: 'reduce' }]
  });
  await send('Page.navigate', { url: BASE_URL + '/' });
  await new Promise((r) => setTimeout(r, 400));

  const reducedMotionState = await evaluate(`(() => {
    const container = document.querySelector('.earth-container');
    const revealGroup = document.getElementById('earth-reveal-group');
    const fallback = document.querySelector('.earth-fallback');
    const canvas = document.getElementById('earth-canvas');

    const style = container ? window.getComputedStyle(container) : null;
    const groupStyle = revealGroup ? window.getComputedStyle(revealGroup) : null;
    const fbStyle = fallback ? window.getComputedStyle(fallback) : null;
    const cvStyle = canvas ? window.getComputedStyle(canvas) : null;

    return {
      animation: style ? style.animationName : '',
      groupDisplay: groupStyle ? groupStyle.display : '',
      fallbackDisplay: fbStyle ? fbStyle.display : '',
      canvasDisplay: cvStyle ? cvStyle.display : ''
    };
  })()`);

  console.log('Reduced Motion State:', reducedMotionState);
  assert(reducedMotionState.animation === 'none' || reducedMotionState.animation === '', 'Scale-up animation is disabled under prefers-reduced-motion');
  assert(reducedMotionState.groupDisplay === 'none', 'Reveal stroke group is hidden immediately under prefers-reduced-motion');
  assert(reducedMotionState.fallbackDisplay === 'block', 'Calm static Earth fallback is visible under reduced motion');

  const shotReduced = await send('Page.captureScreenshot', { format: 'png' });
  writeFileSync('data/processed/_validation/venezuela/reveal_04_reduced_motion.png', Buffer.from(shotReduced.data, 'base64'));
  console.log('Saved screenshot -> data/processed/_validation/venezuela/reveal_04_reduced_motion.png');

  // Reset reduced-motion emulation
  await send('Emulation.setEmulatedMedia', { features: [] });

  console.log('\n=== 6. VERIFY RESPONSIVE VIEWPORTS ===');
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
      mobile: vp.width < 768,
    });
    await send('Page.navigate', { url: BASE_URL + '/' });
    await new Promise((r) => setTimeout(r, 600));

    const vpMetrics = await evaluate(`(() => {
      const docW = document.documentElement.clientWidth;
      const scrollW = document.documentElement.scrollWidth;
      const sphere = document.querySelector('.earth-sphere');
      const cta = document.getElementById('open-explorer');
      const rect = sphere ? sphere.getBoundingClientRect() : null;
      return {
        docW,
        scrollW,
        overflow: scrollW > docW + 1,
        sphereVisible: !!rect && rect.width > 50 && rect.height > 50,
        ctaVisible: !!cta && cta.offsetWidth > 0,
      };
    })()`);

    console.log(`Viewport ${vp.name}:`, vpMetrics);
    assert(!vpMetrics.overflow, `Viewport ${vp.name} has no horizontal overflow`);
    assert(vpMetrics.sphereVisible, `Viewport ${vp.name} displays Earth properly`);
    assert(vpMetrics.ctaVisible, `Viewport ${vp.name} CTA is accessible`);

    const shotVp = await send('Page.captureScreenshot', { format: 'png' });
    writeFileSync(`data/processed/_validation/venezuela/reveal_${vp.name}.png`, Buffer.from(shotVp.data, 'base64'));
    console.log(`Saved screenshot -> data/processed/_validation/venezuela/reveal_${vp.name}.png`);
  }

  console.log('\n========================================');
  console.log('ALL CINEMATIC EARTH REVEAL CHECKS PASSED!');
  console.log('========================================');

} catch (err) {
  console.error('Test execution failed:', err);
  process.exitCode = 1;
} finally {
  try { child.kill(); } catch (e) {}
  try { rmSync(profile, { recursive: true, force: true }); } catch (e) {}
  process.exit(process.exitCode || 0);
}
