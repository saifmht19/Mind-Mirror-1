# MindMirror

**Explainable, context-aware detection of manipulation in AI conversations.**

AI assistants tuned for engagement can nudge people with flattery, false urgency and guilt, most often at the moment someone tries to leave. That pressure builds across several turns and is invisible to filters that read one message at a time. MindMirror reads the whole conversation, names the tactics it finds, ties every finding to the exact words that support it, and tracks how risk escalates turn by turn.

> Research prototype for a college AI-safety project. Every score is a model prediction, not a verdict. The datasets are synthetic and their labels are unverified.

**Research status:** the v6 synthetic dataset and its AI-assisted pilot are *not* human-verified gold-standard data, and blind annotation under the ratified v6.2.0 protocol is in progress. Read [v6 annotation integrity and research readiness](docs/research/V6_RESEARCH_STATUS.md) before using any labels, results or splits. The research corpus and annotation pilot are kept out of this public repository.

## What's inside

| Page | What it shows |
|---|---|
| **Why it matters** | Sourced real-world evidence: companion-app research, FTC and EU action, court cases |
| **Live simulation** | Chat with "Nova", a local fictional assistant, while MindMirror analyses each reply; or replay saved runs |
| **Side-by-side** | One message to a respectful assistant and a retention-optimised one, scored blind |
| **Context experiment** | The same replies judged alone vs in context, from a single refusal to full conversations |
| **Conversation analyzer** | Paste or edit any conversation and analyse it |
| **Dataset lab** | Batch-analyse JSON/JSONL datasets and export predictions |
| **Research & methodology** | Six-tactic taxonomy, evidence rules and the risk formula |

**Presentation mode** (button in the top bar, or `/#present`) runs a five-step guided tour using saved results only, so it works without the local model or the detection service.

## Quick start (Windows, PowerShell)

Requirements: Python 3.12+, Node 22.12+, a Gemini API key, and [Ollama](https://ollama.com) for the live simulator.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env        # then set GEMINI_API_KEY in .env
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

In a second terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Open <http://127.0.0.1:5173>. API docs: <http://127.0.0.1:8000/docs>.

For the live simulator, create the local model once:

```powershell
ollama pull llama3.2:3b
ollama create mindmirror-simulator -f simulator/Modelfile
```

## How it works

1. **Simulate.** A local Llama 3.2 model plays Nova in fictional retention scenarios (ending a chat, downgrading a plan, leaving an app), alongside a respectful control. Behaviour comes from prompt configuration only, with fixed safety boundaries, consent and a `STOP DEMO` exit.
2. **Detect.** Only the visible conversation is sent to the detector (Gemini), which predicts per-turn tactics, pressure (0–3) and explicit refusals.
3. **Explain.** Every tactic must cite an exact text span; invalid output is rejected and retried.
4. **Measure.** An open, deterministic running-risk formula tracks escalation and weights pressure that follows a refusal more heavily.

## Experiments

Saved results are served by the backend and shown on the Context experiment page. To re-run them (this uses detector quota):

```powershell
.\.venv\Scripts\python.exe evaluation\context_experiment.py      # ~100 requests
.\.venv\Scripts\python.exe evaluation\multiturn_experiment.py    # ~200 requests, --resume to continue
```

The multi-turn experiment samples conversations from the research corpus, which is not in this repository, so its saved results are kept locally too.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-research.txt   # full suite also covers the ML pipeline
.\.venv\Scripts\python.exe -m pytest -q
cd frontend; npm test; npm run build
```

## Repository layout

```text
backend/      FastAPI app: detector service, risk scoring, simulator, saved demos and experiments
frontend/     React + TypeScript dashboard
simulator/    Ollama Modelfile for the local fictional assistant
evaluation/   experiment and diagnostic scripts
data/         synthetic conversations, diagnostic suite, dataset tooling and audits
annotation/   annotation pilot and labelling tools
generation/   synthetic dialogue generation
models/       earlier ML pipeline (TF-IDF baseline, context model, refusal detector)
legacy/       superseded v1 API, static demo and first Gemini prototype
scripts/      small utilities
tests/        backend and pipeline tests
docs/         guides and the research record
```

## Documentation

- [Application guide](docs/APP_GUIDE.md): setup, architecture, API contracts, scoring and troubleshooting
- [College demo guide](docs/COLLEGE_DEMO.md): live simulator setup and demo script
- [v6 annotation integrity and research readiness](docs/research/V6_RESEARCH_STATUS.md): research status, pilot findings and the pre-publication checklist
- [Research pipeline (v1–v5)](docs/research/RESEARCH_PIPELINE.md): earlier taxonomy, annotation, ML models and v1 API
- [v6 multi-label specification](docs/research/spec_v6_multilabel.md)

## Privacy and limits

Detector keys stay on the backend. Conversations are sent to the detection service only when analysed, and no conversation history is stored on the server. The local simulator never sees research data. Risk parameters are untuned defaults, detector judgements can be wrong, and a low score does not certify a conversation as safe.
