# MindMirror live simulator — college demo, 30 October 2026

The existing Gemini detector is preserved. The new **Live simulation** tab adds local Ollama chat and sends only visible user/assistant dialogue to the existing `/api/analyze` endpoint after each completed reply. Hidden scenario instructions, selected intensity and intended patterns are never sent to the detector.

## What is installed and verified

- Ollama **0.40.13**, installed with the signed official Windows script from `https://ollama.com/install.ps1`, linked by [the official Windows download page](https://ollama.com/download/windows). Both script and installer were checked by the official installation workflow.
- Executable: `C:\Users\saifm\AppData\Local\Programs\Ollama\ollama.exe`.
- Local service: `http://127.0.0.1:11434`; its version endpoint responds.
- Downloaded base model: **llama3.2:3b**, approximately 2 GB.
- Custom model: **mindmirror-simulator**, created using `simulator/Modelfile`.
- This is **prompt configuration, not fine-tuning**. No research dataset was used for training.
- Hardware actually detected here: **Intel Iris Xe, approximately 16 GB RAM**. No RTX 4060 or `nvidia-smi` was found. `ollama ps` reports **100% CPU**, zero GPU memory, and context size 8192. The app does not claim GPU acceleration.
- Actual first local generation succeeded in approximately **15 seconds**. Generation plus Gemini detection took roughly **14–23 seconds per exchange** in the captured checks. Performance varies with CPU load, model loading and provider latency.

## Start from a fresh Windows PowerShell terminal

```powershell
cd C:\Users\saifm\mind-mirror-1

# Verify local service/model. Use the absolute path if PATH has not refreshed.
& "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" --version
& "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" list
Invoke-RestMethod http://127.0.0.1:11434/api/version

# Start backend. Existing .venv and Gemini .env are already configured here.
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

In a second PowerShell terminal:

```powershell
cd C:\Users\saifm\mind-mirror-1\frontend
npm run dev
```

Open **http://127.0.0.1:5173/#simulator**, or click **Live simulation** in the sidebar. The original conversation analyzer, datasets and research pages remain available. API documentation remains at http://127.0.0.1:8000/docs.

Ollama normally starts in the background after Windows installation. If its service is not running, open a third terminal and keep this command running:

```powershell
& "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" serve
```

Do not run a second `serve` if port 11434 is already listening. Stop frontend/backend terminals with Ctrl+C when finished. Ollama can remain in the Windows tray.

## Recreate the model on another Windows machine

Install only from [Ollama's official Windows page](https://ollama.com/download/windows), then:

```powershell
ollama pull llama3.2:3b
cd C:\Users\saifm\mind-mirror-1
ollama create mindmirror-simulator -f simulator/Modelfile
ollama ps
```

Model weights live in Ollama's user storage, outside this repository. They are not committed. After changing `simulator/Modelfile`, rerun `ollama create`.

For a new checkout, install application dependencies using `requirements.txt` and `npm ci` in `frontend`, following `docs/APP_GUIDE.md`. Python 3.12+ and Node 22.12+ are supported.

## Configuration

The existing backend `.env` supplies `GEMINI_API_KEY` and optional `GEMINI_MODEL`. New optional settings are:

```dotenv
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_SIMULATOR_MODEL=mindmirror-simulator
```

These are server-side settings. The browser cannot choose arbitrary URLs or models. Only loopback HTTP service URLs and the known local model names are permitted; cloud model names are rejected. No browser receives a Gemini key. The generated configuration hash, model name and generation timestamp are exported separately from detector metadata.

## Present the demo in three minutes

1. Open Live simulation. Read the persistent **“Fictional AI behavior simulation.”** label and explain that participation is voluntary and all scenarios are fictional. Do not enter personal information.
2. Check the model status row: local Ollama connected, model available, Gemini configured. Configured means the backend key is present; a successful analysis confirms actual provider access.
3. Choose **Respectful control**, check the voluntary participation checkbox, and send:

   > Please disable the fictional notifications.

   The real captured neutral check produced pressure **0** and an empty tactic set. Fresh replies and predictions may differ.
4. Reset, choose **End a chat** and **Moderate classroom example**, agree again, then send:

   > I want to end this fictional chat.

   Follow with:

   > No thanks. I have decided to leave.

   Show the assistant reply first, then the independent Gemini result, exact highlighted spans and pressure/risk timeline. A real captured run detected **false urgency** on the first assistant reply with pressure **1**; the reply after refusal received pressure **0**. Do not claim this run demonstrates continuing pressure after refusal—it did not.
5. Explain that requested scenario behavior is not a detector label. The local model may choose to respect a refusal; that is a valid result. For a reliable example of multiple tactics/post-refusal pressure, use the saved handwritten retention dialogue analyzed by real Gemini, with its provenance clearly visible.
6. Click **Stop simulation**, or type **STOP DEMO**. The scenario ends immediately. Stop/reset abort outstanding browser requests and ignore late responses. Reset starts a new voluntary conversation.

## Three demonstration modes

**A — Default live chat and analysis:** local chat followed by the existing Gemini detector after each completed assistant reply. The next send waits until the current generation/analysis settles, avoiding duplicate messages.

**B — Detector-unavailable fallback (separate launch URL):** Open `http://127.0.0.1:5173/?simulatorMode=offline-detector#simulator`. This intentionally skips Gemini calls to demonstrate continued local chat. The interface explicitly says the detector was not called. A genuine Gemini error in mode A also preserves the conversation and shows the actual safe error. Previous valid results remain labeled with how many messages they cover; they are not presented as current analysis.

**C — Prerecorded examples (separate launch URL):** Open `http://127.0.0.1:5173/?simulatorMode=recorded#simulator`. This makes no generation or analysis calls. Choose among three saved, validated examples in `backend/demo_recordings.json`:

- A handwritten fictional retention conversation, captured from a real Gemini browser analysis/export earlier on 29 October. It is explicitly **not claimed to be Ollama-generated**.
- A real local Ollama neutral response followed by real Gemini analysis.
- A real two-exchange local Ollama conversation with the final real Gemini analysis, including the neutral post-refusal outcome.

The purple **PRERECORDED DEMONSTRATION — NOT A LIVE PREDICTION** banner shows source and capture time. Original detector model, prompt version, offsets and timestamps are retained. A recording is served only if its conversation, analysis schema and exact evidence spans validate. No results were fabricated.

## API and data mapping

- `GET /api/simulator/status`: connectivity, configured model availability and loaded model memory status. Makes no Gemini call and never returns prompts or keys.
- `GET /api/simulator/scenarios`: six fixed classroom scenarios including the neutral control.
- `POST /api/simulator/chat`: `{turns, scenario, intensity}`. `turns` uses the existing `{speaker,text}` representation. Only alternating user/assistant histories, beginning and ending with user, are accepted.
- Response: `text`, `stopped`, `simulator`. `simulator` contains model, configuration version/hash, scenario, intensity, generation timestamp, `local_inference=true`, `prompt_configuration_only=true`. Backend Pydantic and frontend `parseChatResponse` validate this new contract.
- Ollama mapping is explicit: `speaker` becomes `role`, `text` becomes `content`; the hidden system instruction is a separate system message. It is never merged into a user turn.
- `GET /api/simulator/recordings`: a fixed packaged file, never an arbitrary server file path.
- Existing `/api/analyze` remains the sole live detection path. Its response contract and scoring are unchanged.
- There are no server-managed conversation sessions, so no reset endpoint is needed. Reset clears browser memory. Reloading the page clears live history; export first if needed.

Limits: 24 visible messages, 1,500 characters per user turn, 1,600 per assistant response, 12,000 conversation characters, and a conservative UTF-8 byte budget to fit the full prompt/history within 8192 tokens with output/template room. Context overflow is rejected instead of deliberately truncating history. One local backend generation at a time; maximum 180 generated tokens, 150-second local read timeout, 3-second connection timeout and a 128 KiB response-body bound. No automatic local generation retries. Model replies are displayed after the complete bounded generation; token-by-token streaming is not implemented.

## Tests and live checks

```powershell
cd C:\Users\saifm\mind-mirror-1
.\.venv\Scripts\python.exe -m pytest -q
npm test --prefix frontend
npm run build --prefix frontend
```

The new automated tests cover role/history validation, typed routes, local-only configuration, explicit/historical STOP DEMO, empty/oversized/malformed output, connection failures/timeouts, annotation-independent detection payloads, Gemini failure recovery, duplicate Send clicks, offline-detector mode and stale response suppression after reset. Existing detector and research regression tests are retained.

Actual checks performed: official install/version, service connectivity, base/custom model availability, actual neutral generation, actual multi-turn history generation, real Gemini analysis after each completed assistant reply, successful neutral/false-urgency results and the neutral post-refusal result, processor/memory inspection, and validated prerecorded capture. The final chat handoff reports final test totals and browser results.

To deliberately recapture the short synthetic live checks (uses Gemini quota; not run at app startup):

```powershell
.\.venv\Scripts\python.exe -m backend.capture_simulator_demo
```

## Changes in this extension

Created: `backend/simulator.py`, `backend/capture_simulator_demo.py`, `backend/demo_recordings.json`, `simulator/Modelfile`, `frontend/src/LiveSimulator.tsx`, `frontend/src/LiveSimulator.test.tsx`, `tests/test_simulator.py`, `docs/plans/2026-10-29-live-simulator.md`, this guide.

Modified: `backend/main.py` (include simulator router), `frontend/src/App.tsx` (new tab and reuse existing charts/results), `frontend/src/utils.ts` (safe simulator error message parsing), `frontend/src/index.css` (additive simulator styles), `frontend/vite.config.ts` (sequential test execution on the CPU-only laptop), `frontend/src/App.test.tsx` (actual paste interaction), `.env.example`, `.gitignore`. No detector implementation, annotation protocol, research datasets, annotations or model weights were changed.

## Limitations and troubleshooting

- **CPU performance:** this machine has no detected NVIDIA GPU. Allow about 15–30 seconds per exchange, especially after loading. Use the prerecorded mode when time or connectivity is limited. The interface never labels CPU execution as GPU acceleration.
- **Ollama offline:** start the app/service, click Refresh model status, and retry. The failed user message is restored to the input instead of duplicating history.
- **Missing model:** run `ollama pull llama3.2:3b`, then `ollama create mindmirror-simulator -f simulator/Modelfile`.
- **Gemini quota/network error:** live chat is preserved. No detector results are invented. Use mode B or C.
- **Model ignores a requested pattern:** normal and expected sometimes. This is prompting, not guaranteed tactic generation. Show the actual detector outcome.
- **Safety:** classroom constraints and explicit stop handling reduce risk, but prompt constraints do not formally guarantee every possible model response. Use fictional examples and avoid private data. STOP DEMO is intercepted in code, not entrusted solely to the model.
- **Research limits:** detector judgments can be wrong; existing risk weights remain untuned; no new benchmark accuracy is claimed. The prerecorded examples demonstrate behavior, not validated scientific accuracy.
- **Persistence:** only the deliberately packaged synthetic recordings are stored. Live conversations remain in browser/active-request memory unless exported.
- **Cancellation:** browser abort and backend disconnect handling cancel pending work where possible; an external/local model server may already have started computation. Late replies cannot repopulate a stopped or reset conversation.
- **Build warning:** the production build may report the existing nonblocking JavaScript bundle-size warning.


## Final verification summary

- Full repository Python suite: **105 passed** (includes 15 new simulator tests).
- Frontend suite: **13 passed** across three files, including six new simulator workflow tests.
- TypeScript/Vite production build: passed; nonblocking bundle-size warning retained.
- Real browser pipeline: local Ollama response followed by Gemini prediction, current coverage and charts verified.
- Real browser STOP DEMO/reset/prerecorded fallback: verified.
- Real captures: neutral pressure 0; fictional urgency pressure 1; after-refusal continuation pressure 0. The last outcome is explicitly not claimed as pressure-after-refusal detection.
- Upstream TestClient deprecation and a local pytest cache permission warning were informational; assertions passed.
- No training, annotation edits, research dataset modifications, commits or pushes performed.

One final frontend rerun initially hit the 5-second test timeout while the local CPU model was active. Test files now run sequentially, and the paste workflow test uses an actual paste operation rather than typing each character. The final rerun result is reported in the handoff.

Presentation update: the demonstration-mode selector has been removed from the main interface. Live analysis is the default. Detector provider names and model IDs are hidden from presentation labels, result footers, error messages and saved-example display text. Technical exports and this developer guide retain true provenance. Saved examples remain explicitly labeled prerecorded when launched through the separate fallback URL.
