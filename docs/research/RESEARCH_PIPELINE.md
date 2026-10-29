# Research pipeline (v1–v5)

> Historical record of the research tooling that preceded the v6 web app. The scripts still run and are covered by the test suite. Install their extra dependencies with `pip install -r requirements-research.txt`. For the current app, see the [README](../../README.md).

## Original overview

MindMirror is an AI safety and guardrail system designed to audit, detect, and classify conversational manipulation tactics in real-time dialogs.

---

## Layout of the research tooling

```text
docs/research/taxonomy_v1.md   original single-label taxonomy (0–5 priority, 6–9 extended)
data/schema.py                 Pydantic models for tactics, turns, benchmarks and annotations
annotation/                    20-example pilot, CLI labeller with Cohen's kappa, reviewer sheets
generation/                    synthetic dialogue generation (pairs, urgency, conversation batches)
models/                        TF-IDF baseline, context model, refusal detector, v5 demo model
legacy/api/                    v1 REST API (FastAPI) serving the v5 demo model
legacy/ui/                     v5 static demo page
evaluation/diagnostic_suite.py paired diagnostic evaluation of the ML models
```

---

## 🎯 Priority Taxonomy (v1 Scope)

MindMirror enforces a **single dominant tactic per message**:

- `0: Neutral` — Helpful, honest information or reasonable follow-up with no emotional pressure.
- `1: Guilt-tripping` — Frames user refusal/disagreement as personal failing, betrayal, or fault.
- `2: Excessive Urgency` — Invents/exaggerates deadlines or scarcity to rush decisions.
- `3: Fear-based Persuasion` — Exaggerates negative consequences to provoke anxiety rather than inform.
- `4: Excessive Flattery` — Unearned or disproportionate praise to lower user resistance.
- `5: Repeated Pressure After Refusal` — Re-raises a previously declined request without respecting refusal.

---

## 🚀 Quick Start (Pilot Annotation & Validation)

### 1. View Taxonomy Cheat Sheet
```bash
python annotation/labeler.py --list-tactics
```

### 2. Run Interactive Labeling Session
```bash
python annotation/labeler.py --name YourName
```

### 3. Evaluate Inter-Annotator Agreement (Cohen's Kappa & % Agreement)
```bash
python annotation/labeler.py --compare annotation/results/pilot_team_member_a.json annotation/results/pilot_team_member_b.json
```

### 4. Evaluate Against Ground Truth
```bash
python annotation/labeler.py --evaluate-gold annotation/results/pilot_team_member_a.json
```

---

## 🧠 Phase 3: Machine Learning & Context Models

MindMirror features a dual-stage classification pipeline:

1. **Baseline Model (`models/train_baseline.py`)**: Word + char n-gram TF-IDF vectorizer paired with multinomial Logistic Regression.
2. **Conversational Context Model (`models/train_context_model.py`)**: Augments lexical features with dialogue-level refusal dynamics:
   - User refusal regex detectors (`"no thanks"`, `"not interested"`, `"stop"`)
   - Turn counts & distance since refusal
   - Cross-turn push flags & persistence metrics
   - Output calibrated probabilities & automated human-readable explanations

### Train & Evaluate:
```bash
# Baseline evaluation
python models/train_baseline.py

# Context-aware model training & saving artifacts
python models/train_context_model.py
```

---

## ⚡ Phase 4: REST API Backend (FastAPI)

The backend provides high-performance HTTP endpoints for real-time guardrail evaluation and batch conversation auditing.

### Start the Server:
```bash
python -m uvicorn legacy.api.main:app --reload --port 8000
```
- Interactive Swagger UI: `http://localhost:8000/docs`
- Redoc Documentation: `http://localhost:8000/redoc`

### Key Endpoints:

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/health` | Service health status & model loading info |
| `GET` | `/api/v1/tactics` | All 6 priority tactics with formal definitions |
| `POST` | `/api/v1/detect` | Analyse single chatbot message (with optional context) |
| `POST` | `/api/v1/audit` | Audit full multi-turn conversation & compute manipulation score |

### Example Detection Request:
```bash
curl -X POST "http://localhost:8000/api/v1/detect" \
  -H "Content-Type: application/json" \
  -d '{
    "target_message": "Are you completely sure? You really cannot pass up this discount before midnight.",
    "context": [
      {"speaker": "assistant", "text": "Would you like to purchase our yearly plan?"},
      {"speaker": "user", "text": "No, I am not interested."}
    ]
  }'
```

### Run Automated API Tests:
```bash
python -m unittest tests/test_api.py
```

---

## Step 1 (spec v5): refusal detector and paired diagnostic suite

- `models/refusal.py` — stricter refusal detection; run `python -m unittest tests/test_refusal.py`.
- `data/diagnostic/diagnostic_suite_v0.jsonl` — 50 paired test-only records (not human verified yet). Rebuild with `python data/diagnostic/build_diagnostic_suite.py`.
- `python evaluation/diagnostic_suite.py` — compares models on honest vs pressure follow-ups. Results and caveats: [step1_results.md](step1_results.md).
- Install dependencies with `pip install -r requirements-research.txt`.

## Running the demo (v5 demo model)

```bash
pip install -r requirements-research.txt
python models/train_demo_model.py          # optional: retrain; artifacts are already in models/artifacts/
python -m uvicorn legacy.api.main:app --port 8000
# open http://localhost:8000/demo
```

The demo page scores each assistant turn and shows a refusal-conditioned risk curve
(`models/escalation.py`). Caveats: training banks and the diagnostic suite are Claude-written and
not human verified; the escalation parameters are untuned defaults; the diagnostic numbers are
anecdotal, not paper results. Tests: `python -m unittest discover -s tests -t .`
