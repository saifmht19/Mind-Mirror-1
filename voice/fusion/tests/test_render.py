
from voice.contracts import VoiceFeatures
from voice.fusion.render import render_voice_notes


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


def test_render_returns_none_without_baseline():
    voice = make_voice()

    assert render_voice_notes(voice, None) is None


def test_render_reports_one_significant_relative_change():
    voice = make_voice(speech_rate_wps=2.0)
    baseline = {"speech_rate_wps": 3.0}

    result = render_voice_notes(voice, baseline)

    assert result is not None
    assert "- speech rate down 33%" in result


def test_render_returns_none_when_no_change_passes_threshold():
    voice = make_voice(speech_rate_wps=3.2)
    baseline = {"speech_rate_wps": 3.0}

    assert render_voice_notes(voice, baseline) is None


def test_render_limits_output_to_three_cues():
    voice = make_voice(
        f0_mean_hz=300.0,
        f0_std_hz=30.0,
        f0_range_hz=150.0,
        rms_mean=0.2,
    )
    baseline = {
        "f0_mean_hz": 200.0,
        "f0_std_hz": 20.0,
        "f0_range_hz": 100.0,
        "rms_mean": 0.1,
    }

    result = render_voice_notes(voice, baseline)

    assert result is not None
    cue_lines = [
        line for line in result.splitlines()
        if line.startswith("- ")
    ]
    assert len(cue_lines) == 3


def test_render_reports_pause_ratio_change():
    voice = make_voice(pause_ratio=0.25)
    baseline = {"pause_ratio": 0.10}

    result = render_voice_notes(voice, baseline)

    assert result is not None
    assert "pauses up (pause ratio 0.25 vs 0.10)" in result


def test_render_reports_pause_count_change():
    voice = make_voice(pause_count=5.0)
    baseline = {"pause_count": 2.0}

    result = render_voice_notes(voice, baseline)

    assert result is not None
    assert "more pauses (5 vs 2)" in result
