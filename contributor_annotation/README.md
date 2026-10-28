# MindMirror v6 contributor annotation handoff

## Status and authorization gate

The v6.2.0 protocol on `v6-protocol-freeze` is **proposed, not ratified**. Do not annotate the 780 records or submit conversation text to Claude/Gemini until (a) the research lead commits the completed `V6.2_RATIFICATION_CHECKLIST.md` decisions and (b) explicitly authorizes sharing with those providers. The current public GitHub repository is not a distribution location for the private conversation batches.

After ratification, record the approved protocol/schema/validator SHAs and share the same input files with both contributors. Do not divide batches between the models. Each model submits independently and must not see the other model’s output before both are frozen.

## Local resources

- The private, pre-generated 780 record input batches and full ID-bearing manifest are kept outside this repository. Their protected distribution folder is `mindmirror-v6-private-batches`; it contains `claude/inputs` and `gemini/inputs` identical copies. Do not commit these folders or conversation text.
- The public `distribution_manifest.json` is sanitized: filenames/counts/hashes only, no conversation IDs or text.
- The exact local v6 pilot is the separate derived `annotation_pilot_20.jsonl`; do not substitute legacy `annotation/pilot_dataset.json`.
- `V6.2_RATIFICATION_CHECKLIST.md` records semantic and schema blockers. It is not an approval record.
- `examples/DUMMY_ONLY_NOT_DATASET.jsonl` is synthetic test material and must never be scored as corpus data.

## Per-batch workflow (only after both gates)

1. Confirm batch SHA-256 against the private manifest before each provider upload. Confirm Claude and Gemini receive byte-identical inputs.
2. Use the provider-specific prompt `CLAUDE_PROMPT.md` or `GEMINI_PROMPT.md`. Keep each annotator independent; do not share output files.
3. Save each complete JSONL response in a private output directory, not this public repo. Run Track A’s version-pinned v6.2 validator. Preserve the input batch, output, prompt hash, provider/model/version, timestamp, and validation report.
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

The comparator requires the v6.2 source-turn hash defined in the ratified protocol. The currently proposed algorithm is documented in the checklist; it must not be treated as approved until the lead selects it.

## No public submission of private material

Do not push batches, conversation text, full manifests containing IDs, provider outputs, credentials, or adjudication text to GitHub. Safe scripts, synthetic fixtures, sanitized manifests, and instructions may be committed to this contributor branch. Never merge to `main`.

