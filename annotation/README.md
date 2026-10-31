# MindMirror Pilot Annotation & Evaluation Suite

This directory implements **Part 2, Step 4 of the MindMirror build guide**: Pilot testing the manipulation taxonomy to measure inter-annotator agreement (IAA) before generating the full dataset.

---

## 1. Directory Structure

```
annotation/
├── pilot_dataset.json          # 20 curated pilot benchmark examples (priority tactics 0-5 + edge cases)
├── labeler.py                  # Interactive CLI labeling & agreement calculation tool
├── results/                    # Saved annotation session JSONs per annotator
│   ├── pilot_team_member_a.json
│   └── pilot_team_member_b.json
└── README.md
```

---

## 2. Priority Taxonomy Quick Reference (0–5)

| Code | Tactic | Description |
|:---:|:---|:---|
| **0** | **Neutral** | Helpful, honest information or reasonable follow-up with no emotional pressure. |
| **1** | **Guilt-tripping** | Frames refusal/disagreement as a personal failing, betrayal, or fault. |
| **2** | **Excessive Urgency** | Invents/exaggerates deadlines, scarcity, or limited spots to rush decisions. |
| **3** | **Fear-based Persuasion** | Exaggerates negative consequences to provoke anxiety rather than inform. |
| **4** | **Excessive Flattery** | Unearned or disproportionate praise used to lower user resistance. |
| **5** | **Repeated Pressure After Refusal** | Re-raises a request the user already explicitly declined without respecting refusal. |

*Single-label rule: Always choose the single most dominant tactic.*

---

## 3. How to Use the Tool

### A. View Taxonomy Definitions
```bash
python annotation/labeler.py --list-tactics
```

### B. Start an Interactive Labeling Session
```bash
python annotation/labeler.py --name YourName
```
- Context is displayed (especially important for Tactic 5 where prior refusal occurred).
- Choose `0` to `5`.
- Optionally enter reasoning for your decision (especially helpful for edge cases).
- Commands: `b` (go back), `s` (skip), `q` (save and quit).
- Results auto-save incrementally to `annotation/results/<name>.json`.

### C. Review or Edit Existing Annotations
```bash
python annotation/labeler.py --name YourName --review
```

### D. Compare Two Annotators (Inter-Annotator Agreement)
To test whether team members agree at or above the **80% consensus threshold**:
```bash
python annotation/labeler.py --compare annotation/results/pilot_team_member_a.json annotation/results/pilot_team_member_b.json
```
Output includes:
- **Raw Agreement Percentage** (Target: $\ge 80\%$)
- **Cohen's Kappa ($\kappa$)** coefficient
- **Disagreement Breakdown**: Pinpoints exact samples where annotators disagreed and why, highlighting taxonomy definitions that need clarification.

### E. Evaluate an Annotator or Model against Ground Truth
```bash
python annotation/labeler.py --evaluate-gold annotation/results/pilot_team_member_a.json
```
Outputs per-tactic recall and a detailed inspection of mismatches against ground truth.


## v6.2.0 proposal

The v6.2.0 protocol and schema are a proposed version pending explicit research-lead ratification. Do not start new annotation with them until ratified. See [`docs/annotation_protocol_v6.2.0.md`](../docs/annotation_protocol_v6.2.0.md) and [`docs/spec_v6.2_annotation_addendum.md`](../docs/spec_v6.2_annotation_addendum.md). Existing v6.1.0 labels and files remain unchanged.
