"""The companion's own sounds, made in code: no sound file comes with the program.

The shop sells three more chimes (coin, bells, harp); every one is a few notes written
out below. `trophy` is the standard achievement chime: four quick rising notes on a soft pulse wave (an E major
arpeggio, the way an 8-bit console would play it) that land on a ringing fifth with a short
echo. It is written to a temporary WAV once and played without blocking. Playing works on
Windows (winsound, part of Python); elsewhere this module stays silent.
"""
import math
import os
import struct
import sys
import tempfile
import wave

RATE = 22050
_files = {}


def _tone(freq, secs, duty=0.25, decay=6.0, vol=1.0):
    """A pulse wave rounded off with its own sine, fading out."""
    out = []
    n = int(RATE * secs)
    for i in range(n):
        t = i / float(RATE)
        ph = (t * freq) % 1.0
        pulse = 1.0 if ph < duty else -1.0
        s = 0.45 * pulse + 0.55 * math.sin(2 * math.pi * freq * t)
        attack = min(1.0, i / (0.004 * RATE))
        out.append(vol * s * attack * math.exp(-decay * t))
    return out


def _mix(dst, src, at):
    start = int(at * RATE)
    if len(dst) < start + len(src):
        dst.extend([0.0] * (start + len(src) - len(dst)))
    for i, s in enumerate(src):
        dst[start + i] += s


def trophy_samples():
    E5, GS5, B5, E6, B6 = 659.26, 830.61, 987.77, 1318.51, 1975.53
    buf = []
    for i, f in enumerate((E5, GS5, B5, E6)):               # the run up
        _mix(buf, _tone(f, 0.16, decay=14.0, vol=0.55), 0.075 * i)
    _mix(buf, _tone(E6, 0.9, duty=0.5, decay=4.5, vol=0.5), 0.30)        # the landing: root and fifth
    _mix(buf, _tone(B6, 0.9, duty=0.5, decay=5.5, vol=0.32), 0.30)
    _mix(buf, _tone(B6, 0.5, duty=0.5, decay=7.0, vol=0.14), 0.52)       # a quiet echo
    _mix(buf, _tone(E6 * 2, 0.5, duty=0.5, decay=8.0, vol=0.10), 0.60)
    peak = max(abs(s) for s in buf) or 1.0
    return [s / peak * 0.6 for s in buf]


def _norm(buf):
    peak = max(abs(s) for s in buf) or 1.0
    return [s / peak * 0.6 for s in buf]


def coin_samples():
    """Two bright notes a fourth apart, the second one ringing: short, for players who earn a lot."""
    buf = []
    _mix(buf, _tone(987.77, 0.09, duty=0.5, decay=10.0, vol=0.6), 0.0)
    _mix(buf, _tone(1318.51, 0.75, duty=0.5, decay=5.0, vol=0.6), 0.085)
    return _norm(buf)


def bells_samples():
    """Three soft bells going up a major chord, each with a quiet octave above it."""
    buf = []
    for i, f in enumerate((783.99, 987.77, 1174.66)):
        _mix(buf, _tone(f, 1.1, duty=0.5, decay=3.2, vol=0.5), 0.2 * i)
        _mix(buf, _tone(f * 2, 0.6, duty=0.5, decay=6.0, vol=0.16), 0.2 * i)
    return _norm(buf)


def harp_samples():
    """A harp run: eight quick plucked notes up two octaves of a pentatonic scale."""
    buf = []
    for i, f in enumerate((523.25, 587.33, 659.26, 783.99, 880.0, 1046.5, 1174.66, 1318.51)):
        _mix(buf, _tone(f, 0.7, duty=0.5, decay=6.5, vol=0.5), 0.06 * i)
    return _norm(buf)


SOUNDS = {"trophy": trophy_samples, "coin": coin_samples, "bells": bells_samples, "harp": harp_samples}


def path(name):
    """The WAV of a sound, written on first use. None when it cannot be written."""
    if name not in _files:
        try:
            p = os.path.join(tempfile.gettempdir(), "retro_companion_%s.wav" % name)
            w = wave.open(p, "wb")
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(RATE)
            w.writeframes(b"".join(struct.pack("<h", int(max(-1.0, min(1.0, s)) * 32767)) for s in SOUNDS[name]()))
            w.close()
            _files[name] = p
        except (OSError, wave.Error):
            _files[name] = None
    return _files[name]


def play(name):
    """Play a sound without waiting for it. True when it was handed to the system."""
    if sys.platform != "win32":
        return False
    p = path(name if name in SOUNDS else "trophy")
    if not p:
        return False
    try:
        import winsound
        winsound.PlaySound(p, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
        return True
    except Exception:
        return False
