#!/usr/bin/env python3
"""Sound design for the Alto end card (5 s): python3 outro_sfx.py out.wav"""
import sys
import wave

import numpy as np
from scipy.signal import butter, sosfilt

SR, DUR = 48000, 5.0
rng = np.random.default_rng(11)
N = int(SR * DUR)
L = np.zeros(N)
R = np.zeros(N)


def seg(d):
    return np.arange(int(d * SR)) / SR


def bp(x, lo, hi):
    return sosfilt(butter(2, [lo, hi], 'band', fs=SR, output='sos'), x)


def lp(x, hz):
    return sosfilt(butter(2, hz, 'low', fs=SR, output='sos'), x)


def place(sig, at, gain=1.0, pan=0.0):
    i = int(at * SR)
    j = min(N, i + len(sig))
    L[i:j] += sig[: j - i] * gain * (1 - max(0, pan))
    R[i:j] += sig[: j - i] * gain * (1 + min(0, pan))


def riser(d, lo0, lo1):
    s = seg(d)
    n = rng.standard_normal(len(s))
    out = np.zeros_like(s)
    k = 14
    for i in range(k):
        a, b = int(i * len(s) / k), int((i + 1) * len(s) / k)
        lo = lo0 * (lo1 / lo0) ** (i / k)
        out[a:b] = bp(n, lo, min(lo * 3.5, 18000))[a:b]
    return out


# 1 · arrow whoosh up (0.05–0.75)
s = seg(0.75)
w = riser(0.75, 250, 4000) * np.sin(np.pi * np.clip(s / 0.75, 0, 1)) ** 1.5
place(w, 0.05, 0.55)
# 2 · landing: soft sub hit + bright click when the arrow becomes the "l" (~0.95)
s = seg(1.4)
hit = np.sin(2 * np.pi * (48 + 60 * np.exp(-s / 0.05)) * s) * np.exp(-s / 0.45)
click = bp(rng.standard_normal(len(s)), 2500, 9000) * np.exp(-s / 0.012)
place(hit * 0.9 + click * 0.35, 0.95)
# letters pop (a, t, o)
for i, at in enumerate([1.0, 1.08, 1.16]):
    s = seg(0.18)
    f = 700 + 180 * i
    place(np.sin(2 * np.pi * (f + 500 * s / 0.18) * s) * np.exp(-s / 0.05) * 0.28, at, pan=(-0.4, 0.2, 0.5)[i])
# 3 · tagline sparkles, one per letter
for i in range(20):
    s = seg(0.25)
    f = 2400 + 900 * ((i * 7) % 5) / 4
    place(np.sin(2 * np.pi * f * s) * np.exp(-s / 0.06) * 0.07, 1.62 + i * 0.055, pan=np.sin(i * 1.3) * 0.5)
# warm pad (Cmaj9) under the hold
s = seg(3.9)
pad = sum(np.sin(2 * np.pi * 261.63 * 2 ** (n / 12) * s + k) for n, k in [(-12, 0), (0, 1), (4, 2), (7, 3), (14, 4)])
env = np.clip(s / 0.8, 0, 1) * np.clip((3.9 - s) / 0.9, 0, 1)
place(lp(pad, 1800) * env * 0.06, 1.0)
# 4 · exit whoosh + low boom when the chevron clears
s = seg(0.8)
place(riser(0.8, 300, 6000) * np.sin(np.pi * np.clip(s / 0.8, 0, 1)) ** 1.3, 3.85, 0.6)
s = seg(0.6)
place(np.sin(2 * np.pi * (40 + 30 * np.exp(-s / 0.08)) * s) * np.exp(-s / 0.25) * 0.6, 4.55)

mix = np.stack([L, R])
mix *= np.clip((DUR - np.arange(N) / SR) / 0.25, 0, 1)
mix = np.tanh(mix * 1.1)
mix /= np.abs(mix).max() / 0.89
with wave.open(sys.argv[1], 'wb') as wv:
    wv.setnchannels(2)
    wv.setsampwidth(2)
    wv.setframerate(SR)
    wv.writeframes((mix.T * 32767).astype('<i2').tobytes())
print('Wrote', sys.argv[1])
