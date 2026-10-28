# MindMirror v6.2.0 contributor annotation pipeline

## Protocol and data status

Protocol v6.2.0 / schema 2.0.0 was ratified on 2026-10-28. The canonical protocol and approval record are on `v6-protocol-freeze`; the approval commit is `71cbc4600e7b6eda7bec637a921bda32326d572c`, and the approved source schema/validator blobs are `3630bd0b9a8925bab6810716c87f12b25b12fab2` and `4d80dd473aea58bfb594a61e738967d233ed0e09`. Contributor snapshots now identify ratification while preserving the six-tactic contract, schema constraints, validator behavior, hash recipe, batch hashes, and past annotations. The canonical addendum file still has a pre-ratification banner in its frozen source; the committed protocol and ratification checklist establish the approved status. **Provider sharing is not authorized by that ratification record. Do not send conversation text to Claude, Gemini, or another provider unless a separate authorization is recorded.** See [PROVENANCE.md](protocol/PROVENANCE.md) for candidate and ratified-source SHAs.

No real 780-record annotation is performed by this tooling task. Keep blinded inputs, raw Claude/Gemini responses, normalized private outputs, manifests containing IDs, credentials, and adjudication notes outside Git. Only code, synthetic fixtures, and documentation belong in this repository.

The working raw-output format is specified in [RAW_MODEL_OUTPUT_CONTRACT.md](RAW_MODEL_OUTPUT_CONTRACT.md). The provider prompts are [Claude](CLAUDE_PROMPT.md) and [Gemini](GEMINI_PROMPT.md). Save each raw response unchanged before processing; do not edit it to satisfy the schema.

See [PROVENANCE_LIMITATIONS.md](PROVENANCE_LIMITATIONS.md) for the local five-record trial's unresolved model-version and provider-side prompt provenance, and the evidence required before outputs can be treated as verified.

## Install and verify

From the repository root in PowerShell:

```powershell
python -m pip install -r annotation/requirements-v6-validation.txt
python -m unittest tests.test_annotation_v6_2_protocol tests.test_contributor_compare tests.test_evaluation_prep tests.test_postprocess_annotations -v
```

The postprocessor and assembler run both `jsonschema.Draft202012Validator` and the approved Python `validate_record` implementation. They fail closed and do not overwrite existing outputs. Schema-permitted notes on user turns are retained. Optional `notes: null` fields are omitted from normalized output and counted per record in the transformation log; this does not alter semantic labels or the immutable raw response. The schema description and validator docstring in this contributor snapshot identify the ratified record; constraints, executable logic, and the source-text hash algorithm are unchanged. The approved upstream blob SHAs and documentation-only snapshot SHAs are preserved in [PROVENANCE.md](protocol/PROVENANCE.md). The transformation log records raw/input/output SHA-256 digests, prompt digest, external model metadata, time, per-record span counts, omitted null-note counts, derived values, and validator warnings. It does not copy conversation text or quoted spans into the log.

## Process Claude output

Store all paths below in the private distribution directory. Each raw file is a verbatim provider response exported as JSONL for one 5–10 conversation chunk.

```powershell
python contributor_annotation/postprocess_annotations.py `
  --input "PRIVATE\claude\inputs\batch_001\chunk_001.jsonl" `
  --raw-output "PRIVATE\claude\raw\batch_001\chunk_001.jsonl" `
  --output "PRIVATE\claude\normalized\batch_001\chunk_001.jsonl" `
  --log "PRIVATE\claude\logs\batch_001\chunk_001.transform.json" `
  --annotator-id "claude-annotator-1" `
  --provider "Anthropic" `
  --model "MODEL NAME FROM PROVIDER UI" `
  --model-version "EXACT MODEL VERSION FROM PROVIDER UI" `
  --prompt-file contributor_annotation/CLAUDE_PROMPT.md
```

## Process Gemini output

Use the identical private input bytes supplied to Claude; keep provider responses separate.

```powershell
python contributor_annotation/postprocess_annotations.py `
  --input "PRIVATE\gemini\inputs\batch_001\chunk_001.jsonl" `
  --raw-output "PRIVATE\gemini\raw\batch_001\chunk_001.jsonl" `
  --output "PRIVATE\gemini\normalized\batch_001\chunk_001.jsonl" `
  --log "PRIVATE\gemini\logs\batch_001\chunk_001.transform.json" `
  --annotator-id "gemini-annotator-1" `
  --provider "Google" `
  --model "MODEL NAME FROM PROVIDER UI" `
  --model-version "EXACT MODEL VERSION FROM PROVIDER UI" `
  --prompt-file contributor_annotation/GEMINI_PROMPT.md
```

The model name/version flags must be replaced with the actual provider-reported values. Do not leave placeholders or infer a version from the date. The prompt hash is computed from the exact prompt file bytes.

## Assemble a 40-record batch from chunks

Once all chunks have been independently processed, list every normalized chunk. Each chunk must contain 5–10 records; the assembler checks unique IDs, complete coverage, source turn/text identity, schema and Python validation, then writes records in the original input batch order.

```powershell
python contributor_annotation/assemble_annotation_chunks.py `
  --batch "PRIVATE\claude\inputs\batch_001.jsonl" `
  --chunk "PRIVATE\claude\normalized\batch_001\chunk_001.jsonl" `
  --chunk "PRIVATE\claude\normalized\batch_001\chunk_002.jsonl" `
  --chunk "PRIVATE\claude\normalized\batch_001\chunk_003.jsonl" `
  --chunk "PRIVATE\claude\normalized\batch_001\chunk_004.jsonl" `
  --output "PRIVATE\claude\normalized\batch_001.jsonl"
```

Repeat the assembly independently for Gemini with Gemini paths. Never show one provider the other provider's outputs. Only after both completed outputs are frozen should the existing comparison tool be run and its disagreement queue reviewed by a human.

## Safe trial readiness

The scripts and synthetic tests are designed for a five-conversation trial. Before submitting real text to a provider, the project lead must verify the current sharing authorization, the actual privately held 5-record input, the prompt/model metadata, and that the intended provider receives only the approved blinded input. The trial output remains silver annotation; no model training or corpus rewriting is part of this workflow.
