// node tools/export3d.mjs <out.glb> <out.stl>
import { chromium } from 'playwright';
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
const [,, glbOut, stlOut] = process.argv;
const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const port = 8000 + Math.floor(Math.random() * 1000);
const server = spawn('python3', ['-m', 'http.server', String(port), '--bind', '127.0.0.1'], { cwd: root, stdio: 'ignore' });
await new Promise(r => setTimeout(r, 700));
const browser = await chromium.launch();
try {
  const page = await browser.newPage();
  page.on('pageerror', e => console.log('[pageerror]', e.message));
  await page.goto(`http://127.0.0.1:${port}/tools/export3d.html`);
  await page.waitForFunction(() => window.ready === true);
  const r = await page.evaluate(() => window.exportModel());
  fs.writeFileSync(glbOut, Buffer.from(r.glb, 'base64'));
  fs.writeFileSync(stlOut, Buffer.from(r.stl, 'base64'));
  console.log(`${r.tris} triangles, ${r.unique} unique part meshes`);
  for (const f of [glbOut, stlOut]) console.log(f, (fs.statSync(f).size / 1e6).toFixed(1), 'MB');
} finally { await browser.close(); server.kill(); }
