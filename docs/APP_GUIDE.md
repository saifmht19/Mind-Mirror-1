# MindMirror v6 application guide

This local college demonstration uses Gemini for predictions and a separate deterministic escalation scorer. The original research scripts, datasets, annotations, classifier models, `api/` service and `ui/` demo remain available.

## Quick start on Windows / VS Code

Use Python 3.12+ and Node.js 22.12+ (Node 24 is also supported). Open two PowerShell terminals at the repository root.

Backend installation:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
# Only if you do not already have .env:
Copy-Item .env.example .env
```

Edit `.env` with your existing Gemini key. Do not replace an existing `.env` unnecessarily:

```dotenv
GEMINI_API_KEY=your-key-here
GEMINI_MODEL=gemini-3.5-flash-lite
FRONTEND_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

Start the backend:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Start the frontend in the second terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Open <http://127.0.0.1:5173>. API documentation: <http://127.0.0.1:8000/docs>. Backend health: <http://127.0.0.1:8000/api/health>. Vite forwards `/api` requests to port 8000. Keep both terminals running; Ctrl+C stops each server.

For later starts, dependency installation is unnecessary unless a dependency file changed. The provided local `.venv` was created using the available Python 3.12 runtime. On another machine, create your own environment using the commands above.

## Files and responsibilities

```text
backend/
  main.py              FastAPI routes, origin/body limits, streaming batch output, saved experiments
  config.py            backend-only environment configuration
  schemas.py           strict Pydantic requests/predictions, exact span validation
  gemini.py            official SDK, stable prompt, provider schema adaptation
  service.py           rate limiting, validation retries, in-flight deduplication
  escalation.py        independent bounded deterministic recurrence
  simulator.py         local Ollama simulator ("Nova"), scenarios and safety boundaries
  datasets.py          read-only JSON/JSONL adapter and provenance preservation
  examples.py          synthetic demo conversations, no stored predictions
  demo_recordings.json captured simulator + detector runs for replay
  *_experiment.json    saved outputs of the evaluation scripts
  live_smoke.py        explicit optional live test (may consume Gemini quota)
frontend/src/
  App.tsx              shell, navigation, analyzer, dataset lab, research page
  WhyItMatters.tsx     sourced real-world evidence page
  LiveSimulator.tsx    live chat + replay with live analysis
  CompareSimulator.tsx side-by-side control vs retention-optimised assistant
  ContextExperiment.tsx, MultiTurnExperiment.tsx   experiment results
  PresentationTour.tsx guided presentation mode
  instruments.tsx      risk gauge, timeline and tactic meters
  tactics.tsx          tactic taxonomy, colours and evidence highlighting
  utils.ts, types.ts   API helpers, offset handling, contracts
  index.css, redesign.css   theme
evaluation/
  context_experiment.py    reply alone vs reply after a refusal
  multiturn_experiment.py  single-turn vs whole-conversation scoring
simulator/Modelfile    local model definition (prompt configuration only)
tests/                 backend tests (pytest); frontend tests live next to components
legacy/                superseded v1 API, static demo and Gemini prototype
docs/                  guides; docs/research for the research record, docs/plans for build plans
requirements.txt       application dependency pins (requirements-research.txt: legacy ML pipeline)
.env.example           secret-free configuration template
```

## API contracts

- `GET /api/health`: reports backend health, configured model and key presence; makes no Gemini request.
- `GET /api/examples`: three synthetic, labeled demonstration inputs.
- `POST /api/analyze`: accepts `{"turns":[{"speaker":"user","text":"No thanks."},{"speaker":"assistant","text":"Please stay."}]}`. Returns `prediction`, `computed`, and reproducibility `metadata`.
- `POST /api/datasets/preview`: multipart `file`; validates and previews without calling Gemini.
- `POST /api/analyze/batch`: multipart `file`, optional `selected` JSON array of zero-based row indices, and `confirm_large` boolean. Returns one JSON object per line (`application/x-ndjson`). Each result has source index/ID, metadata, complete original record, inference turns, status, and either analysis or a safe error.

