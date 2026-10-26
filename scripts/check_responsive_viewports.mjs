import { spawn } from 'node:child_process';
import { writeFileSync, mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const chrome = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const viewports = [
  { name: 'desktop_1440', width: 1440, height: 900 },
  { name: 'laptop_1280', width: 1280, height: 720 },
  { name: 'tablet_768', width: 768, height: 1024 },
  { name: 'mobile_390', width: 390, height: 844 }
];

async function run() {
  const profile = mkdtempSync(join(tmpdir(), 'chrome-vp-'));
  const child = spawn(chrome, [
    '--headless=new',
    '--disable-gpu',
    '--remote-debugging-port=9335',
    `--user-data-dir=${profile}`,
    '--no-first-run',
    'about:blank'
  ]);

  await new Promise(r => setTimeout(r, 2000));
  const listRes = await fetch('http://127.0.0.1:9335/json/list');
  const targets = await listRes.json();
  const page = targets.find(t => t.type === 'page');
  const ws = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise(r => { ws.onopen = r; });

  let nextId = 0;
  const pending = new Map();
  ws.addEventListener('message', (event) => {
    const msg = JSON.parse(event.data);
    if (msg.id && pending.has(msg.id)) {
      const { resolve, reject } = pending.get(msg.id);
      pending.delete(msg.id);
      if (msg.error) reject(new Error(msg.error.message));
      else resolve(msg.result);
      return;
    }
  });

  const send = (method, params = {}) => new Promise((resolve, reject) => {
    const id = ++nextId;
    pending.set(id, { resolve, reject });
    ws.send(JSON.stringify({ id, method, params }));
  });

  await send('Page.enable');
  await send('Runtime.enable');
  await send('Page.navigate', { url: 'http://127.0.0.1:8011/' });
  await new Promise(r => setTimeout(r, 2500));

  console.log('--- DASHBOARD RESPONSIVE VERIFICATION ---');
  for (const vp of viewports) {
    await send('Emulation.setDeviceMetricsOverride', {
      width: vp.width,
      height: vp.height,
      deviceScaleFactor: 1,
      mobile: vp.width < 600
    });
    await new Promise(r => setTimeout(r, 600));

    const cardInfo = await send('Runtime.evaluate', {
      expression: '(() => { const cards = [...document.querySelectorAll("#observation-cards .card")]; return { count: cards.length, widths: cards.map(c => Math.round(c.getBoundingClientRect().width)), docWidth: document.documentElement.clientWidth, docScrollWidth: document.documentElement.scrollWidth, hasHorizontalOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth }; })()',
      returnByValue: true
    });

    const shot = await send('Page.captureScreenshot', { format: 'png' });
    const outPath = `D:/Nasa hackton/data/processed/_validation/venezuela/responsive_${vp.name}.png`;
    writeFileSync(outPath, Buffer.from(shot.data, 'base64'));
    console.log(`Viewport ${vp.name} (${vp.width}x${vp.height}): result=${JSON.stringify(cardInfo.result?.value)}`);
  }

  console.log('--- EXPLORER VALIDATION PANEL RESPONSIVE VERIFICATION ---');
  await send('Runtime.evaluate', {
    expression: '(() => { showView("explorer"); openObservation("venezuela"); return true; })()'
  });
  await new Promise(r => setTimeout(r, 3000));

  for (const vp of viewports) {
    await send('Emulation.setDeviceMetricsOverride', {
      width: vp.width,
      height: vp.height,
      deviceScaleFactor: 1,
      mobile: vp.width < 600
    });
    await new Promise(r => setTimeout(r, 600));

    // Scroll to validation section to ensure screenshot shows validation panel clearly
    await send('Runtime.evaluate', {
      expression: '(() => { window.scrollTo(0, 350); return true; })()'
    });
    await new Promise(r => setTimeout(r, 300));

    const valInfo = await send('Runtime.evaluate', {
      expression: `(() => {
        const p = document.querySelector('.meta-panel');
        const v = document.getElementById('validation-list');
        const items = [...(v?.querySelectorAll('li') || [])];
        const panelWidth = Math.round(p?.getBoundingClientRect().width || 0);
        const panelScrollWidth = p?.scrollWidth || 0;
        const listWidth = Math.round(v?.getBoundingClientRect().width || 0);
        const listScrollWidth = v?.scrollWidth || 0;
        const maxItemScrollWidth = Math.max(...items.map(i => i.scrollWidth), 0);
        const docWidth = document.documentElement.clientWidth;
        const docScrollWidth = document.documentElement.scrollWidth;

        return {
          panelWidth,
          panelScrollWidth,
          listWidth,
          listScrollWidth,
          maxItemScrollWidth,
          hasPanelOverflow: panelScrollWidth > panelWidth + 2,
          hasListOverflow: listScrollWidth > listWidth + 2,
          docWidth,
          docScrollWidth,
          hasHorizontalOverflow: docScrollWidth > docWidth
        };
      })()`,
      returnByValue: true
    });

    const expShot = await send('Page.captureScreenshot', { format: 'png' });
    const expOutPath = `D:/Nasa hackton/data/processed/_validation/venezuela/responsive_explorer_${vp.name}.png`;
    writeFileSync(expOutPath, Buffer.from(expShot.data, 'base64'));
    console.log(`Explorer ${vp.name} (${vp.width}x${vp.height}): ${JSON.stringify(valInfo.result?.value)}`);
  }

  // Also verify layer switching works cleanly
  console.log('--- LAYER SWITCHING VERIFICATION ---');
  const layers = ['coherence', 'mask', 'components', 'phase'];
  for (const layer of layers) {
    const layerResult = await send('Runtime.evaluate', {
      expression: `(() => {
        const tab = document.querySelector(\`#layer-tabs [data-layer="\${layer}"]\`);
        if (tab) tab.click();
        return {
          clicked: Boolean(tab),
          currentLayer: map.layer,
          legend: document.getElementById('legend')?.textContent.trim()
        };
      })()`,
      returnByValue: true
    });
    await new Promise(r => setTimeout(r, 400));
    console.log(`Switched to ${layer}: ${JSON.stringify(layerResult.result?.value)}`);
  }

  child.kill();
  process.exit(0);
}

run().catch(e => { console.error(e); process.exit(1); });
