# Track C — scenario grouping and leakage prevention

## Status

Implemented conservative candidate generation and deterministic split utilities. All scenario proposals remain unconfirmed. No official train/validation/test manifest was produced. The original raw/processed conversation JSONL and previous local review files are copied only as untracked inputs in `data/conversations/audit_source/`; they are not staged or committed.

## Findings from the local 800-row collection

- Raw and cleaned sources each have 800 records. Existing domains contain 200 records each.
- Existing TF-IDF similarity file: 282 candidate pairs, covering 289 unique conversations; 52 scores fall in `[0.55, 0.75)`, 9 in `[0.75, 0.90)`, and 221 in `[0.90, 1.00]`. Similarity is lexical evidence only.
- The reviewed candidate table has 555 distinct pairwise edges: 348 have at least two metadata signals, 157 have only one metadata signal, and 50 have conflicting signals. Every edge remains pending.
- 408 records occur in at least one edge; 392 have no candidate edge.
- On normalized text, no exact whole-conversation duplicate groups were found. There are 99 groups (239 rows) with identical normalized openings; these may be matched variants or reused templates and must be grouped only after scenario review.
- The pipeline proposes 54 unconfirmed components covering 200 records, using corroborated, nonconflicting `group_id`, `pair_id`, and `situation` signals. These are proposals, not confirmed scenario groups.

### Investigation of the 50 conflict edges

All 50 are in Education & tutoring and originate from the declared `education_all_merged_plus_50(1).jsonl` source. Each edge is linked only by a shared `pair_id`; neither row has a `group_id`, and the two rows have different `situation` values. There are 50 distinct pair IDs and 33 distinct situation pairs. The evidence is contradictory for scenario identity, so none of these pairs enters a proposed group. The pair IDs may denote paired examples rather than common scenario identity; source documentation or human review is needed to decide.

No relationship is inferred from `card_id`, manipulation labels, or writer-intended tactics. TF-IDF-only edges never create group components.

## Implementation

`data/conversations/scenario_grouping.py` emits:

- `scenario_relationship_review.csv`: edge evidence, conflicts, pending decision, and reviewer fields.
- `proposed_scenario_groups.csv`: stable proposal IDs from corroborated metadata, explicitly marked unconfirmed.
- `grouping_coverage.csv`: one row per conversation.
- `grouping_summary.json` and `GROUPING_REPORT.md`: aggregate audit results.

`assign_group_splits()` hashes an explicit `verified_scenario_id` (configurable) and seed to assign deterministic ratios. Rows missing the verified key remain `unassigned`. `find_split_leakage()` identifies any verified group found in multiple split assignments. These helpers do not generate or freeze official splits and do not stratify for an experiment.

## Reproduce

After placing authorized local input files in the requested locations, run:

```powershell
python data/conversations/scenario_grouping.py --master <cleaned.jsonl> --similarity <scenario_similarity_candidates.csv> --output-dir <derived-dir>
python -m unittest tests.test_scenario_grouping -v
```

The local dataset used for this audit is untracked and excluded from this branch. Counts above summarize only that local snapshot. The input dataset is not included in this branch.

## Remaining human decisions

1. Decide whether the 50 education pair-ID collisions are unrelated scenarios, deliberate matched pairs across different situations, or bad metadata.
2. Review all 555 edges and 54 proposed components, including edge cases with shared broad `situation` values.
3. Resolve or explicitly leave the 392 unlinked records ungrouped.
4. Only after review, provide verified scenario IDs to the split helper. Keep respectful/manipulative variants in the same scenario group; the grouping code never reads labels to determine identity.

