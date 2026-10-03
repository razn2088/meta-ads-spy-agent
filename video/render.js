#!/usr/bin/env node
/*
 * Renders alto-explainer.html to an MP4, frame by frame (deterministic, no dropped frames).
 *
 *   npm i playwright-core            # once
 *   node render.js --lang en         # -> out/alto-dashboard-en.mp4
 *   node render.js --lang he         # -> out/alto-dashboard-he.mp4 (Hebrew, RTL)
 *   node render.js --stills 2,15,40  # just grab PNG stills at those seconds
 *
 * Options: --fps 30  --chrome /path/to/chrome  --workers 4  --audio music.mp3
 *          --page other.html --query "format=feed" --name out-file-prefix
 */
const { chromium } = require('playwright-core');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

const args = Object.fromEntries(process.argv.slice(2).reduce((acc, a, i, arr) => {
  if (a.startsWith('--')) acc.push([a.slice(2), arr[i + 1] && !arr[i + 1].startsWith('--') ? arr[i + 1] : true]);
  return acc;
}, []));
const LANG = args.lang || 'en';
const FPS = +(args.fps || 30);
const WORKERS = +(args.workers || 4);
const OUT_DIR = path.join(__dirname, 'out');
const CHROME = args.chrome || process.env.CHROME_PATH || undefined;
const PAGE_FILE = args.page || 'alto-explainer.html';
const NAME = args.name || 'alto-dashboard';
const PAGE = 'file://' + path.join(__dirname, PAGE_FILE) + `?render=1&lang=${LANG}` + (args.query ? '&' + args.query : '');
fs.mkdirSync(OUT_DIR, { recursive: true });

async function openPage(browser) {
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  await page.goto(PAGE);
  await page.evaluate(() => window.ready);
  // pages may declare their own frame size (e.g. vertical ads)
  const size = await page.evaluate(() => window.STAGE || { w: 1920, h: 1080 });
  if (size.w !== 1920 || size.h !== 1080) {
    await page.setViewportSize({ width: size.w, height: size.h });
    await page.evaluate(() => window.dispatchEvent(new Event('resize')));
  }
  return page;
}

function ffmpeg(argv) {
  const p = spawn('ffmpeg', argv, { stdio: ['pipe', 'ignore', 'inherit'] });
  const done = new Promise((res, rej) => p.on('close', c => (c === 0 ? res() : rej(new Error('ffmpeg exited ' + c)))));
  return { stdin: p.stdin, done };
}

async function renderChunk(browser, from, to, file) {
  const page = await openPage(browser);
  const ff = ffmpeg(['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(FPS), '-c:v', 'png', '-i', '-',
    '-c:v', 'libx264', '-preset', 'medium', '-crf', '16', '-pix_fmt', 'yuv420p', file]);
  for (let f = from; f < to; f++) {
    await page.evaluate(t => window.renderAt(t), f / FPS);
    const buf = await page.screenshot({ type: 'png' });
    if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
    if (f % (FPS * 5) === 0) console.log(`[${LANG}] frame ${f} (${(f / FPS).toFixed(1)}s)`);
  }
  ff.stdin.end();
  await ff.done;
  await page.close();
}

(async () => {
  const browser = await chromium.launch({ executablePath: CHROME, args: ['--force-color-profile=srgb', '--hide-scrollbars'] });

  if (args.stills) {
    const page = await openPage(browser);
    for (const s of String(args.stills).split(',')) {
      await page.evaluate(t => window.renderAt(t), +s);
      const f = path.join(OUT_DIR, `still-${NAME}-${LANG}-${s}.png`);
      await page.screenshot({ path: f });
      console.log(f);
    }
    await browser.close();
    return;
  }

  const dur = await (await openPage(browser)).evaluate(() => window.DUR);
  const total = Math.round(dur * FPS);
  const per = Math.ceil(total / WORKERS);
  const parts = [];
  await Promise.all(Array.from({ length: WORKERS }, (_, i) => {
    const from = i * per, to = Math.min(total, from + per);
    const file = path.join(OUT_DIR, `.part-${NAME}-${LANG}-${i}.mp4`);
    parts.push(file);
    return renderChunk(browser, from, to, file);
  }));
  await browser.close();

  const list = path.join(OUT_DIR, `.parts-${NAME}-${LANG}.txt`);
  fs.writeFileSync(list, parts.map(p => `file '${p}'`).join('\n'));
  const out = path.join(OUT_DIR, `${NAME}-${LANG}.mp4`);
  const audio = args.audio ? ['-i', args.audio, '-map', '0:v', '-map', '1:a', '-c:a', 'aac', '-b:a', '192k', '-shortest'] : [];
  const ff = ffmpeg(['-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', list, ...audio, '-c:v', 'copy', '-movflags', '+faststart', out]);
  ff.stdin.end();
  await ff.done;
  parts.forEach(p => fs.unlinkSync(p));
  fs.unlinkSync(list);
  console.log('Wrote', out);
})().catch(e => { console.error(e); process.exit(1); });
