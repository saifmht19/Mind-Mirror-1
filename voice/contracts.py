"""
voice/contracts.py -- FROZEN SHARED CONTRACTS.

Every module (input, output, features, fusion, orchestrator) talks to the others
ONLY through the types and Protocols in this file. Nobody except the Integrator
edits it. If you think it is wrong or missing something, STOP and raise an issue
(see voice/docs/06_GIT_INTEGRATION_AND_TESTING.md, "Contract change process").

Changing anything here after Phase 0 requires approval from all four module owners.
"""
from __future__ import annotations

import math
import time
from typing import Any, Iterator, Literal, Optional, Protocol, Sequence, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, model_validator

CONTRACT_VERSION = "1.1.0"

# ---- audio format rules (see docs/01) -------------------------------------------------
USER_SAMPLE_RATE = 16_000   # canonical user audio: WAV, PCM 16-bit, mono, 16 kHz
TTS_SAMPLE_RATE = 24_000    # Kokoro output: WAV, PCM 16-bit, mono, 24 kHz

# ---- the fixed, ordered feature set. Keys of VoiceFeatures.features MUST equal this. ----
VOICE_FEATURE_NAMES: tuple[str, ...] = (
    "f0_mean_hz",             # mean fundamental frequency over voiced frames
    "f0_std_hz",              # std of f0 over voiced frames
    "f0_range_hz",            # p95(f0) - p5(f0) over voiced frames
    "rms_mean",               # mean RMS energy over speech frames (linear, 0..1 scale)
    "rms_std",                # std of RMS energy over speech frames
    "speech_rate_wps",        # words / (speech span seconds)           [needs segments]
    "articulation_rate_wps",  # words / (speech span - total pauses)    [needs segments]
    "pause_count",            # number of internal pauses >= PAUSE_MIN_S
    "pause_ratio",            # total internal pause time / speech span
    "mean_pause_s",           # mean duration of internal pauses
    "voiced_ratio",           # voiced frames / speech frames
    "jitter_local",           # local jitter (optional, may be None)
    "shimmer_local",          # local shimmer (optional, may be None)
)

VoiceRole = Literal["user", "ai", "dataset_speaker"]
DetectorName = Literal["text", "context", "context_voice"]


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


# ---- errors -----------------------------------------------------------------------------
class VoiceError(Exception):
    """Base class. Modules raise subclasses; the orchestrator catches and degrades."""


class AudioFormatError(VoiceError): ...
class TranscriptionError(VoiceError): ...
class SynthesisError(VoiceError): ...
class FeatureExtractionError(VoiceError): ...
class DetectionError(VoiceError): ...


# ---- data types -------------------------------------------------------------------------
class Segment(_Frozen):
    """A timed piece of transcript. Word-level when the ASR provides it. Times are seconds
    from the start of the canonical WAV file."""
    start_s: float = Field(ge=0)
    end_s: float = Field(ge=0)
    text: str

    @model_validator(mode="after")
    def _ordered(self) -> "Segment":
        if self.end_s < self.start_s:
            raise ValueError("Segment.end_s must be >= start_s")
        return self


class Utterance(_Frozen):
    """Output of speech input (Module 1). One spoken user message."""
    audio_path: str                     # canonical WAV (16 kHz mono 16-bit)
    sample_rate: int = USER_SAMPLE_RATE
    duration_s: float = Field(ge=0)
    transcript: str                     # "" is valid (no speech detected)
    language: Optional[str] = None      # e.g. "en"
    segments: list[Segment] = Field(default_factory=list)  # sorted by start_s
    asr_model: str                      # e.g. "faster-whisper:small"
    asr_confidence: Optional[float] = Field(default=None, ge=0, le=1)


class TTSResult(_Frozen):
    """Output of speech output (Module 2). One synthesized audio file."""
    audio_path: str                     # WAV 24 kHz mono 16-bit
    sample_rate: int = TTS_SAMPLE_RATE
    duration_s: float = Field(ge=0)
    text: str                           # the (cleaned) text that was spoken
    voice: str
    engine: str                         # e.g. "kokoro"


class VoiceFeatures(_Frozen):
    """Output of feature extraction (Module 3)."""
    role: VoiceRole = "user"
    audio_path: str
    duration_s: float = Field(ge=0)
    features: dict[str, Optional[float]]   # keys == VOICE_FEATURE_NAMES; None = unavailable
    extractor: str                         # e.g. "librosa-pyin"
    version: str                           # extractor version string

    @model_validator(mode="after")
    def _check_features(self) -> "VoiceFeatures":
        if set(self.features) != set(VOICE_FEATURE_NAMES):
            missing = set(VOICE_FEATURE_NAMES) - set(self.features)
            extra = set(self.features) - set(VOICE_FEATURE_NAMES)
            raise ValueError(f"features keys mismatch; missing={sorted(missing)} extra={sorted(extra)}")
        for k, v in self.features.items():
            if v is not None and not math.isfinite(v):
                raise ValueError(f"feature {k} must be finite or None (never NaN/inf)")
        return self


