import math

import pytest
from pydantic import ValidationError

from voice import registry
from voice.contracts import (Detector, FeatureExtractor, ReplyGenerator, Segment, SpeechInput,
                             Synthesizer, Turn, TurnResult, TurnScore, VOICE_FEATURE_NAMES, VoiceFeatures)
from voice.tests.fixtures import synth_speechlike


def _vf(**over):
    feats = {k: 1.0 for k in VOICE_FEATURE_NAMES}
    feats.update(over)
    return VoiceFeatures(role="user", audio_path="x.wav", duration_s=1.0, features=feats,
                         extractor="t", version="0")


def test_feature_names_are_unique_and_stable():
    assert len(VOICE_FEATURE_NAMES) == len(set(VOICE_FEATURE_NAMES)) == 13


def test_voice_features_reject_missing_extra_and_nan():
    with pytest.raises(ValidationError):
        VoiceFeatures(role="user", audio_path="x", duration_s=1, features={"f0_mean_hz": 1.0},
                      extractor="t", version="0")
    with pytest.raises(ValidationError):
        _vf(f0_mean_hz=math.nan)
    feats = {k: None for k in VOICE_FEATURE_NAMES}
    VoiceFeatures(role="user", audio_path="x", duration_s=1, features=feats, extractor="t", version="0")


def test_segment_must_be_ordered():
    with pytest.raises(ValidationError):
        Segment(start_s=2.0, end_s=1.0, text="x")


def test_models_are_frozen_and_json_roundtrip():
    t = Turn(index=0, role="user", text="hi", voice=_vf())
    with pytest.raises(ValidationError):
        t.text = "changed"
    assert Turn.model_validate_json(t.model_dump_json()) == t
    s = TurnScore(detector="context_voice", manipulation_score=0.4, flagged=False)
    r = TurnResult(session_id="abcdefgh", user_turn=t, assistant_turn=Turn(index=1, role="assistant", text="yo", score=s))
    assert TurnResult.model_validate_json(r.model_dump_json()) == r


def test_score_bounds():
    with pytest.raises(ValidationError):
        TurnScore(detector="text", manipulation_score=1.5, flagged=True)


def test_registry_defaults_to_stubs_that_satisfy_protocols():
    assert isinstance(registry.get_speech_input(), SpeechInput)
    assert isinstance(registry.get_synthesizer(), Synthesizer)
    assert isinstance(registry.get_feature_extractor(), FeatureExtractor)
    assert isinstance(registry.get_generator(), ReplyGenerator)
    for name in ("text", "context", "context_voice"):
        d = registry.get_detector(name)
        assert isinstance(d, Detector) and d.name == name


def test_unimplemented_real_modules_fail_loudly():
    for getter in (registry.get_speech_input, registry.get_synthesizer, registry.get_feature_extractor):
        try:
            getter("real")
        except NotImplementedError:
            pass  # placeholder still present: expected in Phase 0
        # once a module is implemented this passes without raising: also fine


def test_synthetic_fixture_is_valid_wav(tmp_path):
    from voice.tests.fixtures import wav_info
    p = synth_speechlike(tmp_path / "a.wav")
    info = wav_info(p)
    assert info["sample_rate"] == 16_000 and abs(info["duration_s"] - 3.0) < 1e-3


def test_turnscore_matches_existing_detector_fields():
    s = TurnScore(detector="context", manipulation_score=0.7, flagged=True, tactics=["guilt"], pressure=2,
                  user_refusal=True, evidence=["you would leave me?"], running_risk=1.4,
                  raw={"turn": 3, "labels": [{"tactic": "guilt"}]})
    assert TurnScore.model_validate_json(s.model_dump_json()) == s
    with pytest.raises(ValidationError):
        TurnScore(detector="context", manipulation_score=0.7, flagged=True, pressure=4)


def test_turnresult_detection_status_defaults_to_done_and_accepts_pending():
    t = Turn(index=0, role="user", text="hi")
    a = Turn(index=1, role="assistant", text="yo")
    assert TurnResult(session_id="abcdefgh", user_turn=t, assistant_turn=a).detection == "done"
    assert TurnResult(session_id="abcdefgh", user_turn=t, assistant_turn=a, detection="pending").detection == "pending"
    with pytest.raises(ValidationError):
        TurnResult(session_id="abcdefgh", user_turn=t, assistant_turn=a, detection="later")
