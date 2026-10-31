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
  assert(initialState.strokeLeftD === 'M 40.8,215.8 A 272.5 272.5 0 0 1 300,27.5',
    'Left stroke SVG path matches exact specification (M 40.8,215.8 A 272.5 272.5 0 0 1 300,27.5)');
  assert(initialState.strokeRightD === 'M 559.2,215.8 A 272.5 272.5 0 0 0 300,27.5',
    'Right stroke SVG path matches exact specification (M 559.2,215.8 A 272.5 272.5 0 0 0 300,27.5)');

  // Verify mathematical curvature & non-overlapping hemispheric geometry via getTotalLength() and getPointAtLength()
  const arcGeometryCheck = await evaluate(`(() => {
    const strokeLeft = document.getElementById('reveal-stroke-left');
    const strokeRight = document.getElementById('reveal-stroke-right');
    const Cx = 300, Cy = 300;
    const targetR = 272.5;

    const analyzePath = (path, hemisphere) => {
      const len = path.getTotalLength();
      const startPt = path.getPointAtLength(0);
      const endPt = path.getPointAtLength(len);

      let maxRadiusError = 0;
      let stayOnHemisphere = true;
      let worstCross = 0;

      const numSamples = 60;
      for (let i = 0; i <= numSamples; i++) {
        const pt = path.getPointAtLength((i / numSamples) * len);
        const dist = Math.hypot(pt.x - Cx, pt.y - Cy);
        const rErr = Math.abs(dist - targetR);
        if (rErr > maxRadiusError) maxRadiusError = rErr;

        if (hemisphere === 'left') {
          // Left arc must stay on left side (x <= 300 + 0.1), meeting only at shared top endpoint
          if (pt.x > 300.1) {
            stayOnHemisphere = false;
            worstCross = Math.max(worstCross, pt.x - 300);
          }
        } else if (hemisphere === 'right') {
          // Right arc must stay on right side (x >= 300 - 0.1), meeting only at shared top endpoint
          if (pt.x < 299.9) {
            stayOnHemisphere = false;
            worstCross = Math.max(worstCross, 300 - pt.x);
          }
        }
      }

      return {
        length: Math.round(len * 100) / 100,
        start: { x: Math.round(startPt.x * 100) / 100, y: Math.round(startPt.y * 100) / 100 },
        end: { x: Math.round(endPt.x * 100) / 100, y: Math.round(endPt.y * 100) / 100 },
        maxRadiusError,
        stayOnHemisphere,
        worstCross
      };
    };

    return {
      left: analyzePath(strokeLeft, 'left'),
      right: analyzePath(strokeRight, 'right')
    };
  })()`);

  console.log('Arc Geometry & Curvature Verification:', arcGeometryCheck);

  // Assertion 1: Left arc starts at approximately (40.8, 215.8)
  assert(Math.abs(arcGeometryCheck.left.start.x - 40.8) < 0.5 && Math.abs(arcGeometryCheck.left.start.y - 215.8) < 0.5,
    `1. Left arc starts at approx (40.8, 215.8): actual (${arcGeometryCheck.left.start.x}, ${arcGeometryCheck.left.start.y})`);

  // Assertion 2: Right arc starts at approximately (559.2, 215.8)
  assert(Math.abs(arcGeometryCheck.right.start.x - 559.2) < 0.5 && Math.abs(arcGeometryCheck.right.start.y - 215.8) < 0.5,
    `2. Right arc starts at approx (559.2, 215.8): actual (${arcGeometryCheck.right.start.x}, ${arcGeometryCheck.right.start.y})`);

  // Assertion 3: Both arcs terminate at approximately (300, 27.5)
  assert(Math.abs(arcGeometryCheck.left.end.x - 300) < 0.5 && Math.abs(arcGeometryCheck.left.end.y - 27.5) < 0.5,
    `3a. Left arc terminates at approx (300, 27.5): actual (${arcGeometryCheck.left.end.x}, ${arcGeometryCheck.left.end.y})`);
  assert(Math.abs(arcGeometryCheck.right.end.x - 300) < 0.5 && Math.abs(arcGeometryCheck.right.end.y - 27.5) < 0.5,
    `3b. Right arc terminates at approx (300, 27.5): actual (${arcGeometryCheck.right.end.x}, ${arcGeometryCheck.right.end.y})`);

  // Assertion 4: Left arc sample points remain on left side of vertical centerline
  assert(arcGeometryCheck.left.stayOnHemisphere,
    `4. Left arc sample points remain on left side of vertical centerline (x <= 300, worstCross=${arcGeometryCheck.left.worstCross})`);

  // Assertion 5: Right arc sample points remain on right side of vertical centerline
  assert(arcGeometryCheck.right.stayOnHemisphere,
    `5. Right arc sample points remain on right side of vertical centerline (x >= 300, worstCross=${arcGeometryCheck.right.worstCross})`);

  // Assertion 6: Both arcs remain within 0.5 px of the intended 272.5 px radius
  assert(arcGeometryCheck.left.maxRadiusError < 0.5,
    `6a. Left arc radius stays within 0.5px of 272.5px radius (max error=${arcGeometryCheck.left.maxRadiusError.toFixed(3)}px)`);
  assert(arcGeometryCheck.right.maxRadiusError < 0.5,
    `6b. Right arc radius stays within 0.5px of 272.5px radius (max error=${arcGeometryCheck.right.maxRadiusError.toFixed(3)}px)`);

  // Allow WebGL texture to fully load and compile shader
  await new Promise((r) => setTimeout(r, 600));

  // Trigger orchestrated capture run starting at t=0 with texture loaded
  await evaluate(`window.earthController?.triggerReveal?.()`);
  await new Promise((r) => setTimeout(r, 450));

  const shotInitial = await send('Page.captureScreenshot', { format: 'png' });
  writeFileSync('data/processed/_validation/venezuela/reveal_01_approach_initial.png', Buffer.from(shotInitial.data, 'base64'));
  console.log('Saved screenshot -> data/processed/_validation/venezuela/reveal_01_approach_initial.png');

  console.log('\n=== 2. VERIFY MID-FLIGHT SCALE-UP & DIAGONAL STROKE SWEEP (t=1000ms) ===');
  await new Promise((r) => setTimeout(r, 450));

  const midState = await evaluate(`(() => {
    const container = document.querySelector('.earth-container');
    const strokeL = document.getElementById('reveal-stroke-left');
    const strokeR = document.getElementById('reveal-stroke-right');
    const pipL = document.getElementById('reveal-pip-left');
    const pipR = document.getElementById('reveal-pip-right');

    const style = container ? window.getComputedStyle(container) : null;
    const styleL = strokeL ? window.getComputedStyle(strokeL) : null;
    const styleR = strokeR ? window.getComputedStyle(strokeR) : null;

    const parseTranslate = (elem) => {
      if (!elem) return null;
      const t = elem.getAttribute('transform');
      const m = t ? t.match(/translate\\(([-0-9.]+),\\s*([-0-9.]+)\\)/) : null;
      return m ? { x: parseFloat(m[1]), y: parseFloat(m[2]), raw: t } : null;
    };

    return {
      transform: style ? style.transform : '',
      strokeLeftOpacity: styleL ? parseFloat(styleL.opacity) : 0,
      strokeRightOpacity: styleR ? parseFloat(styleR.opacity) : 0,
      pipL: parseTranslate(pipL),
      pipR: parseTranslate(pipR),
      revealState: window.earthController?.getRevealState?.()
    };
  })()`);

  console.log('Mid-Flight State at t=1100ms:', midState);
  // Assertion 8a: Both strokes remain visible during the sweep
  assert(midState.strokeLeftOpacity > 0.3, '8a. Left diagonal stroke is actively illuminated during reveal');
  assert(midState.strokeRightOpacity > 0.3, '8a. Right diagonal stroke is actively illuminated during reveal');

  // Assertion 7a: Both moving pips follow their respective corrected trajectories
  assert(midState.pipL && midState.pipL.x < 300, `7a. Left pip is moving along upper-left silhouette (x=${midState.pipL?.x} < 300)`);
  assert(midState.pipR && midState.pipR.x > 300, `7a. Right pip is moving along upper-right silhouette (x=${midState.pipR?.x} > 300)`);

  const pipLRadius = Math.hypot(midState.pipL.x - 300, midState.pipL.y - 300);
  const pipRRadius = Math.hypot(midState.pipR.x - 300, midState.pipR.y - 300);
  assert(Math.abs(pipLRadius - 272.5) < 0.5, `7a. Left pip radius stays at 272.5px (actual=${pipLRadius.toFixed(2)}px)`);
  assert(Math.abs(pipRRadius - 272.5) < 0.5, `7a. Right pip radius stays at 272.5px (actual=${pipRRadius.toFixed(2)}px)`);

  const shotMid = await send('Page.captureScreenshot', { format: 'png' });
  writeFileSync('data/processed/_validation/venezuela/reveal_02_diagonal_strokes.png', Buffer.from(shotMid.data, 'base64'));
  console.log('Saved screenshot -> data/processed/_validation/venezuela/reveal_02_diagonal_strokes.png');

  console.log('\n=== 2B. VERIFY STROKES APPROACHING TOP OF EARTH CONVERGENCE (t=1850ms) ===');
  await new Promise((r) => setTimeout(r, 750));

  const convergingState = await evaluate(`(() => {
    const strokeL = document.getElementById('reveal-stroke-left');
    const strokeR = document.getElementById('reveal-stroke-right');
    const pipL = document.getElementById('reveal-pip-left');
    const pipR = document.getElementById('reveal-pip-right');

    const styleL = strokeL ? window.getComputedStyle(strokeL) : null;
    const styleR = strokeR ? window.getComputedStyle(strokeR) : null;

    const parseTranslate = (elem) => {
      if (!elem) return null;
      const t = elem.getAttribute('transform');
      const m = t ? t.match(/translate\\(([-0-9.]+),\\s*([-0-9.]+)\\)/) : null;
      return m ? { x: parseFloat(m[1]), y: parseFloat(m[2]), raw: t } : null;
    };

    return {
      strokeLeftOpacity: styleL ? parseFloat(styleL.opacity) : 0,
      strokeRightOpacity: styleR ? parseFloat(styleR.opacity) : 0,
      pipL: parseTranslate(pipL),
      pipR: parseTranslate(pipR),
      revealState: window.earthController?.getRevealState?.()
    };
  })()`);

  console.log('Converging State at t=1850ms:', convergingState);
  // Assertion 7b: Both pips approaching top point (300, 27.5) without crossing
  assert(convergingState.pipL && convergingState.pipL.x <= 300.05, `7b. Left pip approaches top from left (x=${convergingState.pipL?.x} <= 300)`);
  assert(convergingState.pipR && convergingState.pipR.x >= 299.95, `7b. Right pip approaches top from right (x=${convergingState.pipR?.x} >= 300)`);
  assert(convergingState.pipL.y < 80 && convergingState.pipR.y < 80, `7b. Both pips have climbed to northmost sector near y=27.5 (yL=${convergingState.pipL.y}, yR=${convergingState.pipR.y})`);

  const shotConverge = await send('Page.captureScreenshot', { format: 'png' });
  writeFileSync('data/processed/_validation/venezuela/reveal_02b_strokes_converging_top.png', Buffer.from(shotConverge.data, 'base64'));
  console.log('Saved screenshot -> data/processed/_validation/venezuela/reveal_02b_strokes_converging_top.png');

  console.log('\n=== 3. VERIFY FINAL DOCKED HERO STATE & HUD HANDOFF (t=2900ms) ===');
  await new Promise((r) => setTimeout(r, 1200));

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
  // Assertion 8b: Both strokes disappear cleanly afterward
  assert(dockedState.revealGroupDisplay === 'none', '8b. Reveal strokes group cleanly dissolved / hidden after reveal');
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
