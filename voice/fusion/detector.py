"""Context detector enhanced with weak, relative voice cues."""

from __future__ import annotations

from typing import Optional, Sequence

from voice.contracts import (
    DetectionError,
    Detector,
    Turn,
    TurnScore,
    VoiceFeatures,
)
from voice.fusion.baseline import compute_baseline
from voice.fusion.render import render_voice_notes


class ContextVoiceDetector:
    """Wrap a context detector with optional voice-derived notes."""

    name = "context_voice"

    def __init__(self, context_detector: Detector) -> None:
        self._context_detector = context_detector

    def analyze(
        self,
        history: Sequence[Turn],
        turn: Turn,
        voice: Optional[VoiceFeatures] = None,
    ) -> TurnScore:
        """Analyze a turn, optionally adding relative voice cues."""

        try:
            if voice is None:
                score = self._context_detector.analyze(
                    history,
                    turn,
                    None,
                )
                return score.model_copy(
                    update={
                        "detector": "context_voice",
                        "used_voice": False,
                    }
                )

            baseline = compute_baseline(history)
            notes = render_voice_notes(voice, baseline)

            score = self._context_detector.analyze(
                history,
                turn,
                None,
                notes=notes,
            )

            explanation = score.explanation
            if notes is not None:
                explanation = (
                    f"{explanation} Voice cues were included as weak, "
                    "relative evidence."
                )

            return score.model_copy(
                update={
                    "detector": "context_voice",
                    "used_voice": notes is not None,
                    "explanation": explanation,
                }
            )

        except DetectionError:
            raise
        except Exception as exc:
            raise DetectionError(
                f"Context voice detection failed: {exc}"
            ) from exc