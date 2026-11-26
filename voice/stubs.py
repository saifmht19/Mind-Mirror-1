"""
voice/stubs.py -- Integrator-owned. Deterministic fake implementations of every Protocol.

Purpose: every teammate can run the WHOLE pipeline on day one, before any real module exists.
Stubs need no models, no network, no ffmpeg. They are also the behavioural reference for the
conformance tests (voice/tests/conformance.py).
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Iterator, Optional, Sequence

from .config import FLAG_THRESHOLD, TTS_SAMPLE_RATE, USER_SAMPLE_RATE
from .contracts import (Detector, DetectorName, Segment, SynthesisError, TTSResult, Turn,
                        TurnScore, Utterance, VOICE_FEATURE_NAMES, VoiceFeatures, VoiceRole)
from .tests.fixtures import synth_speechlike, synth_tone, wav_info

_PRESSURE_WORDS = ("you must", "hurry", "only i", "nobody else", "or else", "you owe me", "if you really")


class StubSpeechInput:
    def normalize(self, src_path: str, out_path: str) -> str:
        # Stub ignores the real content: always emits a valid canonical 3 s clip.
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        return synth_speechlike(out_path, sample_rate=USER_SAMPLE_RATE)

    def transcribe(self, audio_path: str) -> Utterance:
        info = wav_info(audio_path)
        words = ["this", "is", "a", "stub", "transcript"]
        step = info["duration_s"] / (len(words) + 1)
        segs = [Segment(start_s=round(step * (i + 0.5), 3), end_s=round(step * (i + 1.2), 3), text=w)
                for i, w in enumerate(words)]
        return Utterance(audio_path=audio_path, sample_rate=info["sample_rate"],
                         duration_s=info["duration_s"], transcript=" ".join(words),
                         language="en", segments=segs, asr_model="stub", asr_confidence=0.9)


class StubSynthesizer:
    _SENT = re.compile(r"(?<=[.!?])\s+")

    def synthesize(self, text: str, out_path: str, *, voice: Optional[str] = None,
                   speed: float = 1.0) -> TTSResult:
        if not text.strip():
            raise SynthesisError("empty text")
        dur = max(0.3, 0.06 * len(text) / speed)
        synth_tone(out_path, dur, sample_rate=TTS_SAMPLE_RATE)
        return TTSResult(audio_path=out_path, duration_s=dur, text=text, voice=voice or "stub", engine="stub")

    def synthesize_stream(self, text: str, out_dir: str, *, voice: Optional[str] = None,
                          speed: float = 1.0) -> Iterator[TTSResult]:
        sentences = [s for s in self._SENT.split(text.strip()) if s]
        if not sentences:
            raise SynthesisError("empty text")
        for i, s in enumerate(sentences):
            yield self.synthesize(s, str(Path(out_dir) / f"chunk_{i:04d}.wav"), voice=voice, speed=speed)


class StubFeatureExtractor:
    def extract(self, audio_path: str, segments: Optional[Sequence[Segment]] = None, *,
                role: VoiceRole = "user") -> VoiceFeatures:
        info = wav_info(audio_path)
        values = {k: 0.1 for k in VOICE_FEATURE_NAMES}
        values.update(f0_mean_hz=150.0, f0_std_hz=20.0, f0_range_hz=60.0, pause_count=2.0,
                      pause_ratio=0.29, mean_pause_s=0.35, speech_rate_wps=2.0)
        return VoiceFeatures(role=role, audio_path=audio_path, duration_s=info["duration_s"],
                             features=values, extractor="stub", version="0")


class StubDetector:
    def __init__(self, name: DetectorName = "context_voice") -> None:
        self.name = name

    def analyze(self, history: Sequence[Turn], turn: Turn, voice: Optional[VoiceFeatures] = None) -> TurnScore:
        hits = [w for w in _PRESSURE_WORDS if w in turn.text.lower()]
        score = 0.8 if hits else 0.1
        return TurnScore(detector=self.name, manipulation_score=score, flagged=score >= FLAG_THRESHOLD,
                         tactics=["pressure"] if hits else [], pressure=3 if hits else 0,
                         user_refusal=None, evidence=hits, running_risk=score,
                         explanation="stub keyword rule", used_voice=(voice is not None and self.name == "context_voice"),
                         latency_ms=1.0)


class StubReplyGenerator:
    def generate(self, history: Sequence[Turn]) -> str:
        last_user = next((t.text for t in reversed(history) if t.role == "user"), "")
        return f"Stub reply. You said: {last_user}"
