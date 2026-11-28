
from voice.contracts import Turn, TurnScore, VoiceFeatures
from voice.fusion.detector import ContextVoiceDetector


class FakeContextDetector:
    name = "context"

    def __init__(self):
        self.received_notes = None
        self.call_count = 0

    def analyze(self, history, turn, voice=None, *, notes=None):
        self.call_count += 1
        self.received_notes = notes

        return TurnScore(
            detector="context",
            used_voice=False,
            explanation="Context analysis completed.",
            tactics=[],
            pressure=0.0,
            manipulation_score=0.0,
            user_refusal=False,
            flagged=False,
            evidence=[],
            running_risk=0.0,
            raw={},
        )


def make_voice(**overrides):
    features = {
        "f0_mean_hz": 200.0,
        "f0_std_hz": 20.0,
        "f0_range_hz": 100.0,
        "rms_mean": 0.1,
        "rms_std": 0.02,
        "speech_rate_wps": 3.0,
        "articulation_rate_wps": 4.0,
        "pause_count": 2.0,
        "pause_ratio": 0.1,
        "mean_pause_s": 0.5,
        "voiced_ratio": 0.8,
        "jitter_local": 0.01,
        "shimmer_local": 0.02,
    }
    features.update(overrides)

    return VoiceFeatures(
        role="user",
        audio_path="test.wav",
        duration_s=1.0,
        extractor="test",
        version="1.0",
        features=features,
    )


def make_turn(index, voice=None):
    return Turn(
        index=index,
        role="user",
        text="I understand.",
        voice=voice,
    )


def test_detector_without_voice_does_not_send_notes():
    context = FakeContextDetector()
    detector = ContextVoiceDetector(context)

    turn = make_turn(0)
    result = detector.analyze([], turn, None)

    assert context.call_count == 1
    assert context.received_notes is None
    assert result.detector == "context_voice"
    assert result.used_voice is False


def test_detector_sends_voice_notes_when_baseline_exists():
    context = FakeContextDetector()
    detector = ContextVoiceDetector(context)

    first = make_turn(0, make_voice())
    second = make_turn(1, make_voice())
    triggering = make_turn(2, make_voice(speech_rate_wps=2.0))

    result = detector.analyze(
        [first, second, triggering],
        triggering,
        triggering.voice,
    )

    assert context.call_count == 1
    assert context.received_notes is not None
    assert "speech rate down 33%" in context.received_notes
    assert result.detector == "context_voice"
    assert result.used_voice is True


def test_detector_does_not_claim_voice_when_no_baseline_exists():
    context = FakeContextDetector()
    detector = ContextVoiceDetector(context)

    triggering = make_turn(0, make_voice())

    result = detector.analyze(
        [triggering],
        triggering,
        triggering.voice,
    )

    assert context.received_notes is None
    assert result.used_voice is False
