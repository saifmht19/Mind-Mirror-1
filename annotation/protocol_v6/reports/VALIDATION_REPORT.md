# Annotation protocol validation report

## Scope and evidence

Checked `annotation/pilot_dataset.json`, `annotation/results/pilot_team_member_a.json`, `annotation/results/pilot_team_member_b.json`, `docs/spec_v6_multilabel.md`, and the integrity notes in `README.md`. The pilot contains 20 unique items, 45 represented context-plus-target turns (21 user, 24 assistant), with all source structures passing legacy JSON checks. Each stored annotation file has 20 / 20 records matching the pilot IDs.

## Findings

- The stored A/B outputs are legacy single-label records (`chosen_tactic` 0–5). The v6 protocol requires multi-label assistant turn sets, primary tactic, pressure 0–3, user refusal flags, evidence spans, conversation escalation/onset, honest-persistence labels, and label-source/version metadata. All these v6 annotation fields are absent from the 40 stored outputs.
- A and B agree on 19/20 target-message labels (95.0%, Cohen's κ=0.9398). They disagree on `PILOT-18`. This is a recomputation over the stored legacy records, not the README's all-assistant-turn AI–AI statistic and not human IAA.
- `pilot_dataset.json` calls its `gold_label` values ground truth, but the v6 integrity notes require that labels be treated as unverified/AI-assisted silver until independently validated. A/B identity values `team_member_a/b` do not identify AI providers or human reviewers; provider, model/version, and prompt hashes are missing.
- The README reports aggregate adjudication findings (including 12 unresolved issues, 91.2% AI–AI agreement, κ=.852, 80% exact tactic-set agreement, and onset within one turn for 9/16), but no adjudicated JSON or issue-level report is present in the checked files. The stored files contain only one target label per pilot item, so those full-turn aggregates cannot be reproduced here.
- The 12 unresolved issues remain individually unclassified. The queue records 12 aggregate slots, with no invented IDs or labels. The canonical README's proposed triage is: (a) source-internal contradiction, (b) unsupported/unverifiable fictional claim, or (c) other/unclear. To classify an issue, the original issue text, conversation/turn, adjudicator judgment, source evidence, and provenance are required. Do not equate any of the 20 pilot items with the 12 issues without source links.
- Potential content claims (e.g., countdowns, scarcity, viewer counts, health statements) cannot be confirmed as true/false from this synthetic pilot alone. No external fact checking or label repair was performed. If scenario-author metadata is missing, preserve uncertainty.

## Canonical decisions in frozen protocol `v6.1.0`

The protocol and schema resolve the README's legacy single-label instructions in favor of the canonical v6 multi-label rules. It retains the v6 tactic names and primary-label precedence, requires source-backed half-open spans, preserves each annotator/adjudicator artifact, and defines AI outputs as silver. Escalation remains: any assistant turn after a prior user refusal with pressure 2 or 3; onset is the first such turn. It does not mean rising pressure. Pressure anchors are explicitly operationalized in the new version because the v6 spec supplies the 0–3 range but not anchors.

## Validation status

Legacy pilot structure: PASS. Canonical v6 annotation data in stored pilot outputs: **not available**. Adjudicated full-conversation annotation: **not found**. Twelve issue details: **not found; human/source review required**. No original source or annotation file was edited.

See `docs/annotation_protocol_v6.md`, `annotation/schema/mindmirror_v6_annotation.schema.json`, `annotation/validate_v6_annotations.py`, `legacy_pilot_validation.json`, and `unresolved_issue_recovery_queue.csv`.
