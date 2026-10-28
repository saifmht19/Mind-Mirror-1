# Repository cleanup inventory

Audit date: 2026-10-28. Remote baseline: `main` at `2c0db23b676b44a25ff452e2d41f983e05d863df`. Branch comparisons use GitHub's `main...<branch>` comparison at this baseline. Ahead/behind counts are relative to the merge base, not a statement that changes were reviewed or merged. File lists below are the changed paths reported by that comparison; paths are not content endorsements.

## Decisions

- **Keep:** `main`, the active `v6-annotation-contributors` branch, and `v6-protocol-freeze`. The latter has open PR [#2](https://github.com/saifmht19/Mind-Mirror-1/pull/2). Contributors are annotating; do not reset, edit, merge, or delete their branch. Do not change the ratified protocol in cleanup work.
- **Preserve for provenance and review:** `v5-paper-skeleton`, `v6-evaluation-prep`, and `v6-scenario-grouping`. Paper bibliography content is unique; evaluation-prep and scenario-grouping content matches files now on main byte-for-byte, but their feature commits remain outside main ancestry.
- **Preserve as historical experiment refs pending archive/owner confirmation:** `v5-demo-model`, `v5-step1-honest-persistence`, `v5-step2-paired-data`, `v6-multilabel-plan`, `v6-scenario-cards`, and `v6-schema-dismissing-choice`. Their compared commits are shared with other refs, but their trees retain legacy experiment files and the branches provide navigable provenance.
- **Do not remove data or old schema files in this cleanup.** Existing public main already tracks the legacy `annotation/pilot_dataset.json` and two legacy reviewer result JSON files. They predate this change and are marked historical; this PR adds no conversation text, annotation outputs, or manifests.
- **Archive proposal only:** after each artifact has been reviewed, preserve obsolete experiments under `archive/legacy-v1-v5/` and `archive/v6-experiments/` (or keep their source branches as the archive). Nothing is moved or deleted by this PR. Do not copy old schemas into the canonical v6 protocol directory.

## Branch-by-branch audit

The compared commit lists and changed paths are exact for this snapshot. A commit described as “shared” is also reachable from at least one other listed remote branch.

| Branch (HEAD) | Ahead / behind | Commits unique to main comparison | Changed paths |
|---|---:|---|---|
| `v5-demo-model` `10fc735ad61d03f1a73cb0f0d4c1c1e9d62fe289` | 3 / 7 | `22c3a00a`, `eb090cc3`, `10fc735a` (all shared with later refs) | `README.md`; `annotation/review/reviewer_A.csv`, `annotation/review/reviewer_B.csv`, `annotation/review_sheet.py`; `api/main.py`; `data/diagnostic/build_diagnostic_suite.py`, `data/diagnostic/diagnostic_suite_v0.jsonl`, `data/import_chatbotmanip.py`, `data/pairs/build_pair_bank.py`, `data/pairs/build_tactic_bank.py`, `data/pairs/pair_bank_v0.jsonl`, `data/pairs/tactic_bank_v0.jsonl`; `docs/step1_results.md`, `docs/step2_notes.md`; `evaluation/diagnostic_suite.py`; `generation/generate_pairs.py`; `models/artifacts/demo_model.joblib`, `models/artifacts/demo_model_calibrator.joblib`, `models/artifacts/demo_model_metrics.json`, `models/demo_model.py`, `models/escalation.py`, `models/inference.py`, `models/refusal.py`, `models/train_context_model.py`, `models/train_demo_model.py`; `requirements.txt`; `tests/test_escalation_and_demo.py`, `tests/test_refusal.py`, `tests/test_step2_tools.py`; `ui/index.html`. |
| `v5-paper-skeleton` `c2a19c3f02d8fcf43cacb02c310c649d945afc04` | 3 / 7 | `22c3a00a`, `eb090cc3` shared; `c2a19c3f` unique (bibliography) | `README.md`; `annotation/review/reviewer_A.csv`, `annotation/review/reviewer_B.csv`, `annotation/review_sheet.py`; `data/diagnostic/build_diagnostic_suite.py`, `data/diagnostic/diagnostic_suite_v0.jsonl`, `data/import_chatbotmanip.py`; `docs/step1_results.md`, `docs/step2_notes.md`; `evaluation/diagnostic_suite.py`; `generation/generate_pairs.py`; `models/refusal.py`, `models/train_context_model.py`; `paper/refs.bib`; `requirements.txt`; `tests/test_refusal.py`, `tests/test_step2_tools.py`. |
| `v5-step1-honest-persistence` `22c3a00a1ada8404f53b72fffd1c4bace037a630` | 1 / 7 | `22c3a00a` shared by seven other refs | `README.md`; `data/diagnostic/build_diagnostic_suite.py`, `data/diagnostic/diagnostic_suite_v0.jsonl`; `docs/step1_results.md`; `evaluation/diagnostic_suite.py`; `models/refusal.py`, `models/train_context_model.py`; `requirements.txt`; `tests/test_refusal.py`. |
| `v5-step2-paired-data` `eb090cc344cad5e4ca95cd81ba37e74fde1f10bf` | 2 / 7 | `22c3a00a`, `eb090cc3` shared by later refs | `README.md`; `annotation/review/reviewer_A.csv`, `annotation/review/reviewer_B.csv`, `annotation/review_sheet.py`; `data/diagnostic/build_diagnostic_suite.py`, `data/diagnostic/diagnostic_suite_v0.jsonl`, `data/import_chatbotmanip.py`; `docs/step1_results.md`, `docs/step2_notes.md`; `evaluation/diagnostic_suite.py`; `generation/generate_pairs.py`; `models/refusal.py`, `models/train_context_model.py`; `requirements.txt`; `tests/test_refusal.py`, `tests/test_step2_tools.py`. |
| `v6-annotation-contributors` `b05dcb68d450646b7b18b75ddd942e87e0fee612` | 31 / 7 | 31 commits, including inherited v5/v6 foundation plus contributor handoff, ratification sync, scoped-sharing records, postprocessor, and documentation. Active; protect. | `README.md`; `annotation/requirements-v6-validation.txt`, `annotation/review/reviewer_A.csv`, `annotation/review/reviewer_B.csv`, `annotation/review_sheet.py`; `api/main.py`; all contributor files: `contributor_annotation/CLAUDE_PROMPT.md`, `GEMINI_PROMPT.md`, `RAW_MODEL_OUTPUT_CONTRACT.md`, `READINESS_BLOCKERS.md`, `README.md`, `V6.2_RATIFICATION_CHECKLIST.md`, `assemble_annotation_chunks.py`, `compare_annotations.py`, `distribution_manifest.json`, `examples/DUMMY_ONLY_NOT_DATASET.jsonl`, `examples/README.md`, `postprocess_annotations.py`, `prepare_batches.py`, `protocol/PROVENANCE.md`, `protocol/annotation_protocol_v6.2.0.md`, `protocol/mindmirror_v6_annotation.v2.schema.json`, `protocol/spec_v6.2_annotation_addendum.md`, `protocol/validate_v6_annotations.py`, `validate_batch.py`, `validate_batches.py`; `data/conversations/batch_claude_companion.jsonl`, `cards_v0.jsonl`, `claude_companion_turns.json`; v5 diagnostic/pair-bank files listed above; `data/schema.py`; `docs/pilot_batch_notes.md`, `docs/spec_v6_multilabel.md`, `docs/step1_results.md`, `docs/step2_notes.md`; `evaluation/diagnostic_suite.py`; `generation/__init__.py`, `generation/conversations/__init__.py`, `generation/conversations/build_batch.py`, `make_prompts.py`, `run_ollama.py`, `scenario_cards.py`, `generation/generate_pairs.py`; demo/refusal/model files listed above; `requirements.txt`; `tests/test_annotation_v6_2_protocol.py`, `test_contributor_batches.py`, `test_contributor_compare.py`, `test_conversation_batch.py`, `test_escalation_and_demo.py`, `test_postprocess_annotations.py`, `test_refusal.py`, `test_schema_v6.py`, `test_step2_tools.py`; `ui/index.html`. Note: path inventory includes a sanitized manifest and earlier public data artifacts; it does **not** establish that any private 780-batch input is present. |
| `v6-evaluation-prep` `faf3c5a3887e191b5bb1ee599820b2e86d8dd85e` | 2 / 5 | `a3a58d0c`, `faf3c5a3` unique commits | `evaluation/README.md`, `evaluation/__init__.py`, `evaluation/data.py`, `evaluation/experiment.py`, `evaluation/metrics.py`, `evaluation/model_interfaces.py`, `tests/test_evaluation_prep.py`. All seven current blobs are byte-identical to main. |
| `v6-multilabel-plan` `a55c153031245dc516dc90616ec875085722f855` | 4 / 7 | `22c3a00a`, `eb090cc3`, `10fc735a`, `a55c1530` (all shared with later refs) | `README.md`; reviewer CSVs and `annotation/review_sheet.py`; `api/main.py`; diagnostic and pair-bank paths listed above; `data/import_chatbotmanip.py`; `docs/spec_v6_multilabel.md`, `docs/step1_results.md`, `docs/step2_notes.md`; `evaluation/diagnostic_suite.py`; `generation/generate_pairs.py`; demo/refusal/model paths listed above; `requirements.txt`; demo/refusal/step2 test paths listed above; `ui/index.html`. |
| `v6-protocol-freeze` `71cbc4600e7b6eda7bec637a921bda32326d572c` | 6 / 5 | 6 protocol/schema/report commits, including explicit v6.2.0 ratification; open PR #2. Protect. | `annotation/README.md`, `annotation/examples/DUMMY_ONLY_NOT_DATASET.jsonl`, `annotation/protocol_v6/reports/VALIDATION_REPORT.md`, `legacy_pilot_validation.json`, `unresolved_issue_recovery_queue.csv`, `annotation/requirements-v6-validation.txt`, `annotation/schema/mindmirror_v6_annotation.schema.json`, `mindmirror_v6_annotation.v2.schema.json`, `annotation/validate_legacy_pilot.py`, `annotation/validate_v6_annotations.py`; contributor prompts/README/examples; `docs/annotation_protocol_v6.2.0.md`, `docs/annotation_protocol_v6.2.0_ratification_checklist.md`, `docs/annotation_protocol_v6.md`, `docs/spec_v6.2_annotation_addendum.md`, `docs/spec_v6_multilabel.md`; protocol tests. |
| `v6-scenario-cards` `2ca70fd541fb2084dc5891c7afbbaab8c6684353` | 5 / 7 | `22c3a00a`, `eb090cc3`, `10fc735a`, `a55c1530`, `2ca70fd5` (all shared with later refs) | reviewer CSVs and review tool; `README.md`, `api/main.py`; `data/conversations/cards_v0.jsonl`; diagnostic/pair-bank paths listed above; `data/import_chatbotmanip.py`; `docs/spec_v6_multilabel.md`, step notes; `evaluation/diagnostic_suite.py`; `generation/conversations/__init__.py`, `scenario_cards.py`, `generation/generate_pairs.py`; demo/refusal/model paths listed above; `requirements.txt`; demo/refusal/step2 tests; `ui/index.html`. |
| `v6-scenario-grouping` `699711eb88f14f74f7e012e82b638791b116e322` | 2 / 5 | `871b3e5d`, `699711eb` unique commits | `data/conversations/scenario_grouping.py`, `docs/scenario_grouping.md`, `tests/test_scenario_grouping.py`. All three current blobs are byte-identical to main. |
| `v6-schema-dismissing-choice` `4611c330daffe5a60742b91122d499e1345f2d7c` | 8 / 7 | 8 commits, all shared with `v6-annotation-contributors` or other v6 refs | reviewer CSVs/tool; `README.md`, `api/main.py`; companion batch files and `cards_v0.jsonl`; diagnostic/pair-bank paths listed above; schema/import files; `docs/pilot_batch_notes.md`, `docs/spec_v6_multilabel.md`, step notes; evaluation; conversation generation utilities; demo/refusal/model paths; `requirements.txt`; API/conversation/demo/refusal/schema/step2 tests; `ui/index.html`. |

For full per-commit messages and diffs, use the branch comparison links, such as [all branches](https://github.com/saifmht19/Mind-Mirror-1/branches) and [compare main to the contributor branch](https://github.com/saifmht19/Mind-Mirror-1/compare/main...v6-annotation-contributors). Compare output represents file changes from a merge base; it is not a literal current-tree file listing.

## Full branch-only commit inventory

The entries below are the complete commit lists returned by `main...<branch>` for all 11 non-main refs at the baseline above. Repeated SHAs are shared between branches; they are branch-only relative to main but not unique across the historical refs. Full SHAs and subjects are recorded to retain provenance.

### `v5-demo-model`

- [`22c3a00a1ada8404f53b72fffd1c4bace037a630`](https://github.com/saifmht19/Mind-Mirror-1/commit/22c3a00a1ada8404f53b72fffd1c4bace037a630) — feat(step1): stricter refusal detector, paired diagnostic suite, reproducible baseline
- [`eb090cc344cad5e4ca95cd81ba37e74fde1f10bf`](https://github.com/saifmht19/Mind-Mirror-1/commit/eb090cc344cad5e4ca95cd81ba37e74fde1f10bf) — feat(step2): paired-data generator, blind two-reviewer sheet, opt-in mapping v2
- [`10fc735ad61d03f1a73cb0f0d4c1c1e9d62fe289`](https://github.com/saifmht19/Mind-Mirror-1/commit/10fc735ad61d03f1a73cb0f0d4c1c1e9d62fe289) — Add demo model, escalation scorer, pair/tactic banks, demo UI and tests

### `v5-paper-skeleton`

- [`22c3a00a1ada8404f53b72fffd1c4bace037a630`](https://github.com/saifmht19/Mind-Mirror-1/commit/22c3a00a1ada8404f53b72fffd1c4bace037a630) — feat(step1): stricter refusal detector, paired diagnostic suite, reproducible baseline
- [`eb090cc344cad5e4ca95cd81ba37e74fde1f10bf`](https://github.com/saifmht19/Mind-Mirror-1/commit/eb090cc344cad5e4ca95cd81ba37e74fde1f10bf) — feat(step2): paired-data generator, blind two-reviewer sheet, opt-in mapping v2
- [`c2a19c3f02d8fcf43cacb02c310c649d945afc04`](https://github.com/saifmht19/Mind-Mirror-1/commit/c2a19c3f02d8fcf43cacb02c310c649d945afc04) — docs(paper): add verified bibliography for related work

### `v5-step1-honest-persistence`

- [`22c3a00a1ada8404f53b72fffd1c4bace037a630`](https://github.com/saifmht19/Mind-Mirror-1/commit/22c3a00a1ada8404f53b72fffd1c4bace037a630) — feat(step1): stricter refusal detector, paired diagnostic suite, reproducible baseline

### `v5-step2-paired-data`

- [`22c3a00a1ada8404f53b72fffd1c4bace037a630`](https://github.com/saifmht19/Mind-Mirror-1/commit/22c3a00a1ada8404f53b72fffd1c4bace037a630) — feat(step1): stricter refusal detector, paired diagnostic suite, reproducible baseline
- [`eb090cc344cad5e4ca95cd81ba37e74fde1f10bf`](https://github.com/saifmht19/Mind-Mirror-1/commit/eb090cc344cad5e4ca95cd81ba37e74fde1f10bf) — feat(step2): paired-data generator, blind two-reviewer sheet, opt-in mapping v2

### `v6-annotation-contributors`

- [`22c3a00a1ada8404f53b72fffd1c4bace037a630`](https://github.com/saifmht19/Mind-Mirror-1/commit/22c3a00a1ada8404f53b72fffd1c4bace037a630) — feat(step1): stricter refusal detector, paired diagnostic suite, reproducible baseline
- [`eb090cc344cad5e4ca95cd81ba37e74fde1f10bf`](https://github.com/saifmht19/Mind-Mirror-1/commit/eb090cc344cad5e4ca95cd81ba37e74fde1f10bf) — feat(step2): paired-data generator, blind two-reviewer sheet, opt-in mapping v2
- [`10fc735ad61d03f1a73cb0f0d4c1c1e9d62fe289`](https://github.com/saifmht19/Mind-Mirror-1/commit/10fc735ad61d03f1a73cb0f0d4c1c1e9d62fe289) — Add demo model, escalation scorer, pair/tactic banks, demo UI and tests
- [`a55c153031245dc516dc90616ec875085722f855`](https://github.com/saifmht19/Mind-Mirror-1/commit/a55c153031245dc516dc90616ec875085722f855) — Add spec v6: multi-label tactics (tactic set plus primary tactic)
- [`2ca70fd541fb2084dc5891c7afbbaab8c6684353`](https://github.com/saifmht19/Mind-Mirror-1/commit/2ca70fd541fb2084dc5891c7afbbaab8c6684353) — Add scenario-card builder and 800 draft cards for full-conversation dataset
- [`7751f09e5e6d3c7dd31bdea8a6018adc0379bc2f`](https://github.com/saifmht19/Mind-Mirror-1/commit/7751f09e5e6d3c7dd31bdea8a6018adc0379bc2f) — Add DISMISSING_CHOICE tactic and v6 multi-label fields to schema
- [`72c9c05ef75f53b2a71f9c3a72eb3c22bb712acd`](https://github.com/saifmht19/Mind-Mirror-1/commit/72c9c05ef75f53b2a71f9c3a72eb3c22bb712acd) — Add AI-companion pilot batch, Ollama runner, and fix bare-no refusal detection
- [`4611c330daffe5a60742b91122d499e1345f2d7c`](https://github.com/saifmht19/Mind-Mirror-1/commit/4611c330daffe5a60742b91122d499e1345f2d7c) — Add make_prompts.py: paste-ready web-chat prompts for conversation generation
- [`27ea74c856c4f6483e35fc7f9bdc48f941828a8f`](https://github.com/saifmht19/Mind-Mirror-1/commit/27ea74c856c4f6483e35fc7f9bdc48f941828a8f) — docs(annotation): add contributor resource README.md
- [`1404d80c0623383ef456f442cfe992e7b5782c91`](https://github.com/saifmht19/Mind-Mirror-1/commit/1404d80c0623383ef456f442cfe992e7b5782c91) — docs(annotation): add contributor resource CLAUDE_PROMPT.md
- [`345963996821766d46bc3fa57fc4bd8906e59fa5`](https://github.com/saifmht19/Mind-Mirror-1/commit/345963996821766d46bc3fa57fc4bd8906e59fa5) — docs(annotation): add contributor resource GEMINI_PROMPT.md
- [`1fe3bcf522b3bf5dcc2c702871a430d85c3bc20c`](https://github.com/saifmht19/Mind-Mirror-1/commit/1fe3bcf522b3bf5dcc2c702871a430d85c3bc20c) — docs(annotation): add contributor resource prepare_batches.py
- [`636211ea78786d029d19e7ffc9298988516984ec`](https://github.com/saifmht19/Mind-Mirror-1/commit/636211ea78786d029d19e7ffc9298988516984ec) — test(annotation): validate contributor batch structure and evidence offsets
- [`1cae0944078181e19c546267c3ea04b12d33a12e`](https://github.com/saifmht19/Mind-Mirror-1/commit/1cae0944078181e19c546267c3ea04b12d33a12e) — fix(annotation): enforce primary tactic membership
- [`e36ab8bb8b471285d719c780c6263ede45422024`](https://github.com/saifmht19/Mind-Mirror-1/commit/e36ab8bb8b471285d719c780c6263ede45422024) — prep(annotation): gate contributor batches on protocol and data readiness
- [`b2d03cd3658c4bfde56acb7c6b6edfeacdc6e3c8`](https://github.com/saifmht19/Mind-Mirror-1/commit/b2d03cd3658c4bfde56acb7c6b6edfeacdc6e3c8) — feat(annotation): align contributor batches to v6.2 proposal
- [`1d4642795c4a8da732c5f30ff98b89852f11ec25`](https://github.com/saifmht19/Mind-Mirror-1/commit/1d4642795c4a8da732c5f30ff98b89852f11ec25) — docs(annotation): publish sanitized private-batch manifest
- [`5cc63acd964482a70465cdb4df3c4aee834da7f2`](https://github.com/saifmht19/Mind-Mirror-1/commit/5cc63acd964482a70465cdb4df3c4aee834da7f2) — feat(annotation): prepare gated v6.2 contributor handoff
- [`148e33decd32e663956e6afdcdc8cb4c455687b1`](https://github.com/saifmht19/Mind-Mirror-1/commit/148e33decd32e663956e6afdcdc8cb4c455687b1) — docs(annotation): fix validator handoff path
- [`f0e308dce48819f7ce0d10d27ebbbd02c06873d2`](https://github.com/saifmht19/Mind-Mirror-1/commit/f0e308dce48819f7ce0d10d27ebbbd02c06873d2) — test(annotation): align dummy fixture with v6.2 validator
- [`59b15f4c2f1504ec5316f9e370577bbd17e0b393`](https://github.com/saifmht19/Mind-Mirror-1/commit/59b15f4c2f1504ec5316f9e370577bbd17e0b393) — fix(annotation): canonicalize v6 source hash recipe
- [`436db1cbb47ad3580fac3b51dfd4739547cfdaa6`](https://github.com/saifmht19/Mind-Mirror-1/commit/436db1cbb47ad3580fac3b51dfd4739547cfdaa6) — docs(annotation): sync corrected v6.2 contributor contract
- [`2f127f11122aae765fc408e477c5a61a82a3e943`](https://github.com/saifmht19/Mind-Mirror-1/commit/2f127f11122aae765fc408e477c5a61a82a3e943) — docs: synchronize contributor handoff with v6.2.0 ratification
- [`ee577347d1d4ce92cd1cda911ec53632c69a8653`](https://github.com/saifmht19/Mind-Mirror-1/commit/ee577347d1d4ce92cd1cda911ec53632c69a8653) — docs: synchronize contributor handoff with v6.2.0 ratification
- [`1a120aac44c63ed2249ef0b9424caf210d43ca12`](https://github.com/saifmht19/Mind-Mirror-1/commit/1a120aac44c63ed2249ef0b9424caf210d43ca12) — docs: record scoped Claude/Gemini private annotation sharing approval
- [`fb0d82625e0a861812983066f0a0b968046e99a1`](https://github.com/saifmht19/Mind-Mirror-1/commit/fb0d82625e0a861812983066f0a0b968046e99a1) — docs: record scoped Claude/Gemini private annotation sharing approval
- [`ceed3745dea508cc57963c5f5d272425c23d8fa1`](https://github.com/saifmht19/Mind-Mirror-1/commit/ceed3745dea508cc57963c5f5d272425c23d8fa1) — docs: correct ratification status and safeguard Claude annotation workflow
- [`a3b9bbeb08b2e033035b54f6bd597a39f8dc4d80`](https://github.com/saifmht19/Mind-Mirror-1/commit/a3b9bbeb08b2e033035b54f6bd597a39f8dc4d80) — docs: correct ratification status and safeguard Gemini annotation workflow
- [`86e07289136d2e347a25ecb2e5bc4d44073e545b`](https://github.com/saifmht19/Mind-Mirror-1/commit/86e07289136d2e347a25ecb2e5bc4d44073e545b) — feat: add deterministic v6.2 annotation postprocessing pipeline
- [`db6f16e99144d9bfc67f1a3359f5f32d5a21a5e8`](https://github.com/saifmht19/Mind-Mirror-1/commit/db6f16e99144d9bfc67f1a3359f5f32d5a21a5e8) — docs: flag stale contributor protocol copies
- [`b05dcb68d450646b7b18b75ddd942e87e0fee612`](https://github.com/saifmht19/Mind-Mirror-1/commit/b05dcb68d450646b7b18b75ddd942e87e0fee612) — docs: reconcile v6.2 ratification status and provenance

### `v6-evaluation-prep`

- [`a3a58d0c942aeee290bf6b0795c7d69cc0d4cc14`](https://github.com/saifmht19/Mind-Mirror-1/commit/a3a58d0c942aeee290bf6b0795c7d69cc0d4cc14) — feat: add v6 evaluation preparation pipeline
- [`faf3c5a3887e191b5bb1ee599820b2e86d8dd85e`](https://github.com/saifmht19/Mind-Mirror-1/commit/faf3c5a3887e191b5bb1ee599820b2e86d8dd85e) — fix: align evaluation adapter with v6 annotation contract

### `v6-multilabel-plan`

- [`22c3a00a1ada8404f53b72fffd1c4bace037a630`](https://github.com/saifmht19/Mind-Mirror-1/commit/22c3a00a1ada8404f53b72fffd1c4bace037a630) — feat(step1): stricter refusal detector, paired diagnostic suite, reproducible baseline
- [`eb090cc344cad5e4ca95cd81ba37e74fde1f10bf`](https://github.com/saifmht19/Mind-Mirror-1/commit/eb090cc344cad5e4ca95cd81ba37e74fde1f10bf) — feat(step2): paired-data generator, blind two-reviewer sheet, opt-in mapping v2
- [`10fc735ad61d03f1a73cb0f0d4c1c1e9d62fe289`](https://github.com/saifmht19/Mind-Mirror-1/commit/10fc735ad61d03f1a73cb0f0d4c1c1e9d62fe289) — Add demo model, escalation scorer, pair/tactic banks, demo UI and tests
- [`a55c153031245dc516dc90616ec875085722f855`](https://github.com/saifmht19/Mind-Mirror-1/commit/a55c153031245dc516dc90616ec875085722f855) — Add spec v6: multi-label tactics (tactic set plus primary tactic)

### `v6-protocol-freeze`

- [`aae3a78bd8f5318a6338f1f53779bf025acd43f1`](https://github.com/saifmht19/Mind-Mirror-1/commit/aae3a78bd8f5318a6338f1f53779bf025acd43f1) — feat: freeze v6 annotation protocol and validators
- [`4e8d652e0692e183ba6946fea966f4bdafd5afb4`](https://github.com/saifmht19/Mind-Mirror-1/commit/4e8d652e0692e183ba6946fea966f4bdafd5afb4) — docs: include canonical v6 spec for protocol validation
- [`afe1f584b8867fa65c8c2e791d4cbc83f915f04f`](https://github.com/saifmht19/Mind-Mirror-1/commit/afe1f584b8867fa65c8c2e791d4cbc83f915f04f) — feat(annotation): propose v6.2 protocol and schema pending ratification
- [`2ba3414fd1f53eb014e84745a3d8b5a841fc7902`](https://github.com/saifmht19/Mind-Mirror-1/commit/2ba3414fd1f53eb014e84745a3d8b5a841fc7902) — fix(protocol): align v6.2 schema and validator contract
- [`3a6f13b2bdbbf63a9d03f39d5744e0a775ae4c25`](https://github.com/saifmht19/Mind-Mirror-1/commit/3a6f13b2bdbbf63a9d03f39d5744e0a775ae4c25) — docs: record explicit research-lead v6.2.0 ratification and provider-sharing gate
- [`71cbc4600e7b6eda7bec637a921bda32326d572c`](https://github.com/saifmht19/Mind-Mirror-1/commit/71cbc4600e7b6eda7bec637a921bda32326d572c) — docs: mark v6.2.0 protocol ratified with separate provider sharing gate

### `v6-scenario-cards`

- [`22c3a00a1ada8404f53b72fffd1c4bace037a630`](https://github.com/saifmht19/Mind-Mirror-1/commit/22c3a00a1ada8404f53b72fffd1c4bace037a630) — feat(step1): stricter refusal detector, paired diagnostic suite, reproducible baseline
- [`eb090cc344cad5e4ca95cd81ba37e74fde1f10bf`](https://github.com/saifmht19/Mind-Mirror-1/commit/eb090cc344cad5e4ca95cd81ba37e74fde1f10bf) — feat(step2): paired-data generator, blind two-reviewer sheet, opt-in mapping v2
- [`10fc735ad61d03f1a73cb0f0d4c1c1e9d62fe289`](https://github.com/saifmht19/Mind-Mirror-1/commit/10fc735ad61d03f1a73cb0f0d4c1c1e9d62fe289) — Add demo model, escalation scorer, pair/tactic banks, demo UI and tests
- [`a55c153031245dc516dc90616ec875085722f855`](https://github.com/saifmht19/Mind-Mirror-1/commit/a55c153031245dc516dc90616ec875085722f855) — Add spec v6: multi-label tactics (tactic set plus primary tactic)
- [`2ca70fd541fb2084dc5891c7afbbaab8c6684353`](https://github.com/saifmht19/Mind-Mirror-1/commit/2ca70fd541fb2084dc5891c7afbbaab8c6684353) — Add scenario-card builder and 800 draft cards for full-conversation dataset

### `v6-scenario-grouping`

- [`871b3e5d5e52f60372332be17ca237c6032f81c9`](https://github.com/saifmht19/Mind-Mirror-1/commit/871b3e5d5e52f60372332be17ca237c6032f81c9) — feat: add scenario review and leakage-safe split tools
- [`699711eb88f14f74f7e012e82b638791b116e322`](https://github.com/saifmht19/Mind-Mirror-1/commit/699711eb88f14f74f7e012e82b638791b116e322) — style: clean scenario grouping files

### `v6-schema-dismissing-choice`

- [`22c3a00a1ada8404f53b72fffd1c4bace037a630`](https://github.com/saifmht19/Mind-Mirror-1/commit/22c3a00a1ada8404f53b72fffd1c4bace037a630) — feat(step1): stricter refusal detector, paired diagnostic suite, reproducible baseline
- [`eb090cc344cad5e4ca95cd81ba37e74fde1f10bf`](https://github.com/saifmht19/Mind-Mirror-1/commit/eb090cc344cad5e4ca95cd81ba37e74fde1f10bf) — feat(step2): paired-data generator, blind two-reviewer sheet, opt-in mapping v2
- [`10fc735ad61d03f1a73cb0f0d4c1c1e9d62fe289`](https://github.com/saifmht19/Mind-Mirror-1/commit/10fc735ad61d03f1a73cb0f0d4c1c1e9d62fe289) — Add demo model, escalation scorer, pair/tactic banks, demo UI and tests
- [`a55c153031245dc516dc90616ec875085722f855`](https://github.com/saifmht19/Mind-Mirror-1/commit/a55c153031245dc516dc90616ec875085722f855) — Add spec v6: multi-label tactics (tactic set plus primary tactic)
- [`2ca70fd541fb2084dc5891c7afbbaab8c6684353`](https://github.com/saifmht19/Mind-Mirror-1/commit/2ca70fd541fb2084dc5891c7afbbaab8c6684353) — Add scenario-card builder and 800 draft cards for full-conversation dataset
- [`7751f09e5e6d3c7dd31bdea8a6018adc0379bc2f`](https://github.com/saifmht19/Mind-Mirror-1/commit/7751f09e5e6d3c7dd31bdea8a6018adc0379bc2f) — Add DISMISSING_CHOICE tactic and v6 multi-label fields to schema
- [`72c9c05ef75f53b2a71f9c3a72eb3c22bb712acd`](https://github.com/saifmht19/Mind-Mirror-1/commit/72c9c05ef75f53b2a71f9c3a72eb3c22bb712acd) — Add AI-companion pilot batch, Ollama runner, and fix bare-no refusal detection
- [`4611c330daffe5a60742b91122d499e1345f2d7c`](https://github.com/saifmht19/Mind-Mirror-1/commit/4611c330daffe5a60742b91122d499e1345f2d7c) — Add make_prompts.py: paste-ready web-chat prompts for conversation generation

## Shared history and integration status

The following feature commits are reachable from multiple refs: `22c3a00a` (v5 refusal/diagnostic), `eb090cc3` (paired-data tools), `10fc735a` (demo model), `a55c1530` (multi-label spec), `2ca70fd5` (scenario cards), `7751f09e` (dismissing-choice schema), `72c9c05e` (companion pilot tooling), and `4611c330` (prompt generation). This overlap explains repeated files across branch diffs.

The seven evaluation-prep files and three scenario-grouping files are present on main with the same Git blob IDs as their respective branches. Their content is integrated, but their original commits are not in main ancestry. The protocol freeze changes are not on main and have an open PR. The active contributor branch contains significant unmerged tooling and documentation; keep it separate while annotation proceeds.

## Branch-deletion candidates for owner approval

No branch was deleted or renamed. These are **candidates only**, and the condition below must be met before any deletion.

- `v5-demo-model`: its three compared commits are also reachable from `v6-annotation-contributors` and/or other v6 refs; its demo code/artifacts remain reachable there. No open PR uses this head.
- `v5-step1-honest-persistence`: its only commit `22c3a00a` is present in seven other refs; all its changed files come from that shared commit.
- `v5-step2-paired-data`: both commits `22c3a00a` and `eb090cc3` remain reachable from several later refs.
- `v6-multilabel-plan`: all four commits are reachable from later scenario/contributor/schema refs.
- `v6-scenario-cards`: all five commits are reachable from contributor/schema refs; no unique commit is lost by removing this branch pointer.
- `v6-schema-dismissing-choice`: all eight commits are also reachable from `v6-annotation-contributors`; deleting the pointer would not remove those commits while the active branch retains them.

These are Git-reachability conclusions as of the audit snapshot, not confirmation that no teammate has a local checkout or active unlisted work. Confirm with the team before deleting. Retain the exact HEAD SHAs above in the audit record. Do **not** delete `main`, `v6-annotation-contributors`, or `v6-protocol-freeze`.

Not deletion candidates now:

- `v5-paper-skeleton`: unique `c2a19c3f` commit adds `paper/refs.bib`; preserve pending paper review.
- `v6-evaluation-prep` and `v6-scenario-grouping`: file contents match main, but their feature commits are unique. Preserve provenance or archive those commits before considering ref deletion.
- `v6-protocol-freeze`: active and has open PR #2.

## Private-data and secrets check

At the main baseline tree, no files are named as the 780 blinded batches, raw provider annotation outputs, or full private manifests. Existing tracked legacy pilot data/results are listed above and are not part of the cleanup additions. The contributor branch comparison contains a `distribution_manifest.json` path, earlier sample conversation artifacts, and 800 draft cards; this audit checked paths and commit metadata, not full text or authorization status. Do not copy those materials into this branch. The cleanup PR adds only documentation and ignore rules. Recheck tracked paths and inspect staged diffs before every future push.

The root `.gitignore` now protects dedicated private corpus, batch, raw-output, normalized-output, local secret, and generated-data locations. Keep real private inputs outside the public checkout where possible. Ignore rules do not untrack files already committed.

## Recommended archive layout (proposal only)

```text
archive/
├── legacy-v1-v5/       # old taxonomy, demo, paired-data experiments, original notes
└── v6-experiments/     # superseded schema/card/prototype work; retain immutable protocol history separately
```

Before any move, record source branch, commit SHA, original path, checksums for data/artifacts, and destination. Keep the ratified protocol and active contributor workflow at their current versioned branch paths. Do not move, rewrite, or delete data in this cleanup PR.
