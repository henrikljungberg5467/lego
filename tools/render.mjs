// Usage: node tools/render.mjs <model.ldr|mpd> <outprefix> [views-json]
// views-json: [{"name":"front","az":30,"el":20, ...opts}]
import { chromium } from 'playwright';
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

const [,, modelPath, outPrefix, viewsArg] = process.argv;
const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const port = 8000 + Math.floor(Math.random() * 1000);
const server = spawn('python3', ['-m', 'http.server', String(port), '--bind', '127.0.0.1'], { cwd: root, stdio: 'ignore' });
await new Promise(r => setTimeout(r, 700));
const defaultViews = [
  { name: 'ref', az: 120, el: 22 },
  { name: 'front', az: 90, el: 10 },
  { name: 'side', az: 180, el: 0, ortho: true },
  { name: 'top', az: 180, el: 89.9, ortho: true },
  { name: 'rear', az: 300, el: 25 },
  { name: 'under', az: 120, el: -30 },
];
const views = viewsArg ? JSON.parse(viewsArg) : defaultViews;
const browser = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
try {
  const w = views[0].w || 1200, h = views[0].h || 900;
  const page = await browser.newPage({ viewport: { width: w, height: h } });
  page.on('console', m => { if ((m.type() === 'error' || m.type() === 'warning') && !m.text().includes('404')) console.log('[page]', m.text().slice(0, 300)); });
  page.on('pageerror', e => console.log('[pageerror]', e.message));
  await page.goto(`http://127.0.0.1:${port}/tools/render.html?w=${w}&h=${h}`);
  await page.waitForFunction(() => window.ready === true);
  const rel = path.relative(root, path.resolve(modelPath));
  const info = await page.evaluate(u => window.loadModel(u), '/' + rel.split(path.sep).map(encodeURIComponent).join('/'));
  console.log('loaded', JSON.stringify(info));
  for (const v of views) {
    const data = await page.evaluate(([az, el, o]) => window.renderView(az, el, o), [v.az, v.el, v]);
    const file = `${outPrefix}-${v.name}.png`;
    fs.writeFileSync(file, Buffer.from(data.split(',')[1], 'base64'));
    console.log('wrote', file);
  }
} finally {
  await browser.close();
  server.kill();
}
