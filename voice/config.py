"""
voice/config.py -- shared constants, paths and env-var switches. Integrator-owned.
Other modules READ from here; they do not define their own copies of these values.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

try:  # the existing backend keeps secrets/settings in .env; load it if python-dotenv is present
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # pragma: no cover
    pass
from typing import Literal

from .contracts import TTS_SAMPLE_RATE, USER_SAMPLE_RATE  # re-exported for convenience

__all__ = ["USER_SAMPLE_RATE", "TTS_SAMPLE_RATE"]

# ---- paths ----------------------------------------------------------------------------------
def _flag(name: str, default: bool) -> bool:
    return os.getenv(name, "1" if default else "0").strip().lower() in ("1", "true", "yes", "on")


# NOTE: the repo already uses data/ for datasets, so runtime files live in a separate, git-ignored dir.
DATA_DIR = Path(os.getenv("VOICE_DATA_DIR", ".voice_runtime"))

# ---- privacy defaults (the project states that no conversation history is stored on the server) ----
PERSIST_SESSIONS = _flag("VOICE_PERSIST", False)        # True => append TurnResults to JSONL on disk
KEEP_USER_AUDIO = _flag("VOICE_KEEP_USER_AUDIO", False)  # False => delete user WAV after analysis
AUDIO_TTL_S = int(os.getenv("VOICE_AUDIO_TTL_S", "900"))  # delete TTS files / idle sessions after this long
DETECT_WAIT_MS = int(os.getenv("VOICE_DETECT_WAIT_MS", "1500"))  # how long a turn waits for the detector before returning "pending"
_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


def session_dir(session_id: str) -> Path:
    if not _SESSION_ID_RE.match(session_id):
        raise ValueError(f"invalid session_id: {session_id!r}")
    return DATA_DIR / session_id


def user_audio_path(session_id: str, turn_index: int) -> Path:
    return session_dir(session_id) / f"turn{turn_index:04d}_user.wav"


def tts_audio_path(session_id: str, turn_index: int) -> Path:
    return session_dir(session_id) / f"turn{turn_index:04d}_assistant.wav"


def tts_chunk_dir(session_id: str, turn_index: int) -> Path:
    return session_dir(session_id) / f"turn{turn_index:04d}_assistant_chunks"


# ---- shared numeric constants -----------------------------------------------------------------
PAUSE_MIN_S = 0.25            # a silent gap inside speech counts as a pause if >= this
MAX_UTTERANCE_S = 60.0        # reject longer user audio (AudioFormatError)
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
TTS_SENTENCE_GAP_S = 0.15     # silence inserted between sentences when concatenating
FLAG_THRESHOLD = float(os.getenv("MINDMIRROR_FLAG_THRESHOLD", "0.5"))

# ---- model settings (read by the owning module only) ------------------------------------------
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cpu")             # cpu | cuda
WHISPER_COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
KOKORO_VOICE = os.getenv("KOKORO_VOICE", "af_heart")
KOKORO_LANG_CODE = os.getenv("KOKORO_LANG_CODE", "a")           # "a" = American English

# ---- implementation switches --------------------------------------------------------------------
Impl = Literal["stub", "real"]
_KINDS = ("input", "output", "features", "detector", "generator")


def impl_choice(kind: str) -> Impl:
    """VOICE_IMPL_INPUT / _OUTPUT / _FEATURES / _DETECTOR / _GENERATOR = stub | real (default stub)."""
    if kind not in _KINDS:
        raise ValueError(f"unknown kind {kind!r}; expected one of {_KINDS}")
    value = os.getenv(f"VOICE_IMPL_{kind.upper()}", "stub").strip().lower()
    if value not in ("stub", "real"):
        raise ValueError(f"VOICE_IMPL_{kind.upper()} must be 'stub' or 'real', got {value!r}")
    return value  # type: ignore[return-value]


def detector_choice() -> str:
    """MINDMIRROR_DETECTOR = text | context | context_voice (default context_voice)."""
    value = os.getenv("MINDMIRROR_DETECTOR", "context_voice").strip().lower()
    if value not in ("text", "context", "context_voice"):
        raise ValueError(f"MINDMIRROR_DETECTOR invalid: {value!r}")
    return value
