// Pictures and PDF for the building instructions (called by tools/instructions.py).
//   node tools/instructions.mjs render <dir>       renders <dir>/img/* from <dir>/plan.json
//   node tools/instructions.mjs pdf <html> <pdf>   prints the booklet
import { chromium } from 'playwright';
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

const [,, mode, a, b] = process.argv;
const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const browser = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
const save = (file, dataUrl) => fs.writeFileSync(file, Buffer.from(dataUrl.split(',')[1], 'base64'));

try {
  if (mode === 'render') {
    const dir = path.resolve(a), img = path.join(dir, 'img');
    fs.mkdirSync(img, { recursive: true });
    const plan = JSON.parse(fs.readFileSync(path.join(dir, 'plan.json'), 'utf8'));
    const port = 8000 + Math.floor(Math.random() * 1000);
    const server = spawn('python3', ['-m', 'http.server', String(port), '--bind', '127.0.0.1'], { cwd: root, stdio: 'ignore' });
    await new Promise(r => setTimeout(r, 700));
    try {
      const page = await browser.newPage({ viewport: { width: 1500, height: 940 } });
      page.on('pageerror', e => console.log('[pageerror]', e.message));
      await page.goto(`http://127.0.0.1:${port}/tools/instructions.html?w=1500&h=940`);
      await page.waitForFunction(() => window.ready === true);
      const info = await page.evaluate(p => window.load(p), plan);
      if (!info.ok) throw new Error('the build plan does not match the model');
      const views = [];
      let prev = -55;
      const only = process.env.INSTR_STEPS ? new Set(process.env.INSTR_STEPS.split(',').map(Number)) : null;
      for (let i = 0; i < plan.steps.length; i++) {
        if (only && !only.has(i + 1)) continue;
        const r = await page.evaluate(([i, prev]) => window.renderStep(i, prev), [i, prev]);
        save(path.join(img, `step-${String(i + 1).padStart(3, '0')}.jpg`), r.img);
        views.push({ az: r.az, el: r.el });
        prev = r.az;
        for (const m of plan.steps[i].mounts)
          save(path.join(img, `sub-${m.sub.replace('.ldr', '')}.jpg`), await page.evaluate(([s, az]) => window.renderSub(s, az, 26, 640, 420), [m.sub, r.az]));
        process.stdout.write(`\rsteg ${i + 1}/${plan.steps.length}`);
      }
      console.log();
      if (!only) for (const lot of plan.lots)
        save(path.join(img, `part-${lot.key}.png`), await page.evaluate(([i]) => window.renderPart(i, 220), [lot.index]));
      fs.writeFileSync(path.join(dir, 'views.json'), JSON.stringify(views));
      console.log('rendered', plan.steps.length, 'steps,', plan.lots.length, 'parts');
    } finally { server.kill(); }
  } else if (mode === 'pdf') {
    const page = await browser.newPage();
    await page.goto('file://' + path.resolve(a), { waitUntil: 'networkidle' });
    await page.evaluate(() => document.fonts.ready);
    await page.pdf({ path: b, format: 'A4', landscape: true, printBackground: true, preferCSSPageSize: true });
    console.log('wrote', b);
  }
} finally { await browser.close(); }
