# MindMirror v6 Application Implementation Plan

> For agentic workers: use superpowers:executing-plans task by task.

Goal: Deliver a local Gemini-powered explainable multi-turn detector without changing research data.
Architecture: Add an independent FastAPI service and React dashboard. Reuse the existing Gemini model configuration, v6 taxonomy and risk recurrence; preserve the legacy API and models.
Tech Stack: Python 3.12, FastAPI, Pydantic, google-genai; Node 22+, React, TypeScript, Vite, Tailwind, Recharts, Lucide.
Spec: User master prompt attached on 2026-10-29; docs/spec_v6_multilabel.md sections 7.4–7.5.

## Global Constraints
- Six canonical tactic strings; neutral is an empty set.
- Evidence offsets are zero-based half-open Python Unicode character offsets.
- Model responses are predictions, never human-verified labels.
- No secrets or private conversations in logs; no automatic persistence.
- Local-only development; retain all existing user changes and datasets.

## Review Focus
- Unicode evidence offsets must render correctly including emoji.
- Malformed model responses must fail closed after bounded retries.
- Dataset metadata and IDs must survive partial batch failures and export.
- Retrying 429/503 must be bounded; large batches require explicit confirmation.
- Editing messages must invalidate old results.

## Task 1: Contracts, evidence validation and escalation
Files: backend/schemas.py, backend/escalation.py; tests/test_v6_app.py.
Produces: Conversation, Prediction, validate_prediction(conversation, prediction), score(prediction).
- [x] Write tests rejecting unsupported spans/labels/missing turns and checking neutral, rising, post-refusal risk.
- [x] Run pytest to establish failing behavior.
- [x] Implement strict contracts and deterministic bounded recurrence.
- [x] Run targeted tests; expected all pass.

## Task 2: Gemini, API and dataset adapter
Files: backend/config.py, backend/gemini.py, backend/service.py, backend/datasets.py, backend/main.py, backend/examples.py.
Consumes Task 1 models; produces GET health/examples, POST analyze/batch/preview and JSONL streaming.
- [x] Add tests for validation retries, API failures, health, input limits, metadata preservation and mixed batch outcomes.
- [x] Run tests first; implement structured Gemini calls with separate system instructions, timeout and concurrency bounds.
- [x] Run mocked backend tests; expected all pass.

## Task 3: Dashboard and dataset UI
Files: frontend/package.json, frontend/src/{App.tsx,types.ts,index.css,main.tsx}, frontend/vite.config.ts.
Consumes API contracts, renders offset-derived evidence and real charts.
- [x] Add frontend behavioral tests for Unicode highlighting, parsing, edits and failure states; establish failures.
- [x] Implement responsive dark dashboard, editor, results, dataset selection/export and research page.
- [x] Run frontend tests and production build; expected pass and exit 0.

## Task 4: Verification and handoff
Files: README.md, docs/APP_GUIDE.md, .env.example, requirements-app.txt.
- [x] Run full existing and new test suite, backend HTTP smoke test, browser interactions and one small live Gemini test if credentials permit.
- [x] Document actual results, unresolved environment limits, structure, scoring parameters and demo script.

## Execution ledger
Ruling: execute natively without intermediate approval gates because the user explicitly requested autonomous implementation. Keep the current checkout on codex/mindmirror-v6-app to retain existing untracked inputs. No commits or dataset mutation needed.


Task 1: complete — strict schemas, exact Unicode evidence checks and independent scorer; tests pass.
Task 2: complete — official SDK integration, bounded retries, typed API responses, streaming batch and provenance adapter; tests pass.
Task 3: complete — dashboard, editor, real charts, evidence ledger, dataset lab, research page; 7 frontend tests and production build pass.
Task 4: complete — full suite 90 passed; pip check and npm audit clean; live Gemini and browser full-conversation analysis/export verified.
Ruling: no persistent history or six-label benchmark metrics, because no suitable verified multi-label ground truth was identified and privacy/simplicity take precedence.
Ruling: do not commit existing user work; final changes remain reviewable in the current working tree.
Review fixes: preserve Dataset Lab across navigation; protect shared request cancellation; disable Inspect during another analysis; preserve annotated source records; reject unapproved browser POST origins.
