# MindMirror 🪞

MindMirror is an AI safety and guardrail system designed to audit, detect, and classify conversational manipulation tactics in real-time dialogs.

---

## 📂 Project Structure

```text
Mind-Mirror/
├── taxonomy/
│   └── taxonomy.md          # Canonical definition of manipulation tactics (0–5 Priority, 6–9 Extended)
├── data/
│   └── schema.py            # Pydantic data models for tactics, turns, benchmarks, and annotations
├── annotation/
│   ├── pilot_dataset.json   # 20 curated pilot test examples with dialogue context & ground truth
│   ├── labeler.py           # Interactive CLI labeling & Cohen's Kappa agreement evaluation tool
│   ├── results/             # Saved annotator outputs
│   └── README.md            # Detailed pilot testing instructions
├── generation/              # Synthetic dialogue generation pipeline (Phase 2)
├── models/                  # Manipulation classifiers & prompt-based evaluators (Phase 3)
├── api/                     # Backend API services (FastAPI) (Phase 4)
└── ui/                      # Interactive frontend dashboard (Phase 5)
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
