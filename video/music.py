#!/usr/bin/env python3
"""
Synthesizes the background music for the Alto explainer (royalty-free, generated from code).

120 BPM, upbeat electronic: pads, plucky arpeggio, bass, four-on-the-floor drums.
Whooshes and impacts land exactly on the video's scene cuts (see SCENE_CUTS).

    pip install numpy scipy
    python3 music.py                 # -> out/music.wav (explainer)
    python3 music.py --dur 18.5 --bpm 128 --drop 0 --build 0 --outro 17.6 \
        --cuts 2.6,5.2,9,12.4,13.2,14,14.8 --out out/music-ad.wav   # (the ad)
"""
from pathlib import Path
import argparse
import wave

import numpy as np
from scipy.signal import butter, sosfilt

ap = argparse.ArgumentParser()
ap.add_argument('--dur', type=float, default=73.0)
ap.add_argument('--bpm', type=float, default=120)
ap.add_argument('--cuts', default='4.5,11,18,29,47,59,67', help='scene-cut times for whooshes')
ap.add_argument('--build', type=float, default=4.5, help='hats + soft bass start')
ap.add_argument('--drop', type=float, default=11.0, help='full beat starts')
ap.add_argument('--outro', type=float, default=67.0, help='final hit; beat stops')
ap.add_argument('--arp-start', type=float, default=1.0)
ap.add_argument('--out', default=str(Path(__file__).parent / 'out' / 'music.wav'))
A = ap.parse_args()

SR = 44100
DUR = A.dur
BPM = A.bpm
BEAT = 60 / BPM
STEP = BEAT / 4                     # 16th note
SCENE_CUTS = [float(c) for c in A.cuts.split(',') if c]
BUILD = A.build                     # hats + soft bass come in
DROP = A.drop                       # full beat (explainer: "Introducing the Alto Dashboard")
OUTRO = A.outro                     # final logo hit

N = int(SR * DUR)
t = np.arange(N) / SR
rng = np.random.default_rng(7)


def midi(n):
    return 440.0 * 2 ** ((n - 69) / 12)


def lp(x, hz, order=2):
    return sosfilt(butter(order, hz, 'low', fs=SR, output='sos'), x)


def hp(x, hz, order=2):
    return sosfilt(butter(order, hz, 'high', fs=SR, output='sos'), x)


def bp(x, lo, hi, order=2):
    return sosfilt(butter(order, [lo, hi], 'band', fs=SR, output='sos'), x)


def place(buf, sig, at, gain=1.0):
    i = int(at * SR)
    if i < 0:
        sig, i = sig[-i:], 0
    if i >= len(buf):
        return
    j = min(len(buf), i + len(sig))
    buf[i:j] += sig[: j - i] * gain


def seg(d):
    return np.arange(int(d * SR)) / SR


# C – G – Am – F, one chord per bar
CHORDS = [
    dict(bass=36, pad=[60, 64, 67], arp=[72, 76, 79, 84]),
    dict(bass=43, pad=[59, 62, 67], arp=[67, 71, 74, 79]),
    dict(bass=45, pad=[57, 60, 64], arp=[69, 72, 76, 81]),
    dict(bass=41, pad=[57, 60, 65], arp=[65, 69, 72, 77]),
]
BAR = BEAT * 4


