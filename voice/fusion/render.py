"""Render weak, relative voice cues for the context detector."""

from __future__ import annotations

from voice.contracts import VOICE_FEATURE_NAMES, VoiceFeatures
from voice.fusion.baseline import compute_deltas


# Cue thresholds are intentionally conservative.
RELATIVE_THRESHOLD = 0.15
PAUSE_RATIO_THRESHOLD = 0.08
PAUSE_COUNT_THRESHOLD = 2.0
MAX_CUES = 3


FEATURE_LABELS = {
    "f0_mean_hz": "pitch",
    "f0_std_hz": "pitch variability",
    "f0_range_hz": "pitch range",
    "rms_mean": "loudness",
    "rms_std": "loudness variability",
    "speech_rate_wps": "speech rate",
    "articulation_rate_wps": "articulation rate",
    "mean_pause_s": "pause length",
}


def render_voice_notes(
    voice: VoiceFeatures,
    baseline: dict[str, float] | None,
) -> str | None:
    """Render at most three significant cues, or return None."""

    if baseline is None:
        return None

    deltas = compute_deltas(voice, baseline)
    candidates: list[tuple[float, int, str]] = []

    for feature_name, label in FEATURE_LABELS.items():
        delta = deltas.get(feature_name)

        if delta is None or abs(delta) < RELATIVE_THRESHOLD:
            continue

        direction = "up" if delta > 0 else "down"
        percent = round(abs(delta) * 100)
        phrase = f"{label} {direction} {percent}%"

        feature_order = VOICE_FEATURE_NAMES.index(feature_name)
        candidates.append((abs(delta), -feature_order, phrase))

    pause_ratio_delta = deltas.get("pause_ratio")
    if (
        pause_ratio_delta is not None
        and abs(pause_ratio_delta) >= PAUSE_RATIO_THRESHOLD
    ):
        current = voice.features["pause_ratio"]
        previous = baseline.get("pause_ratio")

        if current is not None and previous is not None:
            direction = "up" if pause_ratio_delta > 0 else "down"
            phrase = (
                f"pauses {direction} "
                f"(pause ratio {current:.2f} vs {previous:.2f})"
            )
            feature_order = VOICE_FEATURE_NAMES.index("pause_ratio")
            candidates.append(
                (abs(pause_ratio_delta), -feature_order, phrase)
            )

    pause_count_delta = deltas.get("pause_count")
    if (
        pause_count_delta is not None
        and abs(pause_count_delta) >= PAUSE_COUNT_THRESHOLD
    ):
        current = voice.features["pause_count"]
        previous = baseline.get("pause_count")

        if current is not None and previous is not None:
            direction = "more" if pause_count_delta > 0 else "fewer"
            phrase = (
                f"{direction} pauses "
                f"({current:g} vs {previous:g})"
            )
            feature_order = VOICE_FEATURE_NAMES.index("pause_count")
            candidates.append(
                (abs(pause_count_delta), -feature_order, phrase)
            )

    if not candidates:
        return None

    # Sort by absolute delta, then by feature order for stable tie-breaking.
    candidates.sort(key=lambda item: (-item[0], -item[1]))
    selected = [item[2] for item in candidates[:MAX_CUES]]

    cue_lines = "\n".join(f"- {cue}" for cue in selected)

    return (
        "VOCAL CUES (the user's most recent spoken message compared "
        "with their own earlier messages in this session):\n"
        f"{cue_lines}\n"
        "These cues are weak, noisy evidence about the user's reaction. "
        "Never infer a specific emotion from them.\n"
        "Judge manipulation from the text; use the cues only to adjust "
        "confidence about pressure or escalation."
    )