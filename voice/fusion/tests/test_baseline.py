
from voice.contracts import Turn, VoiceFeatures
from voice.fusion.baseline import compute_baseline, compute_deltas


def make_voice(role="user", **overrides):
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
        role=role,
        audio_path="test.wav",
        duration_s=1.0,
        extractor="test",
        version="1.0",
        features=features,
    )


def make_turn(voice):
    return Turn(index=0, role="user", text="hello", voice=voice)


def test_baseline_requires_two_prior_user_turns():
    first = make_turn(make_voice())
    triggering = make_turn(make_voice(f0_mean_hz=300.0))

    assert compute_baseline([first, triggering]) is None


def test_baseline_uses_median_and_excludes_triggering_turn():
    first = make_turn(make_voice(f0_mean_hz=100.0))
    second = make_turn(make_voice(f0_mean_hz=300.0))
    triggering = make_turn(make_voice(f0_mean_hz=999.0))

    baseline = compute_baseline([first, second, triggering])

    assert baseline is not None
    assert baseline["f0_mean_hz"] == 200.0


def test_baseline_ignores_non_user_turns():
    first = make_turn(make_voice(f0_mean_hz=100.0))
    second = make_turn(make_voice(f0_mean_hz=300.0))
    assistant = Turn(index=2, role="assistant", text="hello")
    triggering = make_turn(make_voice())

    baseline = compute_baseline(
        [first, assistant, second, triggering]
    )

    assert baseline is not None
    assert baseline["f0_mean_hz"] == 200.0


def test_deltas_relative_and_absolute():
    voice = make_voice(f0_mean_hz=250.0, pause_count=5.0)
    baseline = {
        "f0_mean_hz": 200.0,
        "pause_count": 2.0,
    }

    deltas = compute_deltas(voice, baseline)

    assert deltas["f0_mean_hz"] == 0.25
    assert deltas["pause_count"] == 3.0


def test_deltas_return_none_for_missing_or_zero_baseline():
    voice = make_voice(f0_mean_hz=250.0)
    baseline = {
        "f0_mean_hz": 0.0,
        "rms_mean": 0.1,
    }
    voice.features["rms_mean"] = None

    deltas = compute_deltas(voice, baseline)

    assert deltas["f0_mean_hz"] is None
    assert deltas["rms_mean"] is None
