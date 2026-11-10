"""Procedural sound effects + soft background music (no downloads, no copyright)."""
import wave
import numpy as np

SR = 44100


def _env(n, a=.01, r=.2):
    t = np.arange(n) / SR
    e = np.minimum(1, t / max(a, 1e-4)) * np.exp(-t / max(r, 1e-4))
    return e


def sfx(name):
    if name == "whoosh":
        n = int(SR * .45)
        noise = np.random.default_rng(1).normal(0, 1, n)
        k = np.linspace(0, 1, n)
        # sweep a band-pass-ish by modulating a one-pole filter
        out = np.zeros(n)
        y = 0.0
        for i in range(n):
            a = .02 + .6 * np.sin(np.pi * k[i]) ** 2
            y += a * (noise[i] - y)
            out[i] = y
        out *= np.sin(np.pi * k) ** 1.5
        return out / (np.abs(out).max() + 1e-9) * .5
    if name == "pop":
        n = int(SR * .18)
        t = np.arange(n) / SR
        f = 900 * np.exp(-t * 18) + 250
        return np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(n, .002, .05) * .55
    if name == "ding":
        n = int(SR * 1.0)
        t = np.arange(n) / SR
        return (np.sin(2 * np.pi * 1318 * t) + .4 * np.sin(2 * np.pi * 2637 * t)) * _env(n, .003, .35) * .35
    if name == "boom":
        n = int(SR * .9)
        t = np.arange(n) / SR
        f = 120 * np.exp(-t * 3.5) + 38
        rng = np.random.default_rng(2)
        return (np.sin(2 * np.pi * np.cumsum(f) / SR) * .8 + rng.normal(0, .15, n) * np.exp(-t * 9)) * _env(n, .004, .3) * .7
    if name == "hit":
        n = int(SR * .35)
        t = np.arange(n) / SR
        f = 200 * np.exp(-t * 20) + 90
        rng = np.random.default_rng(3)
        return (np.sin(2 * np.pi * np.cumsum(f) / SR) * .8 + rng.normal(0, .25, n) * np.exp(-t * 40)) * _env(n, .002, .1) * .6
    return np.zeros(10)


def write_wav(path, x):
    x = np.clip(x, -1, 1)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((x * 32767).astype("<i2").tobytes())


def shot_sfx(cues, dur, path):
    """cues: [(time, name)] -> wav of length dur."""
    out = np.zeros(int(SR * dur) + SR)
    for t, name in cues:
        s = sfx(name)
        i = int(t * SR)
        if i < len(out):
            seg = s[: len(out) - i]
            out[i:i + len(seg)] += seg
    write_wav(path, out[: int(SR * dur)])


def music(seconds, path, seed=5):
    """Gentle looping pad + soft arpeggio. Intentionally quiet and neutral."""
    rng = np.random.default_rng(seed)
    n = int(SR * seconds)
    t = np.arange(n) / SR
    chords = [(261.63, 329.63, 392.0), (220.0, 261.63, 329.63), (174.61, 220.0, 261.63), (196.0, 246.94, 293.66)]
    bar = 4.0
    out = np.zeros(n)
    for b in range(int(seconds / bar) + 1):
        ch = chords[b % 4]
        i0, i1 = int(b * bar * SR), min(n, int((b + 1) * bar * SR))
        if i0 >= n:
            break
        tt = (np.arange(i1 - i0)) / SR
        env = np.minimum(1, tt / .8) * np.minimum(1, (bar - tt) / .8)
        pad = sum(np.sin(2 * np.pi * f * (np.arange(i0, i1) / SR)) + .3 * np.sin(2 * np.pi * f * 2 * (np.arange(i0, i1) / SR)) for f in ch) / 3
        out[i0:i1] += pad * env * .5
        # arpeggio, 8th notes
        step = bar / 8
        for k in range(8):
            f = ch[k % 3] * (2 if k % 2 else 1)
            j0 = int((b * bar + k * step) * SR)
            if j0 >= n:
                break
            m = min(int(step * SR * 1.6), n - j0)
            tk = np.arange(m) / SR
            note = np.sin(2 * np.pi * f * 2 * tk) * np.exp(-tk * 5) * np.minimum(1, tk / .005)
            out[j0:j0 + m] += note * .22
    out /= (np.abs(out).max() + 1e-9)
    fade = int(SR * 2)
    out[:fade] *= np.linspace(0, 1, fade)
    out[-fade:] *= np.linspace(1, 0, fade)
    write_wav(path, out * .8)
