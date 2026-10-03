# Alto Dashboard – client explainer video

A ~73-second animated explainer (1920×1080, 30 fps) for clients. It covers what the Alto Dashboard is, how to use it, and what they get from it. Branding is Alto dark blue and white.

| File | What it is |
|---|---|
| `out/alto-dashboard-en.mp4` | English version |
| `out/alto-dashboard-he.mp4` | Hebrew version (RTL) |
| `alto-explainer.html` | The animation source. Open it in a browser to preview (`?lang=he` for Hebrew; Space pauses, ←/→ seeks, click the frame to jump) |
| `render.js` | Renders the HTML to MP4 frame by frame with headless Chromium and ffmpeg |

## Storyboard

| Time | Scene |
|---|---|
| 0:00 | Logo intro: "Competitor Intelligence Dashboard" |
| 0:04 | The problem: competitors launch new ads every week. Are you keeping up? |
| 0:11 | Introducing the Alto Dashboard: tracks Meta ads, AI spots changes, insights on WhatsApp |
| 0:18 | How it works in 3 steps: add competitors → Alto scans → get your report |
| 0:29 | Dashboard walkthrough: add a competitor, run the agent with one click, view run history |
| 0:47 | The WhatsApp report: what changed, their strategy, your next moves, ads to look at |
| 0:59 | Benefits: save hours, never miss a move, act with clarity, delivered to WhatsApp |
| 1:07 | Outro: "See every move. Make the next one." |

## Editing and re-rendering

All on-screen text is in the `STR` object at the top of the `<script>` in `alto-explainer.html`, with one block per language. Brand colours are the CSS variables in `:root`. The logo is the `#alto-mark` SVG symbol, plus the two inline marks in scenes 1 and 8. Swap in the official logo there.

```bash
cd video
npm i playwright-core          # one time; needs Chromium + ffmpeg on the machine
node render.js --lang en       # -> out/alto-dashboard-en.mp4
node render.js --lang he       # -> out/alto-dashboard-he.mp4
node render.js --stills 5,30   # quick PNG previews at given seconds
node render.js --lang en --audio music.mp3   # add a music or voice-over track
```

Pass `--chrome /path/to/chrome` if Playwright's bundled browser isn't installed.
