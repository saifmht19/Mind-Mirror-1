"""Voice fusion module."""

from voice.adapters import build_context_detector
from voice.fusion.detector import ContextVoiceDetector


def build() -> ContextVoiceDetector:
    """Build the context detector enhanced with relative voice cues."""
    return ContextVoiceDetector(build_context_detector())
