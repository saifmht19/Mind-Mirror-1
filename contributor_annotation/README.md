# MindMirror v6 contributor annotation handoff

## Status and authorization gate

The v6.2.0 protocol / schema 2.0.0 on `v6-protocol-freeze` was **ratified by the research lead on 2026-10-28** (ratification commit `3a6f13b2bdbbf63a9d03f39d5744e0a775ae4c25`; protocol status commit `71cbc4600e7b6eda7bec637a921bda32326d572c`). **Provider sharing authorized by research lead on 2026-10-28:** the two contributors may privately upload the 780 blinded synthetic MindMirror conversations to Claude and Gemini respectively, solely for independent research annotation. This does not authorize public posting, unrelated use, sharing annotator outputs before freeze, or uploading unblinded/private third-party data. Check the local inputs before sharing; uploads are performed manually by contributors, not by this repository. The current public GitHub repository is not a distribution location for the private conversation batches.

The approved protocol/schema/validator candidate is commit `2ba3414fd1f53eb014e84745a3d8b5a841fc7902`. Provider sharing is now approved for the scoped synthetic batches. Share the same private input files with both contributors, confirm source and batch hashes before upload, and comply with the chosen providers' data-handling settings. Do not divide batches between the models. Each model submits independently and must not see the other model’s output before both are frozen.

## Local resources

- The private, pre-generated 780 record input batches and full ID-bearing manifest are kept outside this repository. Their protected distribution folder is `mindmirror-v6-private-batches`; it contains `claude/inputs` and `gemini/inputs` identical copies. Do not commit these folders or conversation text.
- The public `distribution_manifest.json` is sanitized: filenames/counts/hashes only, no conversation IDs or text.
- The exact local v6 pilot is the separate derived `annotation_pilot_20.jsonl`; do not substitute legacy `annotation/pilot_dataset.json`.
- The approved ratification record is `docs/annotation_protocol_v6.2.0_ratification_checklist.md` on `v6-protocol-freeze`. Historical issue-level uncertainties remain open; they are not a blocker to distributing **new** batches once provider sharing is approved, but must be resolved for evaluation.
- `examples/DUMMY_ONLY_NOT_DATASET.jsonl` is synthetic test material and must never be scored as corpus data.

## Per-batch workflow (provider sharing authorized 2026-10-28)

1. Confirm batch SHA-256 against the private manifest before each provider upload. Confirm Claude and Gemini receive byte-identical inputs.
2. Use the provider-specific prompt `CLAUDE_PROMPT.md` or `GEMINI_PROMPT.md`. Keep each annotator independent; do not share output files.
3. Save each complete JSONL response in a private output directory, not this public repo. Install the validation test dependency with `python -m pip install -r annotation/requirements-v6-validation.txt`. Run `python -m unittest tests.test_annotation_v6_2_protocol` for standard Draft 2020-12 validation and `python contributor_annotation/protocol/validate_v6_annotations.py PRIVATE\claude\batch_001.jsonl` (use the matching provider path) for cross-turn semantics and hash checks. Preserve the input batch, output, prompt hash, provider/model/version, timestamp, and validation reports.
4. Freeze both outputs for the batch. Then run the comparison tool:

   ```powershell
   python contributor_annotation/compare_annotations.py `
     --batch PRIVATE\batch_001.jsonl `
     --annotator-a PRIVATE\claude\batch_001.jsonl `
     --annotator-b PRIVATE\gemini\batch_001.jsonl `
     --out-dir PRIVATE\review\batch_001 `
     --validator contributor_annotation\protocol\validate_v6_annotations.py
   ```

5. The tool writes `comparison.json` and `disagreement_queue.jsonl`. The queue includes disagreement or review flags, not conversation text, and every item remains pending until a human adjudicator records a separate decision and rationale. Never overwrite raw provider outputs.
6. Report AI-AI agreement separately. It is not human inter-annotator agreement, gold-standard accuracy, or adjudication. Human IAA requires independently collected human labels and a specified statistic.

The comparator requires the deterministic v6.2 source-turn SHA-256 algorithm ratified by the research lead on 2026-10-28.

## No public submission of private material

Do not push batches, conversation text, full manifests containing IDs, provider outputs, credentials, or adjudication text to GitHub. Safe scripts, synthetic fixtures, sanitized manifests, and instructions may be committed to this contributor branch. Never merge to `main`.
