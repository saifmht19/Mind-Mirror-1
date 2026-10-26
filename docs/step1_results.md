# Step 1 results: refusal detector and paired diagnostic suite

Branch: `v5-step1-honest-persistence`. Date: 26 October 2026. Spec reference: MindMirror spec v5, sections 8, 9, 11.2.

## What changed
- `models/refusal.py`: stricter refusal detector. "No problem", "no worries", "stop the timer", "skip to the summary", and "can I cancel...?" are no longer refusals. A bare "No" counts only when it answers an offer.
- `models/train_context_model.py`: uses the new detector (`refusal_fn` can be overridden to compare against the legacy regex).
- `data/diagnostic/`: 50-record paired diagnostic suite (20 matched honest/pressure pairs plus 10 non-refusal contexts). **Test-only, drafted by Claude, not yet human verified.**
- `evaluation/diagnostic_suite.py`: compares baseline, context+legacy refusal, and context+new refusal on the suite.
- `tests/test_refusal.py`: 7 tests.

## Reproduced baseline (regenerated data, 696 training samples)
| Model | Validation acc | Validation macro-F1 | Gold benchmark (n=20) acc |
|---|---|---|---|
| TF-IDF + LR baseline | 63.6% | 58.8% | 70.0% |
| Context model (legacy refusal) | 82.9% | 79.3% | 65.0% |

The context model wins on validation and loses on the 20-item benchmark. The benchmark is tiny, so the direction is a flag, not a finding.

## Data findings
- Real ChatbotManip rows have 10-18 prior turns. Generated and hand-written rows have 1-2. Tactic 2 (Urgency) exists only in the short-context data (72 rows, all generated).
- The legacy refusal regex fires on 22% of ChatbotManip rows mapped to Repeated Pressure, so most of those 64 rows are not pressure after refusal. The "Reciprocity Pressure -> 5" mapping needs review.
- The offline generator yields 83 unique rows from 120 requested after exact-match dedup (27 templates plus 5 prefixes).

## Diagnostic suite results (5 seeds, suite n=50, test-only)
| Model | Pressure recall | Honest/respectful correct | Non-refusal correct | Pair accuracy |
|---|---|---|---|---|
| Baseline (text only) | 0.24 | 0.70 | 0.60 | 0.10 |
| Context + legacy refusal | 0.85 | 0.12 | 0.30 | 0.10 |
| Context + new refusal | 0.89 | 0.00 | 0.42 | 0.00 |

Refusal feature alone on the suite: legacy precision 0.81 / recall 0.95; new 1.00 / 1.00. **The new detector was written alongside the suite, so the perfect score is circular and does not show generalization.**

## Conclusions
1. The better refusal feature makes the classifier worse on honest follow-ups: in training, "refusal present" almost always means Repeated Pressure, so the model learns "refusal -> pressure".
2. Adding 10 suite pairs to training (held-out pair split, 10 splits) lifts honest-correct only to about 0.13. A TF-IDF model with a refusal flag cannot tell an honest follow-up from a re-pitch.
3. Step 2 must add hundreds of human-verified honest-persistence and respectful-acceptance examples to training (kept separate from this test-only suite), and add a feature or model that sees whether the reply re-pushes the declined offer.

## Not yet done
- Human verification of the suite (two reviewers per record).
- Fixing the ChatbotManip mapping (spec section 7.2).
- Group-aware splits, DeBERTa, escalation scorer.
