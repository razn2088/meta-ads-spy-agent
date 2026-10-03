#!/usr/bin/env python3
"""
Lays the narration clips onto the timeline from narration.json, ducks the music under the voice,
and muxes the result into the already-rendered videos (no re-render).

    out/vo/en/s1.wav, s2.wav, ...   one clip per line id (any format ffmpeg reads)
    out/music.wav                   from music.py
    python3 voiceover.py en he      -> out/alto-dashboard-<lang>.mp4 with voice + music

Clips are trimmed of leading/trailing silence; a clip longer than its slot is sped up
slightly (max 15%), and anything still too long is reported.
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
OUT = HERE / 'out'
SR = 48000
DUR = 73.0
GAP = 0.15        # minimum breath between consecutive lines
MAX_TEMPO = 1.15


def decode(path, filters=''):
    af = ['-af', filters] if filters else []
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(path), *af, '-ac', '1', '-ar', str(SR), '-f', 'f32le', '-'],
                         check=True, capture_output=True).stdout
    return np.frombuffer(raw, dtype='<f4').copy()


TRIM = ('silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.02,'
        'areverse,silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05,areverse')


def build_voice_track(lang, lines):
    track = np.zeros(int(SR * DUR), dtype=np.float32)
    for i, ln in enumerate(lines):
        clip_path = next((OUT / 'vo' / lang).glob(ln['id'] + '.*'), None)
        if clip_path is None:
            sys.exit(f'missing clip out/vo/{lang}/{ln["id"]}.*')
        clip = decode(clip_path, TRIM)
        end = lines[i + 1]['at'] - GAP if i + 1 < len(lines) else DUR - 0.6
        slot = end - ln['at']
        dur = len(clip) / SR
        if dur > slot:
            tempo = min(MAX_TEMPO, dur / slot)
            clip = decode(clip_path, f'{TRIM},atempo={tempo:.3f}')
            dur = len(clip) / SR
            note = f'sped up x{tempo:.2f}'
        else:
            note = 'ok'
        status = 'OVERRUNS by %.2fs' % (dur - slot) if dur > slot + 0.01 else note
        print(f'  [{lang}] {ln["id"]:4s} at {ln["at"]:5.1f}s  {dur:4.1f}s / slot {slot:4.1f}s  {status}')
        a = int(ln['at'] * SR)
        b = min(len(track), a + len(clip))
        track[a:b] += clip[: b - a]
    return track


def write_wav(path, x):
    import wave
    pcm = (np.clip(x, -1, 1) * 32767).astype('<i2')
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def main(langs):
    cfg = json.loads((HERE / 'narration.json').read_text(encoding='utf-8'))
    lines = sorted(cfg['lines'], key=lambda l: l['at'])
    for lang in langs:
        voice = build_voice_track(lang, lines)
        vo_wav = OUT / 'vo' / f'voice-{lang}.wav'
        write_wav(vo_wav, voice / max(1e-6, np.abs(voice).max()) * 0.9)
        video = OUT / f'alto-dashboard-{lang}.mp4'
        tmp = OUT / f'.tmp-{lang}.mp4'
        graph = (
            '[1:a]aresample=48000,loudnorm=I=-27:TP=-3[mus];'
            '[2:a]aresample=48000,loudnorm=I=-17:TP=-2,asplit=2[vo][key];'
            '[mus][key]sidechaincompress=threshold=0.03:ratio=5:attack=15:release=450:makeup=1[duck];'
            '[duck][vo]amix=inputs=2:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=11[a]'
        )
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', str(video), '-i', str(OUT / 'music.wav'), '-i', str(vo_wav),
                        '-filter_complex', graph, '-map', '0:v', '-map', '[a]', '-c:v', 'copy',
                        '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-t', str(DUR), '-movflags', '+faststart', str(tmp)],
                       check=True)
        tmp.replace(video)
        print('Wrote', video)


if __name__ == '__main__':
    main(sys.argv[1:] or ['en', 'he'])
