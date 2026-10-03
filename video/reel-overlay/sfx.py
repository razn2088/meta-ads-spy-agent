#!/usr/bin/env python3
"""Synthesizes subtle UI sound effects at the overlay's cue times: python3 sfx.py cues.json out.wav duration"""
import json
import sys
import wave

import numpy as np
from scipy.signal import butter, sosfilt

SR = 48000
cues, out, dur = json.load(open(sys.argv[1])), sys.argv[2], float(sys.argv[3])
rng = np.random.default_rng(3)
track = np.zeros(int(SR * dur) + SR)


def seg(d):
    return np.arange(int(d * SR)) / SR


def bp(x, lo, hi):
    return sosfilt(butter(2, [lo, hi], 'band', fs=SR, output='sos'), x)


def tone(f0, f1, d, decay):
    s = seg(d)
    f = f0 + (f1 - f0) * (s / d)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-s / decay)


def whoosh():
    s = seg(0.45)
    n = rng.standard_normal(len(s))
    out = np.zeros_like(s)
    for i in range(8):
        a, b = int(i * len(s) / 8), int((i + 1) * len(s) / 8)
        lo = 400 * 2 ** (i * 3 / 8)
        out[a:b] = bp(n, lo, min(lo * 3, 16000))[a:b]
    env = np.sin(np.pi * np.clip(s / 0.45, 0, 1)) ** 2
    return out * env * 0.35


SOUNDS = {
    'tick': lambda: tone(1800, 1400, 0.06, 0.02) * 0.5,
    'pop': lambda: tone(600, 1200, 0.12, 0.04) * 0.7,
    'send': lambda: tone(900, 1700, 0.14, 0.05) * 0.55,
    'alert': lambda: np.concatenate([tone(1320, 1320, 0.12, 0.06), tone(1760, 1760, 0.2, 0.08)]) * 0.6,
    'hit': lambda: tone(110, 45, 0.9, 0.3) * 0.9,
    'whoosh': whoosh,
}

for t, kind in cues:
    snd = SOUNDS.get(kind, SOUNDS['pop'])()
    start = max(0, int((t - (0.2 if kind == 'whoosh' else 0)) * SR))
    track[start:start + len(snd)] += snd[: len(track) - start]

track = track[: int(SR * dur)]
track = track / max(1e-6, np.abs(track).max()) * 0.8
with wave.open(out, 'wb') as w:
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes((track * 32767).astype('<i2').tobytes())
print('Wrote', out)
