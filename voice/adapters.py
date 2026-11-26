"""
voice/adapters.py -- INTEGRATOR-OWNED. Wraps the EXISTING MindMirror backend so it satisfies the
Protocols in contracts.py. This is the only file in voice/ that imports from `backend.*`.

What exists today (from the repo README): `backend/` is a FastAPI app with
  * a detector service (Gemini) that reads the visible conversation and returns, per turn, tactics from
    the six-tactic taxonomy, pressure 0-3, explicit refusals and exact evidence spans (invalid output is
    rejected and retried),
  * deterministic running-risk scoring that weights pressure following a refusal,
  * a simulator that talks to the local Ollama model "mindmirror-simulator" (the fictional assistant "Nova").
The detector judges a WHOLE conversation, so the per-turn adapters below send history + turn and keep only
the result for `turn` (the last assistant message). Never send audio or voice features to Gemini: only text.

Phase 0 TODO for the Integrator (see docs/06): fill the three builders below, then run
    VOICE_IMPL_GENERATOR=real VOICE_IMPL_DETECTOR=real MINDMIRROR_DETECTOR=context pytest voice -q
"""
from __future__ import annotations

from typing import Optional, Sequence

from .contracts import Detector, ReplyGenerator, Turn, TurnScore, VoiceFeatures


class OllamaReplyGenerator:
    """Wrap the existing simulator (Ollama, "Nova"). history[-1] is the new user turn.
    Reuse the backend's simulator module so scenarios/safety boundaries stay identical to the web demo."""

    def generate(self, history: Sequence[Turn]) -> str:
        # TODO(Integrator): convert `history` to the simulator's message format and call it
        # (import from backend.*). Return the assistant reply text only.
        raise NotImplementedError("Integrator: wrap the existing Ollama simulator here")


class GeminiTextDetector:
    """Existing single-turn detector (baseline 'text'). Ignores history and voice."""
    name = "text"

    def analyze(self, history: Sequence[Turn], turn: Turn,
                voice: Optional[VoiceFeatures] = None) -> TurnScore:
        # TODO(Integrator): run the existing detector on [turn] ONLY (no context) and map its output to
        # TurnScore(detector="text", used_voice=False, tactics/pressure/evidence/running_risk, raw=<native>).
        raise NotImplementedError("Integrator: wrap the existing text-only detector here")


class GeminiContextDetector:
    """Existing text+context detector. Returns TurnScore(detector="context", used_voice=False).

    INTEGRATION POINT IP-1 (required for Module 3):
    `notes` is an OPTIONAL extra block of text that, when not None, must be inserted into the
    Gemini prompt as a clearly delimited section (after the conversation, before the output
    instructions). When notes is None the prompt MUST be byte-identical to today's prompt.
    Module 3's fusion detector calls analyze(history, turn, None, notes=<voice text>).
    """
    name = "context"

    def analyze(self, history: Sequence[Turn], turn: Turn,
                voice: Optional[VoiceFeatures] = None, *, notes: Optional[str] = None) -> TurnScore:
        # TODO(Integrator): send list(history) + [turn] to the existing detector, take the result for the last
        # assistant turn, compute running_risk with the existing deterministic scorer, support `notes` (IP-1),
        # and map to TurnScore(detector="context", used_voice=False, raw=<native>).
        raise NotImplementedError("Integrator: wrap the existing context detector here")

    def build_prompt(self, history: Sequence[Turn], turn: Turn, notes: Optional[str] = None) -> str:
        """Return the exact prompt string that analyze() sends. Used by regression tests."""
        raise NotImplementedError("Integrator: expose the existing prompt builder here")


def build_generator() -> ReplyGenerator:
    return OllamaReplyGenerator()


def build_text_detector() -> Detector:
    return GeminiTextDetector()


def build_context_detector() -> GeminiContextDetector:
    return GeminiContextDetector()
