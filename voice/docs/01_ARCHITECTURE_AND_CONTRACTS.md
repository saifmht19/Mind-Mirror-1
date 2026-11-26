# 01 - Architecture and Contracts (everyone reads this)

## 1. Scope
Existing and **unchanged**: the text + context detector (Gemini) and the reply generator (Ollama).
New in this branch: speech input, speech output, voice features, voice-aware detector, a pipeline that
runs it all, an API, and a small web UI. The text-only and context-only detectors stay available as
ablation baselines (`text`, `context`); the new one is `context_voice`.

## 2. One voice turn, step by step
```
Browser mic -> POST /api/voice/sessions/{id}/turns/audio   (webm/opus blob)

 1. M1 normalize(src, out)            -> canonical user WAV (16 kHz mono 16-bit)
 2. M1 transcribe(wav)                -> Utterance (transcript + word timings)
        empty transcript => stop, return error "no_speech" (nothing is stored)
 3. IN PARALLEL
      a. generator.generate(history)  -> reply text            (existing Ollama, via adapters.py)
      b. M3 extractor.extract(wav, utt.segments, role="user") -> VoiceFeatures   (failure => voice=None)
 4. IN PARALLEL
      a. M2 synthesizer.synthesize(reply) -> TTSResult         (failure => tts=None)
      b. detector.analyze(history, ai_turn, voice) -> TurnScore (failure => score=None)
         The turn returns when speech is ready and the detector has answered, or after
         DETECT_WAIT_MS with detection="pending" (client polls). Detection never blocks speech.
 5. Keep both turns in the in-memory session (JSONL only if VOICE_PERSIST=1), delete the user's WAV
    (unless VOICE_KEEP_USER_AUDIO=1), return TurnResult (JSON) with timings and warnings.
```
Why steps 3 and 4 are parallel: feature extraction only needs the user audio, and detection only needs
the reply text, so neither should wait for the other or for speech synthesis. Gemini (with its retries) can be slower
than Kokoro, which is why the turn may return with `detection: "pending"`.

## 3. The contracts (all in `voice/contracts.py`)
| Type / Protocol | Produced by | Consumed by | Key invariants |
|---|---|---|---|
| `Segment` | M1 | M3, M4 | seconds from start of canonical WAV; `end >= start` |
| `Utterance` | M1 `transcribe` | M4, M3 (segments) | `sample_rate==16000`; `transcript==""` is valid; segments sorted by `start_s` |
| `TTSResult` | M2 | M4 | WAV 24 kHz mono 16-bit; `duration_s` equals real file duration |
| `VoiceFeatures` | M3 `extract` | M3 fusion, M4 | `features` keys **exactly** `VOICE_FEATURE_NAMES`; values finite float or `None` (never NaN) |
| `TurnScore` | any Detector | M4, eval, UI | mirrors the existing detector: `tactics`, `pressure` 0-3, `user_refusal`, `evidence` (exact spans), `running_risk`, plus `manipulation_score` in [0,1] and `raw` (native output, untouched); `detector` in {text, context, context_voice}; `used_voice` honest |
| `Turn` | M4 | all | immutable; user turns carry `.voice`, assistant turns carry `.score` |
| `TurnResult` | M4 | API/UI | `timings_ms` keys: `normalize asr generate features tts detect total`; `detection` in {done, pending, failed} |
| `SpeechInput` | M1 | M4 | `normalize()`, `transcribe()` |
| `Synthesizer` | M2 | M4 | `synthesize()`, `synthesize_stream()` |
| `FeatureExtractor` | M3 | M4, eval | stateless, deterministic |
| `Detector` | adapters + M3 | M4, eval | see section 5 |
| `ReplyGenerator` | adapters | M4 | `generate(history)`; last element of history is the new user turn |

All models are **frozen** pydantic v2 objects with `extra="forbid"`. To change one use `turn.model_copy(update={...})`.
JSON round-trip (`model_dump_json` / `model_validate_json`) is tested; keep your types serializable.

## 4. Audio formats (non-negotiable)
| Audio | Format |
|---|---|
| User audio after `normalize` (input to ASR and features) | WAV, PCM 16-bit, **mono**, **16 000 Hz** |
| TTS audio | WAV, PCM 16-bit, mono, **24 000 Hz** |
| Max user utterance | `config.MAX_UTTERANCE_S` (60 s); longer => `AudioFormatError` |
| File locations | `config.user_audio_path(session, turn)`, `config.tts_audio_path(...)`. Modules write only where told (`out_path` / `out_dir`) |

