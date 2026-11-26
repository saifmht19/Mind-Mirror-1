"""
voice/tests/fixtures.py -- deterministic synthetic audio with KNOWN ground truth.
Pure standard library (no numpy) so it works everywhere, including the stubs.

synth_speechlike() makes a 3.0 s clip of harmonic tone bursts (f0 = 150 Hz) separated by silence:

    0.0-0.2  silence (leading, NOT a pause)
    0.2-0.8  burst 1
    0.8-1.1  silence  -> pause of 0.30 s
    1.1-1.7  burst 2
    1.7-2.1  silence  -> pause of 0.40 s
    2.1-2.6  burst 3
    2.6-3.0  silence (trailing, NOT a pause)

Ground truth is in SPEECHLIKE_TRUTH. Feature extractors are tested against it.
"""
from __future__ import annotations

import math
import struct
import wave
from pathlib import Path
from typing import Iterable, Sequence, Tuple

SPEECHLIKE_BURSTS: Tuple[Tuple[float, float], ...] = ((0.2, 0.8), (1.1, 1.7), (2.1, 2.6))
SPEECHLIKE_TRUTH = {
    "duration_s": 3.0,
    "f0_hz": 150.0,
    "pause_count": 2,
    "mean_pause_s": 0.35,
    "speech_span_s": 2.4,                 # first onset 0.2 -> last offset 2.6
    "pause_ratio": 0.7 / 2.4,             # (0.3 + 0.4) / 2.4
}


def write_wav(path: str | Path, samples: Sequence[float], sample_rate: int) -> str:
    """Write mono 16-bit PCM WAV from floats in [-1, 1]. Returns str(path)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = b"".join(struct.pack("<h", int(max(-1.0, min(1.0, s)) * 32767)) for s in samples)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(frames)
    return str(path)


def wav_info(path: str | Path) -> dict:
    with wave.open(str(path), "rb") as w:
        return {
            "channels": w.getnchannels(),
            "sample_width": w.getsampwidth(),
            "sample_rate": w.getframerate(),
            "duration_s": w.getnframes() / float(w.getframerate()),
        }


def _tone(t: float, f0: float) -> float:
    return sum(math.sin(2 * math.pi * h * f0 * t) / h for h in (1, 2, 3, 4)) / 2.08


def synth_speechlike(path: str | Path, *, sample_rate: int = 16_000, f0: float = 150.0,
                     bursts: Iterable[Tuple[float, float]] = SPEECHLIKE_BURSTS,
                     total_s: float = 3.0, amplitude: float = 0.3, fade_s: float = 0.01) -> str:
    bursts = list(bursts)
    n = int(total_s * sample_rate)
    samples = [0.0] * n
    for start, end in bursts:
        for i in range(int(start * sample_rate), min(n, int(end * sample_rate))):
            t = i / sample_rate
            edge = min(t - start, end - t)
            env = min(1.0, max(0.0, edge / fade_s))
            samples[i] = amplitude * env * _tone(t, f0)
    return write_wav(path, samples, sample_rate)


def synth_tone(path: str | Path, duration_s: float, *, sample_rate: int = 24_000,
               f0: float = 220.0, amplitude: float = 0.2) -> str:
    n = int(duration_s * sample_rate)
    return write_wav(path, [amplitude * math.sin(2 * math.pi * f0 * i / sample_rate) for i in range(n)],
                     sample_rate)