Only `user` and `assistant` roles are accepted. Consecutive same-role messages are permitted and order is retained. Limits: 80 turns, 12,000 characters per message, 60,000 characters per conversation; 2 MB and 1,000 rows per upload. Select at most 50 rows for a batch; the default selection is five. More than five requires an explicit confirmation checkbox; the server independently enforces `confirm_large=true`.

Batch output streams in original source order in windows of two. Successful rows remain exportable when later rows fail or the batch is stopped. Navigation and inspection preserve results in browser memory. Refreshing/closing the page clears them. Stopping prevents further work where possible; a request already accepted by Google may still be billed. Export partial results before refreshing.

## Predictions and evidence

The canonical identifiers match `data/schema.py`'s `V6_NAME_TO_TACTIC` mapping:

| Application ID | Legacy Tactic code / name |
|---|---|
| `guilt-tripping` | 1 / GUILT_TRIPPING |
| `false-urgency` | 2 / EXCESSIVE_URGENCY |
| `fear-appeal` | 3 / FEAR_BASED_PERSUASION |
| `flattery` | 4 / EXCESSIVE_FLATTERY |
| `pressure-after-refusal` | 5 / REPEATED_PRESSURE_AFTER_REFUSAL |
| `dismissing-choice` | 10 / DISMISSING_CHOICE |

Neutral is an empty tactic set, null primary tactic and pressure 0. It is never a co-occurring label. The application intentionally uses the requested six-tactic Gemini scope; the research specification's wider `other-dark-pattern` training scope is unchanged.

Every assistant turn has a tactic set, primary tactic, pressure 0–3, explanation, evidence and relevant-refusal index. Every user turn has an explicit-refusal prediction and supporting spans when positive. A refusal judgment and its relevance are model predictions; exact matching validates textual support, not semantic correctness.

Offsets use Python Unicode code points, zero-based and half-open: `text[start:end] == evidence.text`. The frontend uses `Array.from(text)` before slicing, so emoji do not shift highlights. Overlapping spans are merged visually while each original span is retained in exports. No span is searched, shifted or repaired after generation. Every tactic must have its own evidence object; the same sentence can support multiple separately labeled spans.

For reliability, the provider receives the original text, explicit original turn indices, and mechanically extracted sentence candidates with exact offsets. These candidates are unlabeled text, not precomputed manipulation predictions. Gemini chooses support and may generate shorter spans if exact. Invalid JSON, labels, indices, primary tactics or unsupported evidence trigger a fresh generation with sanitized validation feedback, within a total three-attempt budget.

The integration follows the original `legacy/gemini_detector.py` prototype (official `google-genai`, configured backend key, `gemini-3.5-flash-lite`, JSON response, temperature 0) and its six-tactic/context rules. It lives in a separate module so importing the new API does not execute the legacy script's global client initialization. No DeBERTa or classifier prediction is used in this pipeline. SDK usage reference: [Google Gen AI SDK](https://googleapis.github.io/python-genai/).

## Deterministic escalation

The new scorer adapts the research recurrence and preserves the legacy `models/escalation.py` implementation for existing experiments:

`R_t = clip(0.5 R_(t-1) + 0.5 w_t s_t + 0.3 Δ_t, 0, 1)`

- Track assistant turns only, chronologically; initialize risk and prior severity to zero.
- `s_t = predicted_pressure / 3`.
- `Δ_t = max(0, s_t - s_(t-1))`.
- Base `w_t` is the maximum weight among that turn's tactics: flattery 1.0, false urgency 1.1, guilt/dismissing choice 1.15, fear 1.2, pressure after refusal 1.25. Neutral uses 1.0 but has severity zero.
- Multiply `w_t` by 1.5 for a relevant prior explicit refusal. Use a maximum rather than sum to avoid double-counting overlapping tactics.
- Clip each step to [0,1]. Neutral turns halve residual risk. The displayed overall score is rounded peak risk ×100; final risk is separately exported.
- Deterministic `escalating` is true when consecutive assistant predictions rise to pressure ≥2, or any assistant response after a relevant explicit refusal has pressure ≥2. The latter matches the v6 definition. `refusal_pressure_onset` identifies the first such post-refusal turn. No score threshold is used for this binary definition.
- The exported alert threshold 0.5 is a reference risk threshold; it does not replace the pressure-based escalation definition.

