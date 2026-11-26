# 05 - Module 4: Pipeline, API Router, React Voice Page, Logging (Teammate 4 / Integrator)

> Command syntax: examples use bash-style env prefixes; on Windows PowerShell see the README ("Environment variables in commands").

**Mission:** run one voice turn end to end, expose it as a router inside the **existing FastAPI backend**, show it in a
**new page of the existing React frontend**, and observe it. You work **entirely on stubs** first (everything defaults to stub),
then flip modules to real one at a time.

**You own:** `voice/orchestrator/` and a new folder `frontend/src/voice/`  **Branch:** `vm/orchestrator`
**Expose:** `voice.orchestrator.router:create_router(components=None) -> APIRouter` (mounted by the Integrator at `/api/voice`)

## Before you start (30 min, do not skip)
Read `docs/APP_GUIDE.md` (API contracts, architecture), `backend/main.py` (how routers, CORS and env are set up), and one existing
frontend page + its API client (routing, fetch pattern, styling, how presentation mode works). **Match those patterns.** Do not add a
new UI framework, state library or CSS system. Confirm the frontend dev proxy/base-URL setup so `/api/voice/*` works from `npm run dev`.

## Paste into your AI assistant
> You are implementing Module 4 (pipeline, API router, React voice page, logging) of the MindMirror voice feature. First read voice/AGENTS.md, voice/contracts.py, voice/config.py, voice/registry.py, voice/docs/01_ARCHITECTURE_AND_CONTRACTS.md and voice/docs/05_MODULE4_ORCHESTRATOR_API_UI.md, then docs/APP_GUIDE.md, backend/main.py and one existing frontend page. Build a FastAPI `APIRouter` in voice/orchestrator/ that runs the turn flow from the doc, obtaining all components ONLY through voice/registry.py getters, and a React + TypeScript page in frontend/src/voice/ that follows the existing frontend patterns. Everything must work with the default stubs. Edit only voice/orchestrator/ and frontend/src/voice/ (plus one route/nav entry in the frontend router, and pinned lines under the M4 header of requirements-voice.txt). Finish by walking the Definition of Done checklist.

## 1. Turn flow (implement exactly; diagram in doc 01 section 2)
```python
async def run_turn(session_id: str, upload: bytes, mime: str) -> TurnResult:
    async with session_lock(session_id):                    # turns of one session are strictly sequential
        t0 = perf_counter()
        idx = store.next_index(session_id)                  # user turn index; assistant gets idx+1
        src = write_temp(upload); wav = config.user_audio_path(session_id, idx)
        await run_cpu(speech.normalize, src, str(wav))                  # "normalize" -> AudioFormatError => 422 bad_audio
        utt = await run_cpu(speech.transcribe, str(wav))                # "asr"       -> TranscriptionError => 502 asr_failed
        if not utt.transcript.strip(): raise NoSpeech                   # 422 no_speech, nothing stored
        user_turn = Turn(index=idx, role="user", text=utt.transcript, audio_path=str(wav))
        history = store.turns(session_id) + [user_turn]
        reply, voice = await gather(                                    # PARALLEL
            run_cpu(generator.generate, history),                       # "generate" -> failure => 502 generator_failed
            run_cpu(extractor.extract, str(wav), utt.segments, role="user"),   # "features" -> failure => voice=None + warning "features_failed"
            return_exceptions=True)
        if not config.KEEP_USER_AUDIO: delete(wav)                      # privacy default: user audio is gone after features
        user_turn = user_turn.model_copy(update={"voice": voice, "audio_path": None if deleted else str(wav)})
        history = store.turns(session_id) + [user_turn]
        ai_turn = Turn(index=idx + 1, role="assistant", text=reply)
        det_task = asyncio.create_task(run_cpu(detector.analyze, history, ai_turn, voice))      # starts now
        tts = await safe(run_cpu(synth.synthesize, reply, str(config.tts_audio_path(session_id, idx + 1))))   # "tts" -> failure => tts=None + "tts_failed"
        try:    score = await asyncio.wait_for(asyncio.shield(det_task), config.DETECT_WAIT_MS / 1000); detection = "done"
        except asyncio.TimeoutError:                                    # Gemini (with retries) is slower than speech
            score, detection = None, "pending"
            det_task.add_done_callback(lambda t: store.set_score(session_id, idx + 1, t))   # fills score, sets done/failed
        except DetectionError/Exception: score, detection = None, "failed"   # + warning "detector_failed"
        result = TurnResult(..., detection=detection, timings_ms={..., "total": ...}, warnings=[...], impl={...})
        store.append(session_id, result)
        return result
```
- `run_cpu` = `asyncio.to_thread` guarded by a global `asyncio.Semaphore(N)` (default 2, env `VOICE_CPU_CONCURRENCY`). The detector call is network-bound: do **not** count it against the CPU semaphore.
- Per-stage timeouts (env, defaults: asr 60 s, generate 120 s, tts 60 s, detect 90 s). A timeout is a failure of that stage per the failure policy.
- Components come from `registry.get_*()` **once**, when the router is created, not per request. `create_router(components: Optional[Components] = None)` must accept injected components (for tests).
- `TurnResult.impl` records which implementation ran (`stub`/`real`) per component, plus the detector name.
- The detector judges the whole conversation, so each turn sends the history to Gemini again: keep that call as the single detector call per turn, and never call it twice.

