# MindMirror Voice Feature (branch `voice-manipulation`)

Repo: `saifmht19/Mind-Mirror-1` (FastAPI `backend/`, React + TypeScript `frontend/`, Ollama simulator "Nova", Gemini detector).
Today MindMirror detects manipulation from **text, in context**. This branch adds the **complete voice loop**:

```
mic -> Whisper (speech->text) -> Nova reply (Ollama) -> Kokoro (text->speech)
              \-> voice features of the user's audio -> voice-aware detector (Gemini, text prompt) -> tactics / pressure / risk
```

Four people build four modules **independently**. They fit together because everything goes through the frozen
contracts in `voice/contracts.py`, and every module has a working stub from day one.

## Read in this order
1. This file (5 min)
2. `voice/docs/01_ARCHITECTURE_AND_CONTRACTS.md` (everyone, 15 min)
3. `voice/docs/06_GIT_INTEGRATION_AND_TESTING.md` (everyone, 10 min)
4. **Your** module doc (02, 03, 04 or 05)
5. `voice/AGENTS.md` -- the rules your AI coding assistant must follow (see "Using AI" below)

## Who builds what
| Owner | Module | You own (only edit here) | You must expose | Doc |
|---|---|---|---|---|
| Teammate 1 | **M1 Speech input** (audio normalize + Whisper) | `voice/input/` | `voice.input.build() -> SpeechInput` | `docs/02_MODULE1_SPEECH_INPUT.md` |
| Teammate 2 | **M2 Speech output** (Kokoro) + **M2B eval harness** | `voice/output/`, `voice/eval/` | `voice.output.build() -> Synthesizer` | `docs/03_MODULE2_SPEECH_OUTPUT_AND_EVAL.md` |
| Teammate 3 | **M3 Voice features + fusion detector** | `voice/features/`, `voice/fusion/` | `voice.features.build() -> FeatureExtractor`, `voice.fusion.build() -> Detector` | `docs/04_MODULE3_VOICE_FEATURES_AND_FUSION.md` |
| Teammate 4 | **M4 Pipeline + API router + React voice page** | `voice/orchestrator/`, `frontend/src/voice/` | `voice.orchestrator.router:create_router` | `docs/05_MODULE4_ORCHESTRATOR_API_UI.md` |
| **Integrator** (author of the text+context system; recommended: also Teammate 4) | scaffold, contracts, adapters, registry, the few edits to existing files, final merges | `contracts.py config.py registry.py stubs.py adapters.py tests/ docs/ requirements-voice.txt` | -- | `docs/06_...` |

## How it plugs into the existing project (the only edits outside `voice/`, all by the Integrator)
| Existing file | Change |
|---|---|
| `backend/main.py` | 2 lines: `from voice.orchestrator.router import create_router` and `app.include_router(create_router(), prefix="/api/voice")` (done in Phase 2, after Module 4 lands) |
| `.gitignore` | add `.voice_runtime/` (runtime audio/sessions live there, **not** in `data/`, which holds your datasets) |
| `.env.example` | append the lines from `voice/.env.example` |
| `frontend/` | Teammate 4 adds a new `frontend/src/voice/` folder and one route/nav entry, following the existing page patterns |
| `requirements.txt` | untouched. Voice dependencies are heavy (torch, whisper), so they live in the new `requirements-voice.txt`, like your `requirements-research.txt` |
Everything else about the existing app (detector prompt, risk formula, simulator, presentation mode) stays as is. The detector prompt changes **only** through the optional `notes` argument (IP-1) and only for the `context_voice` detector.

## Quick start (every teammate, Windows PowerShell)
```powershell
git fetch; git checkout voice-manipulation; git pull
git checkout -b vm/<your-module>        # vm/input | vm/output | vm/eval | vm/features | vm/fusion | vm/orchestrator
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-voice.txt
Get-Content voice\.env.example | Add-Content .env   # appends the voice settings to your .env (create it from .env.example first if you have none)
.\.venv\Scripts\python.exe -m pytest voice -q      # MUST be green before you write anything (stubs only)
```
macOS/Linux: `python3.12 -m venv .venv && source .venv/bin/activate`, then `pip` / `pytest` directly.

**Environment variables in commands.** The docs show `VOICE_TEST_REAL=input pytest ...` (bash). In PowerShell use:
```powershell
$env:VOICE_TEST_REAL = "input"; .\.venv\Scripts\python.exe -m pytest voice -m real -q
$env:VOICE_IMPL_INPUT = "real"          # persists for this terminal; Remove-Item Env:VOICE_IMPL_INPUT to unset
```

