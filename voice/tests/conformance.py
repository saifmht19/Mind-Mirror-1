"""
voice/tests/conformance.py -- reusable checks that ANY implementation of a Protocol must pass.
Module owners run these against their real implementation (see test_conformance.py) and may add
stricter module-specific tests of their own. Real-model tests are gated by VOICE_TEST_REAL.
"""
from __future__ import annotations

from pathlib import Path

from voice.contracts import (Detector, FeatureExtractor, Segment, SpeechInput, Synthesizer, Turn,
                             Utterance, TTSResult, VOICE_FEATURE_NAMES, VoiceFeatures)
from .fixtures import SPEECHLIKE_TRUTH, synth_speechlike, wav_info


def check_speech_input(impl: SpeechInput, tmp: Path) -> None:
    assert isinstance(impl, SpeechInput)
    src = synth_speechlike(tmp / "src_44k.wav", sample_rate=44_100)       # non-canonical rate
    out = impl.normalize(src, str(tmp / "norm.wav"))
    assert Path(out).exists()
    info = wav_info(out)
    assert (info["channels"], info["sample_width"], info["sample_rate"]) == (1, 2, 16_000)
    assert abs(info["duration_s"] - 3.0) < 0.1
    utt = impl.transcribe(out)
    assert isinstance(utt, Utterance)
    assert utt.sample_rate == 16_000 and abs(utt.duration_s - info["duration_s"]) < 0.1
    assert isinstance(utt.transcript, str)
    starts = [s.start_s for s in utt.segments]
    assert starts == sorted(starts), "segments must be sorted by start_s"
    assert all(s.end_s <= utt.duration_s + 0.2 for s in utt.segments), "segment beyond end of audio"


def check_synthesizer(impl: Synthesizer, tmp: Path) -> None:
    assert isinstance(impl, Synthesizer)
    text = "Hello there. This is a test of the voice output."
    res = impl.synthesize(text, str(tmp / "one.wav"))
    assert isinstance(res, TTSResult) and Path(res.audio_path).exists()
    info = wav_info(res.audio_path)
    assert (info["channels"], info["sample_width"], info["sample_rate"]) == (1, 2, 24_000)
    assert res.duration_s > 0.3 and abs(res.duration_s - info["duration_s"]) < 0.1
    chunks = list(impl.synthesize_stream(text, str(tmp / "chunks")))
    assert len(chunks) >= 2, "two sentences must yield at least two chunks"
    assert all(Path(c.audio_path).exists() for c in chunks)


def check_feature_extractor(impl: FeatureExtractor, tmp: Path, *, strict: bool) -> None:
    assert isinstance(impl, FeatureExtractor)
    wav = synth_speechlike(tmp / "clip.wav")
    vf = impl.extract(wav, None, role="user")
    assert isinstance(vf, VoiceFeatures) and vf.role == "user"
    assert set(vf.features) == set(VOICE_FEATURE_NAMES)
    assert abs(vf.duration_s - 3.0) < 0.1
    again = impl.extract(wav, None, role="user")
    assert again.features == vf.features, "extract() must be deterministic"
    if strict:  # real implementations must recover the synthetic ground truth
        f = vf.features
        t = SPEECHLIKE_TRUTH
        assert f["f0_mean_hz"] is not None and abs(f["f0_mean_hz"] - t["f0_hz"]) / t["f0_hz"] < 0.10
        assert f["pause_count"] == t["pause_count"]
        assert f["mean_pause_s"] is not None and abs(f["mean_pause_s"] - t["mean_pause_s"]) < 0.08
        assert f["pause_ratio"] is not None and abs(f["pause_ratio"] - t["pause_ratio"]) < 0.06
        # no segments given -> word-based rates must be None, not guessed
        assert f["speech_rate_wps"] is None and f["articulation_rate_wps"] is None
        segs = [Segment(start_s=0.2, end_s=0.8, text="one two"), Segment(start_s=1.1, end_s=1.7, text="three four"),
                Segment(start_s=2.1, end_s=2.6, text="five six")]
        with_words = impl.extract(wav, segs, role="user").features
        assert with_words["speech_rate_wps"] is not None and abs(with_words["speech_rate_wps"] - 6 / 2.4) < 0.3


def check_detector(impl: Detector) -> None:
    assert isinstance(impl, Detector)
    assert impl.name in ("text", "context", "context_voice")
    u = Turn(index=0, role="user", text="I think I will go out tonight.")
    a = Turn(index=1, role="assistant", text="If you really cared about me you would stay home.")
    before = [t.model_dump() for t in (u,)]
    s = impl.analyze([u], a, None)
    assert 0.0 <= s.manipulation_score <= 1.0 and s.detector == impl.name
    assert s.used_voice is False, "used_voice must be False when voice=None"
    assert [t.model_dump() for t in (u,)] == before, "analyze() must not mutate history"