## 2. Session store (`store.py`) - privacy defaults matter
The project states that no conversation history is stored on the server. Therefore:
- Sessions live **in memory** only, with an idle TTL (`config.AUDIO_TTL_S`, default 15 min). A background sweeper deletes expired sessions **and their TTS files**.
- JSONL persistence (`config.session_dir(session_id)/turns.jsonl`) happens **only** when `config.PERSIST_SESSIONS` is true. Default is off.
- The user's WAV is deleted right after feature extraction unless `config.KEEP_USER_AUDIO` is true.
- `session_id` = `uuid4().hex`; always validate through `config.session_dir` (it rejects path tricks).
- API: `create()`, `turns()`, `next_index()`, `append()`, `set_score()`, `delete(session_id)` (deletes memory + files), `sweep()`.

## 3. HTTP API (router prefix `/api/voice`, mounted in `backend/main.py` by the Integrator)
| Method / path | Purpose | Success body |
|---|---|---|
| `GET /api/voice/health` | liveness + config | `{"contract_version","impl":{"input":"stub",...},"detector":"context_voice","ffmpeg":bool,"persist":bool}` |
| `POST /api/voice/sessions` | new session | `{"session_id": "..."}` |
| `POST /api/voice/sessions/{id}/turns/audio` | multipart field **`audio`** -> one turn | `TurnResult` JSON + `tts_url` (string or null) |
| `POST /api/voice/sessions/{id}/turns/text` | `{"text": "..."}` -> same flow without audio steps (`voice=None`) | same |
| `GET /api/voice/sessions/{id}/turns/{assistant_index}` | poll a turn (used while `detection == "pending"`) | same `TurnResult` |
| `GET /api/voice/sessions/{id}` | history | `{"session_id","turns":[TurnResult...]}` |
| `DELETE /api/voice/sessions/{id}` | delete everything | 204 |
| `GET /api/voice/audio/{id}/{filename}` | serve a TTS wav of that session | audio/wav |
Errors: JSON `{"error": "<code>", "detail": "..."}` with the HTTP status from doc 01 section 6; codes `bad_audio no_speech asr_failed generator_failed too_large unsupported_media session_not_found`.
Security: reject uploads > `config.MAX_UPLOAD_BYTES` (413); allow mime `audio/webm audio/ogg audio/wav audio/x-wav audio/mpeg audio/mp4 audio/x-m4a video/webm` (415 otherwise); serve audio only from the session folder with filename `^[A-Za-z0-9_.-]+\.wav$`; reuse the backend's existing CORS setup (do not add another). No auth in v1 (local demo): say so in MODULE_README.md. The existing detector API key stays on the backend; never send it to the browser.