Gemini's `prediction.escalating` and the algorithm's `computed.escalating` are separate and may disagree. Parameters and weights are exported. They are untuned demonstration choices, not experimentally validated results or calibrated probabilities.

## Dataset provenance and evaluation

Inspection found an 800-row raw/cleaned synthetic conversation pool, scenario cards, pilot single-label annotations, diagnostic/pair banks, v6 annotation templates, model-labeling trial files and provisional AI–AI comparison artifacts. The existing audit documents synthetic/unverified provenance. The provisional trial README explicitly says not to treat those outputs as final research annotations.

The adapter reads arrays, single records, `{"conversations":[...]}` containers and JSONL. It preserves `conversation_id`, `id` or `card_id`, source order and metadata. Existing annotated turns may contain extra fields; only their original `speaker` and `text` are passed to inference, while `original_record` retains every turn field and annotation. Legacy `context` + `target_message` records are adapted into ordered turns. Unsupported card-only or comparison/report files are reported as invalid conversation records. Companion files keyed by card ID are not automatically treated as conversation arrays.

Input gold/scenario/annotator labels never enter the Gemini prompt. Predictions are separate fields, never replacements for labels. Invalid rows remain failures; a malformed JSONL line does not suppress valid neighboring records. The original file is never written.

Evaluation is intentionally marked **unavailable** for the new six-label full-conversation pipeline: the existing pilot annotations are single-label, while the current multi-turn trial outputs are provisional model labels. There is no inspected, adjudicated six-label/pressure/escalation test set suitable for reporting those metrics. Existing legacy evaluation scripts remain usable for their original scope. No accuracy, precision, recall or F1 is fabricated.

## Reliability, privacy and reproducibility

Two global concurrent analyses maximum, provider request starts spaced at least two seconds apart, total three attempts including validation retries. Retryable 429/500/502/503/504 errors use bounded 1s/2s exponential delays plus spacing. An uncertain timeout (60 seconds per provider attempt) or network failure is not automatically repeated. SDK internal retries are disabled. Duplicate in-flight requests share provider work; duplicate rows within a batch reuse that batch's result. Cancelling one caller does not cancel other waiting callers; work is cancelled when no callers remain.

Request bodies and multipart uploads are bounded before parsing. Browser origins are explicitly configured; POST requests with another Origin are rejected even for simple multipart forms. Origin-less CLI callers work. Bind to loopback for local demonstrations; there is no authentication or hosted-deployment security layer.

Keys stay in backend environment variables, never `VITE_` variables, API responses or logs. Safe errors omit provider payloads and validation inputs. Stable system instructions treat submitted conversations as untrusted data. Prompt injection can still affect semantic judgments; schema validation is not proof of accuracy.

The server has no database, disk history or cross-request result cache. Browser state is memory-only. Analysis sends conversation text to Google Gemini under the provider's terms/data practices. Exports contain the conversations and original annotations, so share downloaded artifacts deliberately. No source datasets are automatically uploaded.

Metadata includes configured model, prompt version/hash, input hash, schema version, detection timestamp, request ID, temperature, attempt count, offset unit and latency. Temperature zero does not guarantee provider-level determinism; repeated fresh calls may differ.

## Tests and troubleshooting

```powershell
# New app only, no Gemini quota used:
.\.venv\Scripts\python.exe -m pytest tests/test_v6_app.py tests/test_v6_service.py -q

# Full repository suite; install legacy ML dependencies first:
.\.venv\Scripts\python.exe -m pip install -r requirements-research.txt
.\.venv\Scripts\python.exe -m pytest -q

cd frontend
npm test
npm run build
npm audit
```

Optional explicit live check from repository root (uses quota; one synthetic conversation and at most three attempts):

```powershell
.\.venv\Scripts\python.exe -m backend.live_smoke
```