**System tools on Windows** (verify against each tool's current instructions): ffmpeg (e.g. `winget install Gyan.FFmpeg`, then reopen the terminal and check `ffmpeg -version`) for Module 1; espeak-ng (Windows installer from the espeak-ng GitHub releases, make sure it is on PATH) for Module 2/Kokoro.

## The 8 golden rules
1. **Only edit your own directories.** Shared files belong to the Integrator; propose changes by issue/PR.
2. **Never change `contracts.py`.** If it is wrong, stop and raise a `contract:` issue (doc 06).
3. **Implement the Protocol exactly** and expose `build()`. Same method names, argument names, return types.
4. **Stubs first.** Develop against `voice/stubs.py` and `voice/tests/fixtures.py`; never wait for a teammate.
5. **No side effects on import.** Models load lazily on first use (and are cached). `import voice.input` must be instant.
6. **Fail with the contract's exceptions** (`AudioFormatError`, `TranscriptionError`, ...). The pipeline relies on them.
7. **Small PRs into `voice-manipulation`, tests green, owner review.** Never push to `main`. (Your two open PRs on `main` are unaffected.)
8. **Document what you built** in `voice/<module>/MODULE_README.md` (how to run, measured latency, limitations).

## Using AI to write your module
- Give the assistant `voice/AGENTS.md`. Cursor/Codex/Copilot read it from the repo. **Claude Code** reads `CLAUDE.md`: if the repo already has one, add the line `@voice/AGENTS.md` to it (do not overwrite it); if not, create a `CLAUDE.md` containing just that line.
- Paste the **"Paste into your AI assistant"** block from the top of your module doc as the first prompt.
- The assistant must read `contracts.py`, `config.py` and your module doc before writing code.
- **You** are responsible for the result: run the tests, read the diff, check library calls against the library's *current* docs (AI often recalls outdated APIs), never commit secrets, model files or voice recordings.

## Repo map
```
Mind-Mirror-1/
  backend/ frontend/ simulator/ evaluation/ data/ models/ tests/ docs/ ...   <- existing, untouched except as listed above
  requirements-voice.txt                                                   <- new (Integrator)
  .github/CODEOWNERS  .github/pull_request_template.md                     <- new
  voice/
    README.md  AGENTS.md  .env.example  pytest.ini
    contracts.py  config.py  registry.py  stubs.py  adapters.py            <- Integrator-owned (shared)
    docs/                                                                  <- all guidance
    input/  output/  features/  fusion/  orchestrator/  eval/              <- one owner each
    tests/  fixtures.py conformance.py conftest.py test_*.py               <- shared tests (Integrator)
  frontend/src/voice/                                                      <- Teammate 4 (new)
```

## Decisions made up front (Integrator may change before Phase 1, never after)
- **D1 Whose voice?** The live pipeline analyzes the **user's** audio as a *reaction signal* (hesitation, pace and pitch shifts relative to that user's own earlier turns). The synthetic AI voice is **not** analyzed: it has almost no signal. Speech-dataset evaluation uses a separate `dataset_speaker` role and is never pooled with `user` results.
- **D2 Fusion method.** Voice features become a short, clearly-labelled "weak evidence" text block added to the Gemini prompt (integration point IP-1). The existing risk formula is untouched. Raw-audio-to-Gemini and trained fusion are optional experiments behind the same `Detector` interface.
- **D3 Detection never blocks speech.** The turn returns as soon as the reply and its audio are ready. If Gemini (with its retries) is slower, the turn comes back with `detection: "pending"` and the UI polls for the score.
- **D4 English only** for v1 (ASR auto-detects; Kokoro speaks English).
- **D5 Privacy (consistent with the README's "no conversation history is stored on the server").** Whisper and Kokoro run locally. Gemini receives **text only** (transcripts + the cue block), never audio. By default sessions live in memory with a TTL, the user's WAV is deleted right after analysis (`VOICE_KEEP_USER_AUDIO=0`), TTS files expire after `VOICE_AUDIO_TTL_S`, and nothing is written to JSONL (`VOICE_PERSIST=0`). The UI shows a short consent notice before recording. A voice recording is personal data: **never commit recordings** (see doc 02 section 7).

## Assumptions the Integrator must still verify (I could not read the backend code)
- How `backend/` calls the Gemini detector and the Ollama simulator, and the exact shape of the detector output: `adapters.py` must map it into `TurnScore` (including `pressure`, `user_refusal`, `evidence`, `running_risk`, `raw`).
- That the detector accepts an extra prompt block (IP-1) without changing today's prompt when it is absent.
- The `frontend/` source layout and routing library (Teammate 4 reads one existing page and `docs/APP_GUIDE.md` first).
- Dev machines are CPU-only unless noted (`WHISPER_DEVICE=cuda` is supported if someone has a GPU).
