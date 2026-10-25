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
    '--remote-debugging-port=9333',
    `--user-data-dir=${profile}`,
    '--no-first-run',
    'about:blank'
  ]);

  await new Promise(r => setTimeout(r, 2000));
  const listRes = await fetch('http://127.0.0.1:9333/json/list');
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
    console.log(`Viewport ${vp.name} (${vp.width}x${vp.height}): result=${JSON.stringify(cardInfo.result.value)}`);
  }

  // Also navigate into explorer and capture screenshot
  await send('Runtime.evaluate', {
    expression: '(() => { document.getElementById("open-explorer").click(); return true; })()'
  });
  await new Promise(r => setTimeout(r, 1500));
  const expShot = await send('Page.captureScreenshot', { format: 'png' });
  writeFileSync('D:/Nasa hackton/data/processed/_validation/venezuela/responsive_explorer_desktop.png', Buffer.from(expShot.data, 'base64'));
  console.log('Captured explorer screenshot');

  child.kill();
  process.exit(0);
}

run().catch(e => { console.error(e); process.exit(1); });
