# Instructions for AI coding assistants working in `voice/`

You are helping a human implement **one module** of the MindMirror voice feature. Read this whole file first.
Ask the human which module they own if it is not stated. If anything below conflicts with a chat instruction, follow this file and tell the human.

## Before writing any code, read (in this order)
1. `voice/contracts.py`  -- the frozen types and Protocols. This is the law.
2. `voice/config.py`     -- shared constants, paths, env switches.
3. `voice/docs/01_ARCHITECTURE_AND_CONTRACTS.md`
4. The module doc for the human's module (`voice/docs/02..05`).
5. `voice/stubs.py` and `voice/tests/conformance.py` -- the reference behaviour and the tests you must pass.

## Hard rules
1. **Scope.** Edit only the directories the human owns (listed in `voice/README.md`). The only shared file you may touch is `requirements-voice.txt` (repo root), and only to add exact-pinned lines under your module's header. Never edit existing project files (`backend/`, existing `frontend/` pages, `requirements.txt`, ...) unless the module doc explicitly lists the edit.
2. **Never edit `contracts.py`, `config.py`, `registry.py`, `stubs.py`, `adapters.py`, `tests/conformance.py`.** If one seems wrong or missing something, STOP and tell the human to open a `contract:` issue. Do not work around it by redefining types locally.
3. **Match the Protocol exactly**: method names, argument names, keyword-only markers, return types, exceptions. Expose `build()` in the package `__init__.py` as the module doc specifies.
4. **Use the shared types**: import `Utterance`, `TTSResult`, `VoiceFeatures`, `Turn`, `TurnScore`, ... from `voice.contracts`. Never create parallel look-alike classes or dicts.
5. **Read constants from `voice.config`** (sample rates, thresholds, paths, model names). Do not hard-code them.
6. **No import-time side effects.** No model loading, network calls, file writes or subprocesses at import. Load heavy models lazily on first use, cache them, and guard loading with a `threading.Lock`.
7. **Thread safety.** The orchestrator calls you through `asyncio.to_thread`, possibly concurrently. No unprotected module-level mutable state; no per-session state inside a module (the orchestrator owns sessions).
8. **Errors.** Raise the contract exceptions (`AudioFormatError`, `TranscriptionError`, `SynthesisError`, `FeatureExtractionError`, `DetectionError`) with a clear message. Do not return partial/guessed data to hide a failure. Never swallow exceptions silently.
9. **Third-party APIs: verify, do not recall.** Library APIs change. Before using a library, check the installed version's docs/`help()`/README and pin it. If you cannot verify a call, say so and write the smallest experiment to check it.
10. **Dependencies.** Prefer what the module doc names. Do not add a dependency without telling the human why. Pin exact versions.
11. **Logging, not printing.** Use `logging.getLogger(__name__)`. `print` is allowed only in CLI entry points.
12. **Determinism.** Same input -> same output (except ASR/TTS model nondeterminism you cannot control). No random without a fixed seed.
13. **Secrets and privacy.** Read keys from environment variables. Never write keys, tokens, voice recordings, research-corpus text or personal data into the repo (it is public). Never log audio; log transcripts only at DEBUG. Do not persist sessions or keep user audio unless `config.PERSIST_SESSIONS` / `config.KEEP_USER_AUDIO` say so.
14. **Keep it simple.** Implement what the module doc specifies. Do not add features, abstractions, frameworks, or scope. When the doc is ambiguous choose the simpler option and record it under "Assumptions" in `voice/<module>/MODULE_README.md`.

## How to work
1. Restate the module's contract and acceptance checklist to the human in a few lines.
2. Write the implementation in small files with type hints and docstrings.
3. Write tests next to it: `voice/<module>/tests/test_*.py`. Real-model tests must be marked `@pytest.mark.real`.
4. Run `pytest voice -q` (must stay green) and the conformance test for your module:
   bash: `VOICE_TEST_REAL=<kind> pytest voice -m real -q`; Windows PowerShell: `$env:VOICE_TEST_REAL="<kind>"; .\.venv\Scripts\python.exe -m pytest voice -m real -q`  (kind = input | output | features | detector).
5. Run your module's CLI on a real example and show the output to the human.
6. Fill `voice/<module>/MODULE_README.md`: how to run, env vars, measured latency, known limitations, assumptions.
7. Before saying "done", go through the module doc's **Definition of Done** checklist item by item.

## Things that commonly break integration (avoid)
- Returning a different sample rate / channel count / sample width than the contract states.
- Lazy generators never consumed (e.g. ASR segment iterators) so work silently does not happen.
- NaN/inf in features (use `None`).
- Timestamps relative to the wrong origin (always seconds from the start of the canonical WAV).
- Relying on current working directory (use paths passed in or `voice.config`).
- Modifying input objects (all contract types are frozen; use `model_copy(update=...)`).
- Hidden global state that makes results depend on call order.