## 4. React page (`frontend/src/voice/`, TypeScript, follow existing patterns)
Files (adapt names to the repo's conventions): `VoicePage.tsx`, `voiceApi.ts` (typed client), `types.ts` (hand-written mirror of `TurnResult`, `TurnScore`, `Turn`, `VoiceFeatures`; keep in sync with `contracts.py` v1.1.0), `useRecorder.ts`, `useTurnPolling.ts`, small components.
- **Consent notice** before the first recording: audio is processed locally, deleted right after analysis by default, and only the transcript text goes to the detection service.
- Record button (press to start/stop) using `MediaRecorder`; negotiate mime (`audio/webm;codecs=opus`, fallback `audio/mp4`); upload `FormData` field `audio`. Works on `http://127.0.0.1` / `localhost` (mic needs a secure context).
- Conversation list: user transcript; assistant reply with **tactic chips**, **pressure 0-3**, **evidence spans highlighted in the reply**, **running risk**, and a flag badge from `manipulation_score`.
- While `detection === "pending"` show a "Analysing..." state and poll `GET .../turns/{assistant_index}` every ~700 ms (stop after done/failed or 90 s). Auto-play the reply audio from `tts_url` immediately, independent of detection.
- "Details" drawer per turn: stage timings, `impl`, warnings, the voice features, and whether `used_voice` was true (i.e. voice cues reached the detector).
- Text box (uses `/turns/text`), "End and delete session" button (DELETE), clear error toasts for every error code, record button disabled while a turn is processing.
- One route + nav entry only. Presentation mode, existing pages and their tests must be unaffected.
- Tests with the repo's frontend test runner (`npm test`) for the recorder state machine, polling hook and score rendering (mock `fetch`). `npm run build` must pass.

## 5. Logging and observability
Structured log line per turn (`logging`, JSON): session id, indices, stage timings, `impl`, warnings, flagged, detector, detection status. Never log audio, and log transcripts/replies only at DEBUG. Keep per-stage timings in every `TurnResult`.

## 6. Headless CLI (`cli.py`)
`python -m voice.orchestrator.cli turn --audio clip.wav [--session ID]` runs a turn without HTTP and prints the `TurnResult` JSON. `python -m voice.orchestrator.cli serve` starts a **standalone** app (`create_app()` = FastAPI + this router at `/api/voice`) on `127.0.0.1:8001`, so Module 4 can be developed without touching `backend/main.py`. FastAPI's `/docs` is the quick manual test UI.

## 7. Tests (`voice/orchestrator/tests/`, FastAPI `TestClient`, stubs unless marked real)
1. Happy path: create session -> upload the `synth_speechlike` wav -> 200, valid `TurnResult`, all timing keys, assistant turn has a score, `tts_url` fetchable and is a WAV; second turn has indices 2 and 3.
2. `no_speech`: injected `SpeechInput` returning `""` -> 422 `no_speech`, nothing stored.
3. Failure matrix with injected failing fakes: extractor raises -> 200, `voice=None`, `features_failed`; synthesizer raises -> `tts=null`, `tts_failed`; detector raises -> `score=null`, `detection="failed"`, `detector_failed`; generator raises -> 502 and nothing stored; garbage upload -> 422 `bad_audio`.
4. **Parallelism**: generator and extractor each `sleep(0.3)` -> that stage takes < 0.5 s; detector overlaps TTS.
5. **Pending detection**: detector sleeps 3 s with `DETECT_WAIT_MS=500` -> POST returns in < 1.5 s with `detection="pending"`, `score=null`, `tts` present; polling the turn endpoint later returns `done` with the score.
6. Per-session sequencing: two concurrent uploads to one session get strictly increasing, non-overlapping indices.
7. Security: > 10 MB -> 413; path traversal on `/audio` -> 404; bad mime -> 415.
8. **Privacy defaults**: after a turn, the user WAV no longer exists and no `turns.jsonl` was written; with `VOICE_PERSIST=1` the JSONL exists; deleting a session removes memory and files; expired sessions are swept.
9. Mount test: include the router in a plain `FastAPI()` at `/api/voice`; health responds (proves the Integrator's 2-line mount works).
10. Swap test (manual, recorded in the PR): happy path with each `VOICE_IMPL_*=real` flipped one at a time as modules land.
Run: `.\.venv\Scripts\python.exe -m pytest voice -q`.

## 8. Files
```
voice/orchestrator/__init__.py      # exports create_router, create_app, Components
voice/orchestrator/router.py        # APIRouter + routes
voice/orchestrator/pipeline.py      # run_turn (section 1)
voice/orchestrator/store.py         # in-memory store, TTL sweeper, optional JSONL
voice/orchestrator/app.py           # standalone create_app() for dev/tests
voice/orchestrator/cli.py
voice/orchestrator/MODULE_README.md
voice/orchestrator/tests/
frontend/src/voice/...              # section 4
```

## 9. Pitfalls
Calling real modules per request instead of once; forgetting `return_exceptions=True` (one failure cancels its sibling); blocking the event loop; awaiting the detector before returning (breaks D3); counting the network-bound detector against the CPU semaphore; browser `MediaRecorder` mime differences; returning server file paths to the browser (return URLs); two turns of one session interleaving; persisting or logging private transcripts; leaving user WAVs on disk; adding a second CORS layer; touching existing pages/tests.

## Definition of Done
- [ ] Whole loop works on stubs in the browser: record, see transcript, reply with tactics/pressure/risk, hear the reply
- [ ] Parallelism and pending-detection tests pass; per-stage timings returned
- [ ] Failure matrix behaves exactly as doc 01 section 6; no voice failure breaks the text reply
- [ ] Components obtained only via `voice/registry.py`; router accepts injected components; mount test passes
- [ ] Privacy-default tests pass (no persistence, user WAV deleted, TTL sweep, delete endpoint); consent notice shown
- [ ] Security checks pass; no second CORS layer; no secrets reach the browser
- [ ] `npm test` and `npm run build` pass; existing pages/presentation mode unaffected
- [ ] Swapped to real modules one at a time with the e2e check recorded for each
- [ ] MODULE_README.md: run steps, env vars, curl examples, limitations; requirements pinned under the M4 header
