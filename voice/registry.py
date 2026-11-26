"""
voice/registry.py -- the ONLY place that decides stub vs real. Integrator-owned.

The orchestrator and the tests obtain every component through these getters, so swapping a
stub for a real module is an environment-variable change, never a code change.
"""
from __future__ import annotations

import importlib
from typing import Callable, Optional

from .config import detector_choice, impl_choice
from .contracts import Detector, FeatureExtractor, ReplyGenerator, SpeechInput, Synthesizer

_TABLE = {
    "input":     {"stub": "voice.stubs:StubSpeechInput",       "real": "voice.input:build"},
    "output":    {"stub": "voice.stubs:StubSynthesizer",       "real": "voice.output:build"},
    "features":  {"stub": "voice.stubs:StubFeatureExtractor",  "real": "voice.features:build"},
    "generator": {"stub": "voice.stubs:StubReplyGenerator",    "real": "voice.adapters:build_generator"},
}
_DETECTOR_REAL = {
    "text":          "voice.adapters:build_text_detector",
    "context":       "voice.adapters:build_context_detector",
    "context_voice": "voice.fusion:build",
}


def _load(path: str) -> Callable:
    module_name, attr = path.split(":")
    return getattr(importlib.import_module(module_name), attr)


def get_speech_input(impl: Optional[str] = None) -> SpeechInput:
    return _load(_TABLE["input"][impl or impl_choice("input")])()


def get_synthesizer(impl: Optional[str] = None) -> Synthesizer:
    return _load(_TABLE["output"][impl or impl_choice("output")])()


def get_feature_extractor(impl: Optional[str] = None) -> FeatureExtractor:
    return _load(_TABLE["features"][impl or impl_choice("features")])()


def get_generator(impl: Optional[str] = None) -> ReplyGenerator:
    return _load(_TABLE["generator"][impl or impl_choice("generator")])()


def get_detector(name: Optional[str] = None, impl: Optional[str] = None) -> Detector:
    name = name or detector_choice()
    if (impl or impl_choice("detector")) == "stub":
        from .stubs import StubDetector
        return StubDetector(name=name)  # type: ignore[arg-type]
    return _load(_DETECTOR_REAL[name])()