## 5. Detector semantics (read twice)
`analyze(history, turn, voice=None)`:
- `turn` is the **assistant** turn being judged. The AI is the potential manipulator.
- `history` holds every turn **before** `turn`, oldest first. `history[-1]` is the user turn that triggered it and its `.voice` holds that turn's `VoiceFeatures` (or `None`).
- `voice` is that same `VoiceFeatures` (or `None`) passed explicitly for convenience.
- Never mutate arguments. With `voice=None` the output must equal the existing text+context system.
- `used_voice=True` only if voice information actually reached the model (changed the prompt).

### What "voice" means here (decision D1)
Live pipeline: `voice.role == "user"`. It is the **user's reaction signal**, compared against that user's own
earlier turns in the same session (never against absolute numbers: pitch and loudness vary per person and per microphone).
The synthetic AI voice is not analyzed. Evaluation on speech datasets uses `role == "dataset_speaker"`
(the manipulator's own speech). Those two are different experiments: **never pool them in one results table.**

## 6. Failure policy (the orchestrator implements this; modules just raise the right exception)
| Failure | Module raises | User-visible result | `warnings` key |
|---|---|---|---|
| Unreadable / too long audio | `AudioFormatError` | HTTP 422 `bad_audio` | - |
| ASR crashes | `TranscriptionError` | HTTP 502 `asr_failed` | - |
| No speech detected | (returns `""`) | HTTP 422 `no_speech`, nothing stored | - |
| Generator crashes | any | HTTP 502 `generator_failed`, nothing stored | - |
| Feature extraction fails | `FeatureExtractionError` | turn continues with `voice=None` | `features_failed` |
| TTS fails | `SynthesisError` | `tts=null`, text still returned | `tts_failed` |
| Detector fails | `DetectionError` | `score=null`, `detection="failed"` | `detector_failed` |
| Detector slower than `DETECT_WAIT_MS` | - | `score=null`, `detection="pending"`; the client polls `GET /api/voice/sessions/{id}/turns/{n}` | - |

Rule of thumb: voice problems must **never** break the text conversation.

## 7. Concurrency rules
- Calls come from `asyncio.to_thread`; two sessions can call you at once. Load models once, behind a lock; don't keep per-session state.
- CPU-heavy work (Whisper, Kokoro, pyin) is limited by a semaphore in the orchestrator; you don't manage that.
- No blocking `input()`, no GUI, no global `sd.default` mutation outside CLIs.

## 8. Configuration
All env vars are listed in `voice/.env.example` (append them to the repo's `.env.example`) and read through `voice/config.py`, which also loads `.env`. Everything defaults to **stub**.
`VOICE_IMPL_<KIND>=real` switches a single component; `MINDMIRROR_DETECTOR` picks `text | context | context_voice`.
Components are always obtained from `voice/registry.py` - never import an implementation directly in another module.

## 9. Integration points that need the Integrator
- **IP-1** `GeminiContextDetector.analyze(..., notes=...)` in `adapters.py`: optional text block inserted into the Gemini prompt; `notes=None` must leave the prompt byte-identical. Module 3 depends on it.
- **IP-2** `GeminiContextDetector.build_prompt(...)`: returns the exact prompt string; used by regression tests.
- **IP-3** `adapters.build_generator()`: wraps the existing simulator (Ollama model `mindmirror-simulator`, "Nova") so the voice demo uses the same scenarios and safety boundaries as the web demo.
- **IP-4** `adapters` must map the existing detector output (tactics, pressure, refusals, evidence spans) and the existing running-risk scorer into `TurnScore`, keeping the native output in `raw`. The detector judges a whole conversation: send `history + [turn]`, keep the result for `turn`.

## 10. Versioning
`CONTRACT_VERSION` (currently 1.1.0). `/api/voice/health` reports it. Any contract change bumps it and updates stubs, tests, docs in one PR (see doc 06).

## 11. Privacy rules (apply to every module)
The project states that no conversation history is stored on the server and that conversations reach the detection service only when analysed.
- Whisper, Kokoro and feature extraction run locally. **Gemini receives text only** (transcript + the optional cue block), never audio or raw features.
- Defaults: sessions in memory with a TTL; user WAV deleted right after feature extraction; TTS files expire; no JSONL (`VOICE_PERSIST=0`, `VOICE_KEEP_USER_AUDIO=0`).
- Voice recordings are personal data. Never commit recordings, never log audio, log transcripts only at DEBUG.
- Runtime files live in `.voice_runtime/` (git-ignored), never in the repo's `data/` folder.
