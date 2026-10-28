# MindMirror v6 — Contributor annotation workspace

**Branch:** `v6-annotation-contributors` (created from `v6-schema-dismissing-choice`)

This branch is for the two independent AI annotators (Claude and Gemini), *not* model training. The same 780 non-pilot conversations must be independently annotated by **both** models. Do **not** divide the 780 between the two models.

## Prerequisite: frozen protocol

**Do not start actual annotation until Track A has published a frozen protocol and machine-readable schema.** The current repository's `docs/spec_v6_multilabel.md` is the reference for review, but a Track A protocol may refine unclear operational definitions. Record exactly which protocol commit SHA/version was used. Never mix batches labeled under different guideline versions without revalidation.

## Inputs and availability

- Canonical spec: `docs/spec_v6_multilabel.md` (included through the source branch).
- Cleaned dataset expected **locally**: `data/conversations/processed/master_cleaned.jsonl` (800 conversations; currently NOT confirmed present on GitHub at this path).
- Frozen pilot: `annotation_pilot_20.jsonl` (get the exact frozen version from the project lead; do not regenerate).
- Frozen guideline/schema from Track A (copy/link once ready).
- AI annotators must see **only** conversation ID, domain, ordered turns, and the frozen annotation schema. Keep generator identities, writer-intended labels, sampling metadata and other annotator's results hidden.

Do not upload private, unlicensed, or restricted data to third-party AI providers without project-lead authorization. Verify access and project rules first.

## Setup (Windows CMD / PowerShell)

```bash
git fetch origin
git switch v6-annotation-contributors
git pull --ff-only origin v6-annotation-contributors
python contributor_annotation/prepare_batches.py --dataset data/conversations/processed/master_cleaned.jsonl --pilot data/conversations/derived/v6_audit/annotation_pilot_20.jsonl --out PATH_TO_PRIVATE_BATCH_DIRECTORY --batch-size 40
python contributor_annotation/validate_batches.py PATH_TO_PRIVATE_BATCH_DIRECTORY --dataset data/conversations/processed/master_cleaned.jsonl --pilot data/conversations/derived/v6_audit/annotation_pilot_20.jsonl
```

The script creates a stable 780-ID manifest and small JSONL batches, but stops if counts, IDs, or exclusions fail. Review the generated manifest before sharing batches. Upload the *same batch files* to each model independently.

## Roles and workflow

- **Claude contributor:** copy `contributor_annotation/CLAUDE_PROMPT.md`, annotate all batches into `contributor_annotation/outputs/claude/`.
- **Gemini contributor:** copy `contributor_annotation/GEMINI_PROMPT.md`, annotate those *same* batches into `contributor_annotation/outputs/gemini/`.
- Each contributor keeps a batch manifest and validates batches locally before a commit.
- No one sees the other model's labels before both annotation submissions for a batch are frozen.
- Use separate subdirectories, commit only your model's derived outputs, and push commits to this branch. Do not rewrite anyone else's files.
- Because this is a shared branch, fetch + rebase on the latest remote branch before push; never force-push. Coordinate before editing shared files.
- If GitHub rejects a push or the branch is protected, push to a personal branch such as `v6-claude-annotations-USERNAME` or `v6-gemini-annotations-USERNAME` and open a PR into this contributor branch.
- Do not merge anything into `main`.

### Suggested commit/push flow

```bash
git status
git add contributor_annotation/outputs/claude/
git commit -m "data: add Claude annotation batch 001"
git fetch origin
git rebase origin/v6-annotation-contributors
git push origin HEAD:v6-annotation-contributors
```

Gemini contributor replaces `claude` with `gemini`. If rebasing conflicts, stop and resolve without overwriting independent annotation files. Commit only validated outputs; never add API keys or model secrets.

## Required submission for each batch

- Fully annotated JSONL with unchanged conversation IDs, original turn text, order and indices.
- Annotation model/provider, exact version if known, generation date, prompt hash/version, frozen protocol commit SHA, batch ID and conversation count.
- A short uncertainties file (or explicit empty uncertainties list) and local validation result.
- No claimed human validation, no invented labels, no incomplete/truncated JSONL.

## Quality checks

1. Every input ID appears exactly once and there are no extra IDs.
2. Source messages, speaker roles and indices are unchanged.
3. Every user turn contains refusal boolean, correct zero-based half-open span or nulls.
4. Every assistant turn contains tactic set, valid primary tactic, integer pressure 0–3 and at least one in-range exact evidence span per assigned tactic.
5. Empty tactic set means primary `neutral`; no `neutral` inside tactic set.
6. Every conversation has escalation/onset computed from the protocol, honest persistence, annotator ID and uncertainty notes.
7. Cross-check output against frozen schema using Track A's validator (when delivered).
8. Keep AI annotation disagreements for independent adjudication, not automatic majority voting.

## Limits

The AI-assisted labels are **silver-standard candidates**, not human gold-standard data. Scenario-grouping and final train/test split decisions remain with the research lead. This branch should never be used to claim confirmatory model performance.


## Current readiness gate

See [`READINESS_BLOCKERS.md`](READINESS_BLOCKERS.md) before generating or sharing batches. Track A's versioned protocol is frozen as v6.1.0, but two operational decisions are still awaiting research-lead ratification, so the 780-record run is blocked. The exact cleaned corpus and frozen pilot are not present in this branch. Do not use the legacy `annotation/pilot_dataset.json` as a substitute. After the lead supplies the canonical files and authorizes provider sharing, run `prepare_batches.py` and then `validate_batches.py`; the exact same batch files and manifest must be used by Claude and Gemini.