def chord_at(time):
    return CHORDS[int(time // BAR) % 4]


# ---------------------------------------------------------------- layers
pad = np.zeros(N)
arp = np.zeros(N)
bass = np.zeros(N)
kick = np.zeros(N)
clap = np.zeros(N)
hats = np.zeros(N)
fx = np.zeros(N)

# pads: detuned saws per bar with soft attack/release
nbars = int(np.ceil(DUR / BAR))
for b in range(nbars):
    start = b * BAR
    if start >= OUTRO:
        break
    d = BAR + 0.4
    s = seg(d)
    tone = np.zeros_like(s)
    for n in chord_at(start)['pad']:
        for det in (-0.08, 0.0, 0.08):
            f = midi(n + det)
            tone += 2 * ((s * f) % 1.0) - 1
    env = np.minimum(1, s / 0.25) * np.clip((d - s) / 0.4, 0, 1)
    place(pad, tone * env / 9, start)
# outro: one long C chord
s = seg(DUR - OUTRO)
tone = sum(2 * ((s * midi(n + det)) % 1.0) - 1 for n in [48, 60, 64, 67, 72] for det in (-0.08, 0, 0.08))
place(pad, tone * np.exp(-s / 2.2) / 9, OUTRO)
pad = lp(pad, 1600)

# arpeggio: 16th-note plucks over the chord tones
PATTERN = [0, 1, 2, 3, 2, 1, 2, 3]
k = 0
time = A.arp_start
while time < OUTRO:
    c = chord_at(time)
    n = c['arp'][PATTERN[k % 8]]
    s = seg(0.35)
    f = midi(n)
    tri = 2 * np.abs(2 * ((s * f) % 1.0) - 1) - 1
    note = (0.6 * np.sin(2 * np.pi * f * s) + 0.4 * tri) * np.exp(-s / 0.09)
    accent = 1.0 if k % 4 == 0 else 0.7
    place(arp, note * accent, time)
    k += 1
    time += STEP
arp = lp(arp, 5000)

# bass: driving 8ths on the root, from the drop
time = DROP
while time < OUTRO:
    c = chord_at(time)
    s = seg(BEAT / 2)
    f = midi(c['bass'])
    note = np.tanh(2.2 * (np.sin(2 * np.pi * f * s) + 0.35 * np.sin(4 * np.pi * f * s)))
    env = np.minimum(1, s / 0.005) * np.exp(-s / 0.18)
    place(bass, note * env, time)
    time += BEAT / 2
# softer bass pulse in the build-up
time = BUILD
while time < DROP:
    s = seg(BEAT)
    f = midi(chord_at(time)['bass'])
    place(bass, np.sin(2 * np.pi * f * s) * np.exp(-s / 0.3) * 0.55, time)
    time += BEAT
bass = lp(bass, 900)

# drums
def kick_hit():
    s = seg(0.45)
    f = 45 + 85 * np.exp(-s / 0.03)
    ph = 2 * np.pi * np.cumsum(f) / SR
    return np.sin(ph) * np.exp(-s / 0.16) + 0.3 * rng.standard_normal(len(s)) * np.exp(-s / 0.003)


def clap_hit():
    s = seg(0.3)
    env = sum(np.exp(-np.clip(s - o, 0, None) / (0.012 if o < 0.02 else 0.09)) * (s >= o) for o in (0, 0.011, 0.022))
    return bp(rng.standard_normal(len(s)), 900, 3200) * env


def hat_hit(decay=0.035):
    s = seg(0.12)
    return hp(rng.standard_normal(len(s)), 7000) * np.exp(-s / decay)


kick_times = []
beat_i = 0
time = 0.0
while time < OUTRO:
    full = time >= DROP
    if full:
        place(kick, kick_hit(), time)
        kick_times.append(time)
        if beat_i % 2 == 1:
            place(clap, clap_hit(), time)
    if time >= BUILD:
        place(hats, hat_hit(), time + BEAT / 2, 1.0 if full else 0.6)
        if full:
            place(hats, hat_hit(0.018), time + BEAT / 4, 0.35)
            place(hats, hat_hit(0.018), time + 3 * BEAT / 4, 0.35)
    beat_i += 1
    time += BEAT
place(kick, kick_hit(), OUTRO, 1.2)

# sidechain pump on pads/bass from the kick
duck = np.ones(N)
for kt in kick_times:
    s = seg(0.4)
    i = int(kt * SR)
    j = min(N, i + len(s))
    duck[i:j] = np.minimum(duck[i:j], 1 - 0.55 * np.exp(-s[: j - i] / 0.11))
pad *= duck
bass *= 0.4 + 0.6 * duck

# fx: whooshes into every scene cut, impacts on logo moments, riser into the drop
def whoosh(length=0.7):
    s = seg(length + 0.25)
    noise = rng.standard_normal(len(s))
    out = np.zeros_like(s)
    # step the band-pass upward to sweep the noise
    steps = 10
    for i in range(steps):
        a, b = int(i * len(s) / steps), int((i + 1) * len(s) / steps)
        lo = 300 * 2 ** (i * 4 / steps)
        out[a:b] = bp(noise, lo, min(lo * 4, 16000))[a:b]
    rise = np.clip(s / length, 0, 1) ** 2.5
    tail = np.exp(-np.clip(s - length, 0, None) / 0.06)
    return out * rise * tail


def impact():
    s = seg(2.5)
    boom = np.sin(2 * np.pi * (40 + 40 * np.exp(-s / 0.08)) * s) * np.exp(-s / 0.7)
    crash = hp(rng.standard_normal(len(s)), 4000) * np.exp(-s / 0.9) * 0.35
    return boom + crash


for cut in SCENE_CUTS:
    place(fx, whoosh(), cut - 0.7, 0.45)
place(fx, impact(), 0.12, 0.9)
place(fx, impact(), OUTRO, 1.0)
s = seg(2.5)
riser = hp(rng.standard_normal(len(s)), 1500) * (s / 2.5) ** 3
place(fx, riser, DROP - 2.5, 0.35)

# ---------------------------------------------------------------- mix
def stereo(x, width=0.0, delay_ms=0.0):
    d = int(delay_ms * SR / 1000)
    r = np.concatenate([np.zeros(d), x[: len(x) - d]]) if d else x
    return np.stack([x * (1 - width) + r * width, r * (1 - width) + x * width])


# ping-pong echo on the arp
d = int(STEP * 3 * SR)
arp_l = arp.copy()
arp_r = np.zeros(N)
echo = arp.copy()
for i in range(4):
    echo = np.concatenate([np.zeros(d), echo[:-d]]) * 0.38
    (arp_r if i % 2 == 0 else arp_l)[:] += echo

intro_lpf = np.clip((t - A.arp_start) / max(0.01, DROP - A.arp_start - 1), 0.25, 1.0) if DROP > A.arp_start else 1.0   # arp opens up through the build
mix = (
    stereo(pad, 0.3, 11) * 1.1
    + np.stack([arp_l, arp_r]) * 0.75 * intro_lpf
    + stereo(hp(bass, 35)) * 0.3
    + stereo(hp(kick, 35)) * 0.42
    + stereo(clap, 0.25, 7) * 0.5
    + stereo(hats, 0.4, 5) * 0.2
    + stereo(fx, 0.3, 9) * 0.6
)
fade = np.clip(t / 0.03, 0, 1) * np.clip((DUR - t) / 1.2, 0, 1)
mix *= fade
mix = np.tanh(mix * 1.2) / np.tanh(1.2)
mix /= np.max(np.abs(mix)) / 0.89

out = Path(A.out)
out.parent.mkdir(exist_ok=True)
pcm = (mix.T * 32767).astype('<i2')
with wave.open(str(out), 'wb') as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(pcm.tobytes())
print('Wrote', out)
