# Alto Dashboard – client explainer video

A ~73-second animated explainer (1920×1080, 30 fps) for clients. It covers what the Alto Dashboard is, how to use it, and what they get from it. Branding is Alto dark blue and white.

| File | What it is |
|---|---|
| `out/alto-dashboard-en.mp4` | English version |
| `out/alto-dashboard-he.mp4` | Hebrew version (RTL) |
| `alto-explainer.html` | The animation source. Open it in a browser to preview (`?lang=he` for Hebrew; Space pauses, ←/→ seeks, click the frame to jump) |
| `render.js` | Renders the HTML to MP4 frame by frame with headless Chromium and ffmpeg |
| `out/alto-ad-reel-he.mp4` | 18.5 s Reel ad for Facebook/Instagram (9:16, content kept inside the 4:5 crop). Copy and lead form: `ad-copy.md` |
| `alto-ad.html` | The ad's animation source (`?guides=1` shows the 4:5 crop and the text-safe area) |
| `out/alto-endcard.mp4` | 5 s branded end card (1080×1920) to append to reels: arrow lands as the "l", tagline types in, gradient chevron wipes out. Source `outro/outro.html`, sound `outro/outro_sfx.py` |
| `music.py` | Synthesizes the royalty-free background track: 120 BPM upbeat electronic, with whooshes and impacts timed to the scene cuts |

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
```

### Music

Both MP4s include the generated soundtrack, normalized to -16 LUFS. To rebuild or replace it:

```bash
pip install numpy scipy
python3 music.py                                  # -> out/music.wav
# mux it into an existing render (no re-render needed):
ffmpeg -i out/alto-dashboard-en.mp4 -i out/music.wav -map 0:v -map 1:a -c:v copy \
  -af loudnorm=I=-16:TP=-1.5 -c:a aac -b:a 192k -shortest out/with-music.mp4
```

To use your own track instead, put its file in place of `out/music.wav` in that command. The same applies to a voice-over.

### Re-rendering the ad

```bash
python3 music.py --dur 18.5 --bpm 128 --drop 0 --build 0 --outro 17.6 \
  --cuts 2.6,5.2,9,12.4,13.2,14,14.8 --arp-start 0 --out out/music-ad.wav
node render.js --page alto-ad.html --name alto-ad-reel --lang he --audio out/music-ad.wav
```

### Re-rendering the end card

```bash
python3 outro/outro_sfx.py out/outro-sfx.wav
node render.js --page outro/outro.html --name alto-endcard --fps 30 --audio out/outro-sfx.wav
```

Pass `--chrome /path/to/chrome` if Playwright's bundled browser isn't installed.
