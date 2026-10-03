#!/usr/bin/env node
/*
 * Composites overlay.html (transparent motion graphics) onto the source talking-head reel.
 *
 *   node compose.js --src ../src/src.mp4                 # -> ../out/alto-reel-dashboard.mp4
 *   node compose.js --src ../src/src.mp4 --stills 4,20   # PNG previews of the real composite
 *
 * Needs: playwright-core (+ Chromium), ffmpeg, python3 with numpy (for sfx.py).
 */
const { chromium } = require('playwright-core');
const { spawnSync, spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

const args = Object.fromEntries(process.argv.slice(2).reduce((acc, a, i, arr) => {
  if (a.startsWith('--')) acc.push([a.slice(2), arr[i + 1] && !arr[i + 1].startsWith('--') ? arr[i + 1] : true]);
  return acc;
}, []));
const SRC = path.resolve(args.src || path.join(__dirname, '../src/src.mp4'));
const OUT_DIR = path.join(__dirname, '../out');
const WORK = path.join(OUT_DIR, '.reel-frames');
const FPS = 25;
const WORKERS = +(args.workers || 6);
const PAGE = 'file://' + path.join(__dirname, 'overlay.html') + '?render=1';
const CHROME = args.chrome || process.env.CHROME_PATH || undefined;

// gentle punch-ins on the speaker during the key lines: [start, end] in seconds
const ZOOMS = [[19.0, 27.0], [37.8, 44.1], [58.2, 62.0], [77.4, 82.5]];
const Z = '1+0.06*(' + ZOOMS.map(([a, b]) => `clip((t-${a})/0.35,0,1)-clip((t-${b})/0.35,0,1)`).join('+') + ')';
// zoom anchored on the burned-in caption line (y≈1120 px) so the captions never slide under the cards
const BASE = `scale=w='2*trunc(1080*(${Z})/2)':h='2*trunc(1920*(${Z})/2)':eval=frame,crop=1080:1920:x='(in_w-1080)*0.42':y='(in_h-1920)*0.583'`;

async function openPage(browser) {
  const page = await browser.newPage({ viewport: { width: 1080, height: 1920 }, deviceScaleFactor: 1 });
  await page.goto(PAGE);
  await page.evaluate(() => window.ready);
  return page;
}
const ff = argv => { const r = spawnSync('ffmpeg', ['-y', '-v', 'error', ...argv], { stdio: 'inherit' }); if (r.status) throw new Error('ffmpeg failed'); };

(async () => {
  fs.mkdirSync(WORK, { recursive: true });
  const browser = await chromium.launch({ executablePath: CHROME });

  if (args.stills) {
    const page = await openPage(browser);
    for (const s of String(args.stills).split(',')) {
      const ov = path.join(WORK, `ov-${s}.png`);
      await page.evaluate(t => window.renderAt(t), +s);
      await page.screenshot({ path: ov, omitBackground: true });
      const out = path.join(OUT_DIR, `still-reel-${s}.png`);
      ff(['-ss', s, '-i', SRC, '-i', ov, '-frames:v', '1', '-filter_complex', `[0:v]setpts=PTS-STARTPTS+${s}/TB,${BASE}[b];[b][1:v]overlay=0:0`, out]);
      console.log(out);
    }
    await browser.close();
    return;
  }

  const first = await openPage(browser);
  const dur = await first.evaluate(() => window.DUR);
  const sfx = await first.evaluate(() => window.SFX);
  await first.close();
  fs.writeFileSync(path.join(WORK, 'sfx.json'), JSON.stringify(sfx));

  const total = Math.round(dur * FPS), per = Math.ceil(total / WORKERS);
  await Promise.all(Array.from({ length: WORKERS }, async (_, w) => {
    const page = await openPage(browser);
    for (let f = w * per; f < Math.min(total, (w + 1) * per); f++) {
      await page.evaluate(t => window.renderAt(t), f / FPS);
      await page.screenshot({ path: path.join(WORK, `f${String(f).padStart(5, '0')}.png`), omitBackground: true });
      if (f % 250 === 0) console.log('frame', f, '/', total);
    }
    await page.close();
  }));
  await browser.close();

  // sound effects track
  const r = spawnSync('python3', [path.join(__dirname, 'sfx.py'), path.join(WORK, 'sfx.json'), path.join(WORK, 'sfx.wav'), String(dur)], { stdio: 'inherit' });
  if (r.status) throw new Error('sfx failed');

  const out = path.join(OUT_DIR, 'alto-reel-dashboard.mp4');
  ff(['-i', SRC, '-framerate', String(FPS), '-i', path.join(WORK, 'f%05d.png'), '-i', path.join(WORK, 'sfx.wav'),
    '-filter_complex', `[0:v]${BASE}[b];[b][1:v]overlay=0:0:format=auto,format=yuv420p[v];[0:a][2:a]amix=inputs=2:normalize=0:weights='1 0.28'[a]`,
    '-map', '[v]', '-map', '[a]', '-c:v', 'libx264', '-preset', 'slow', '-crf', '18', '-r', String(FPS),
    '-c:a', 'aac', '-b:a', '256k', '-movflags', '+faststart', '-t', String(dur), out]);
  console.log('Wrote', out);
})().catch(e => { console.error(e); process.exit(1); });
