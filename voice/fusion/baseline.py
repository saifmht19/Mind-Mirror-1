"""Per-user voice baseline and relative feature deltas."""

from __future__ import annotations

from statistics import median
from typing import Optional, Sequence

from voice.contracts import Turn, VoiceFeatures


RELATIVE_FEATURES = (
    "f0_mean_hz",
    "f0_std_hz",
    "f0_range_hz",
    "rms_mean",
    "rms_std",
    "speech_rate_wps",
    "articulation_rate_wps",
    "mean_pause_s",
)

ABSOLUTE_FEATURES = (
    "pause_count",
    "pause_ratio",
    "voiced_ratio",
    "jitter_local",
    "shimmer_local",
)


def compute_baseline(
    history: Sequence[Turn],
) -> Optional[dict[str, float]]:
    """Calculate per-feature medians from earlier user turns."""

    samples: list[VoiceFeatures] = []

    # Exclude the triggering user turn (history[-1]).
    for turn in history[:-1]:
        voice = turn.voice

        if voice is None or voice.role != "user":
            continue

        if all(value is None for value in voice.features.values()):
            continue

        samples.append(voice)

    if len(samples) < 2:
        return None

    baseline: dict[str, float] = {}

    for feature_name in RELATIVE_FEATURES + ABSOLUTE_FEATURES:
        values = [
            voice.features[feature_name]
            for voice in samples
            if voice.features[feature_name] is not None
        ]

        if values:
            baseline[feature_name] = float(median(values))

    return baseline


def compute_deltas(
    voice: VoiceFeatures,
    baseline: dict[str, float],
) -> dict[str, Optional[float]]:
    """Calculate relative or absolute changes from the baseline."""

    deltas: dict[str, Optional[float]] = {}

    for feature_name in RELATIVE_FEATURES:
        current = voice.features[feature_name]
        base = baseline.get(feature_name)

        if current is None or base is None or base <= 1e-6:
            deltas[feature_name] = None
        else:
            deltas[feature_name] = (current - base) / base

    for feature_name in ABSOLUTE_FEATURES:
        current = voice.features[feature_name]
        base = baseline.get(feature_name)

        if current is None or base is None:
            deltas[feature_name] = None
        else:
            deltas[feature_name] = current - base

    return deltas