# Evaluation preparation utilities

This package prepares examples, targets, metrics, and run provenance. It does not fit models, download weights, call APIs, or train.

## Contract boundary

`evaluation.data.AnnotationContract.from_json_schema()` reads the tactic inventory from Track A's versioned JSON Schema. The loader joins the source `turns` array with the aligned `turn_annotations` array and fails closed if array lengths, turn indices, or speakers disagree. Taxonomy names are never defined by this package. Unknown tactic values remain errors; null labels remain unknown rather than negative labels. The canonical empty tactic set is an all-zero multi-hot vector with primary `neutral`.

For each assistant turn, preparation emits that target turn plus at most `k` preceding turns, where `k` is one of `0, 2, 4, 6`. Context turns and targets are role-marked. `[REFUSAL]` is inserted only for an explicitly annotated refusal on a preceding user turn. At `k=0`, the model input contains only the target assistant turn. The input excludes annotations, generator metadata, and provenance fields. Prepared targets retain turn and conversation label source plus annotator type so AI/silver labels can be distinguished from human/adjudicated labels.

The adapter follows Track A's current schema v1.0.0 fields: per-turn `refusal`, `tactic_set`, `primary_tactic`, `pressure_level`, and `label_source`; conversation-level `escalating`, `onset_turn_index`, and `label_source`. It does not replace Track A's semantic span validator. Tactic/refusal character spans remain available in source records for separate validation and error analysis.

Conversation-level escalation uses the canonical v6 condition: any assistant turn after a user refusal with pressure 2 or 3. Explicit conversation labels are preferred. Derivation occurs only when the required refusal/pressure evidence is known; incomplete evidence returns unknown rather than a negative. Pressure threshold 2 is fixed in this loader to avoid silently changing the operational definition.

## Metrics and model interfaces

`evaluation.metrics.multilabel_metrics` reports per-tactic precision/recall/F1 and support, macro scores over classes with gold support, micro scores, sample-averaged Jaccard, and exact-set accuracy. Zero-denominator precision/recall values are zero; class supports are included so the convention is visible.

`evaluation.model_interfaces` declares inference-only protocols for TF-IDF, single-turn DeBERTa, context DeBERTa, refusal-conditioned classification, and conversation escalation scoring. There are no concrete estimator implementations in this package. `evaluation.experiment` hashes canonical configuration and records seed, input SHA-256, source revision, runtime, and `training_started: false`.

## Tests

```powershell
python -m unittest tests.test_evaluation_prep -v
```

All fixtures are synthetic, schema-aligned dummy examples and contain no MindMirror conversation text or labels.