class TurnScore(_Frozen):
    """Output of a Detector for one assistant turn.

    Mirrors what the existing MindMirror detector produces (tactics from the six-tactic taxonomy,
    pressure 0-3, explicit refusals, evidence spans, running risk). `raw` carries the existing
    detector's native output unchanged so the UI/debugging never lose information.
    """
    detector: DetectorName
    manipulation_score: float = Field(ge=0.0, le=1.0)   # overall 0..1 score for this turn
    flagged: bool
    tactics: list[str] = Field(default_factory=list)     # labels from the project taxonomy
    pressure: Optional[int] = Field(default=None, ge=0, le=3)   # existing detector's pressure level
    user_refusal: Optional[bool] = None                  # explicit refusal in the user turn that triggered this reply
    evidence: list[str] = Field(default_factory=list)    # exact text spans cited for the tactics
    running_risk: Optional[float] = Field(default=None, ge=0.0)  # existing deterministic running-risk value
    explanation: str = ""
    used_voice: bool = False
    latency_ms: Optional[float] = Field(default=None, ge=0)
    raw: dict[str, Any] = Field(default_factory=dict)    # native detector output, JSON-serializable


class Turn(_Frozen):
    """One conversation turn. Immutable: use model_copy(update=...) to add score/voice."""
    index: int = Field(ge=0)
    role: Literal["user", "assistant"]
    text: str
    audio_path: Optional[str] = None
    voice: Optional[VoiceFeatures] = None   # only on user turns
    score: Optional[TurnScore] = None       # only on assistant turns
    created_at: float = Field(default_factory=time.time)


class TurnResult(_Frozen):
    """What the orchestrator returns for one full voice turn."""
    session_id: str
    user_turn: Turn
    assistant_turn: Turn                    # has .score filled in if detection succeeded
    tts: Optional[TTSResult] = None         # None if synthesis failed/disabled
    detection: Literal["done", "pending", "failed"] = "done"
    # "pending": reply + speech are ready but the detector (Gemini) is still running; the client
    # polls GET /api/voice/sessions/{id}/turns/{assistant_index} until it becomes done/failed.
    timings_ms: dict[str, float] = Field(default_factory=dict)
    # timing keys: normalize, asr, generate, features, tts, detect, total
    warnings: list[str] = Field(default_factory=list)    # degradations, e.g. "features_failed"
    impl: dict[str, str] = Field(default_factory=dict)   # which impl ran, e.g. {"input":"real"}


# ---- Protocols: what each module must implement -------------------------------------------
@runtime_checkable
class SpeechInput(Protocol):
    """Module 1."""
    def normalize(self, src_path: str, out_path: str) -> str:
        """Convert any audio file (webm/opus, m4a, mp3, wav, any rate/channels) to canonical
        WAV at out_path. Returns out_path. Raises AudioFormatError."""
        ...

    def transcribe(self, audio_path: str) -> Utterance:
        """Transcribe a canonical WAV. Raises TranscriptionError. No speech => transcript ""."""
        ...


@runtime_checkable
class Synthesizer(Protocol):
    """Module 2."""
    def synthesize(self, text: str, out_path: str, *, voice: Optional[str] = None,
                   speed: float = 1.0) -> TTSResult:
        """Speak the whole text into ONE wav at out_path. Raises SynthesisError."""
        ...

    def synthesize_stream(self, text: str, out_dir: str, *, voice: Optional[str] = None,
                          speed: float = 1.0) -> Iterator[TTSResult]:
        """Yield one TTSResult per sentence, in order, files named chunk_0000.wav, ... in out_dir."""
        ...


@runtime_checkable
class FeatureExtractor(Protocol):
    """Module 3a."""
    def extract(self, audio_path: str, segments: Optional[Sequence[Segment]] = None, *,
                role: VoiceRole = "user") -> VoiceFeatures:
        """Compute VoiceFeatures from a canonical WAV. Stateless. Raises FeatureExtractionError."""
        ...


@runtime_checkable
class Detector(Protocol):
    """Module 3b (context_voice) and the Integrator's adapters (text, context).

    analyze() semantics (IMPORTANT):
      turn    = the ASSISTANT turn being judged (role == "assistant").
      history = every turn BEFORE `turn`, oldest first. Its last element is the user turn that
                triggered `turn`, and that user Turn's .voice holds its VoiceFeatures (or None).
      voice   = VoiceFeatures of that triggering user turn (same object as history[-1].voice) or None.
    Must not mutate its inputs. With voice=None every detector must behave exactly like the
    existing text+context system.
    """
    name: DetectorName

    def analyze(self, history: Sequence[Turn], turn: Turn,
                voice: Optional[VoiceFeatures] = None) -> TurnScore: ...


@runtime_checkable
class ReplyGenerator(Protocol):
    """The existing Ollama generator, wrapped by the Integrator in voice/adapters.py."""
    def generate(self, history: Sequence[Turn]) -> str:
        """history's last element is the new user turn. Returns the assistant reply text."""
        ...