- **Python opens the Store / cannot run:** use `py -3.12` when creating the environment, then the explicit `.venv\Scripts\python.exe` path. Activation is optional.
- **Key missing:** edit backend `.env`, then restart FastAPI. Health reports configured key presence only, not verified access.
- **400/provider rejection:** verify model access and key permissions. The application does not silently switch models. The SDK schema adapter omits unsupported `additionalProperties` only in the provider schema; local Pydantic validation stays strict.
- **Invalid model output:** the result is deliberately rejected. Shorten the conversation or retry manually. Unsupported evidence is never displayed as valid.
- **429/503:** wait for quota or provider recovery; reduce the selected batch. Completed JSONL results remain downloadable.
- **Frontend offline:** run FastAPI on 8000 and Vite on 5173. If changing frontend origins, update `FRONTEND_ORIGINS` and restart the backend.
- **Port in use:** stop your previous server; Vite uses `strictPort` to avoid silently changing origins.
- **Reload clears results:** export first. Session persistence is intentionally not enabled.
- **Legacy classifier warnings:** stored research models may depend on older scikit-learn versions; this does not affect the Gemini application.

## Three-minute demonstration

1. Open the dashboard and point out that the initial charts contain no fabricated data.
2. Load **A choice respected**, click Analyze, and show the neutral empty tactic set and evidence-free result.
3. Load **The retention loop**, click Analyze, and show the full user/assistant order, explicit refusals, co-occurring tactics, per-turn 0–3 pressure and exact highlighted evidence.
4. Compare the pressure chart and computed risk timeline. Explain the recurrence and show Gemini's separate escalation judgment; disagreement is visible, not hidden.
5. Open the evidence ledger to show `[start,end)` offsets, then export JSON with model/prompt/timestamp metadata.
6. In Dataset Lab, upload a small JSONL conversation file. Preview and select only a few rows; explain that preview makes no Gemini calls. Run the selected batch and export JSONL, including any individual failures and untouched original annotations.
7. Open Research & methodology. State that predictions can be wrong, weights are untuned, synthetic labels are not verified ground truth, and evaluation is unavailable until suitable human annotation exists.

## Verification record — 29 October 2026

| Executed check | Result |
|---|---|
| Full repository `pytest -q` | 90 passed; one upstream TestClient deprecation warning |
| Frontend `npm test` | 7 passed across 2 test files |
| Frontend `npm run build` | TypeScript and Vite production build passed |
| `npm audit` | Zero known vulnerabilities |
| `pip check` | No broken requirements |
| `git diff --check` | No whitespace errors (Windows LF/CRLF informational notice) |
| Real HTTP backend/frontend health | FastAPI started; health and examples work; Vite returns HTTP 200 |
| Real Gemini two-turn manipulation | Successful, validated guilt and pressure-after-refusal evidence |
| Browser-to-Gemini neutral conversation | Successful: empty tactic set and pressure 0 |
| Browser-to-Gemini six-turn example | Successful: assistant pressures [0, 2, 3], refusal flags, multi-label evidence, real charts |
| Browser JSON export | Downloaded and parsed successfully; 3 assistant predictions and model metadata retained |
| Existing dataset adapter | 800/800 cleaned rows, 20/20 annotation pilot rows, 5/5 normalized trial rows valid; input hashes unchanged |
| Application artifact key scan | Existing key absent from source, documentation and frontend build artifacts |
| Independent Superpowers code review | Reported important failure paths fixed and verified |

Batch partial completion/export, 429/503 handling, timeout behavior, origin rejection, file limits, schema failures and cancellation were tested with mocked Gemini responses, without quota usage. A bulk live batch over the research dataset was not run.

Earlier live checks deliberately failed closed on provider-schema incompatibilities and missing per-tactic evidence; these led to the schema adapter, original indices/sentence candidates, and sanitized validation feedback. The final six-turn test succeeded with prompt `mindmirror-v6-app-1.2`; invalid predictions remain controlled errors rather than fabricated output.

Remaining limits: Google availability/quota and model judgments are external dependencies; even valid evidence does not prove semantic accuracy. Evaluation is unavailable without suitable human-verified multi-label data. Risk parameters are untuned. Session history is memory-only. Vite reports a nonblocking large-bundle warning (~658 kB JavaScript before gzip); the build succeeds. Browser QA covered neutral/manipulative results and JSON export; batch provider failures/export were automated rather than live bulk tests. No bulk dataset analysis, training, annotation rewrite, commit or push was performed.
