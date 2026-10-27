# Evaluation preparation utilities

This package prepares examples, targets, metrics, and run provenance. It does not fit models, download weights, call APIs, or train.

## Contract boundary

`evaluation.data.AnnotationContract` requires the owner to inject the taxonomy names. Its current default field mapping is an adapter boundary, not a second source of taxonomy truth. Track A owns the frozen annotation protocol and machine-readable schema; compatibility should be checked against that deliverable before use. The loader fails closed for unknown tactic values and never converts missing labels to negative labels.

Records are one JSON object per JSONL line with an ordered `turns` list. For each assistant turn, preparation emits the target assistant turn and at most `k` preceding turns, where `k` is one of `0, 2, 4, 6`. Context turns and targets are role-marked. `[REFUSAL]` is inserted only for an explicitly annotated refusal in a preceding user turn. For `k=0`, the model input contains only the target assistant turn.

The provisional adapter looks for per-assistant-turn `tactic_set`, `primary_tactic`, and `pressure_level_0_3`, and per-user-turn `user_refusal.refusal`, plus optional conversation-level `conversation_annotation.escalating` and `onset_turn_index`. These names must be reconciled with Track A's final contract. Empty tactic sets are represented as all-zero multi-hot targets; null tactic sets remain unknown (`None`). The taxonomy itself is never hard-coded here.

Conversation-level escalation uses the canonical v6 condition: any assistant turn after a user refusal with pressure 2 or 3. Explicit conversation annotations are preferred. Derivation occurs only when the required refusal/pressure evidence is known; incomplete evidence returns unknown rather than a negative. The configurable threshold is an adapter parameter and must remain 2 unless Track A documents an approved canonical change.

## Metrics and model interfaces

`evaluation.metrics.multilabel_metrics` reports per-tactic precision/recall/F1 and support, macro scores over classes with gold support, micro scores, sample-averaged Jaccard, and exact-set accuracy. Zero-denominator precision/recall values are zero; class supports are included so the convention is visible.

`evaluation.model_interfaces` declares inference-only protocols for TF-IDF, single-turn DeBERTa, context DeBERTa, refusal-conditioned classification, and conversation escalation scoring. There are no concrete estimator implementations in this preparation package. `evaluation.experiment` hashes canonical configuration and records seed, input SHA-256, source revision, runtime, and `training_started: false`.

## Tests

```powershell
python -m unittest tests.test_evaluation_prep -v
```

All fixtures are synthetic and contain no MindMirror conversation text or labels.
