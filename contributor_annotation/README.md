# MindMirror v6.2.0 contributor annotation pipeline

## Protocol and data status

Protocol v6.2.0 / schema 2.0.0 was ratified on 2026-10-28. The committed ratification record and canonical protocol are on `v6-protocol-freeze`; the approved schema and Python validator blob SHAs are `3630bd0b9a8925bab6810716c87f12b25b12fab2` and `4d80dd473aea58bfb594a61e738967d233ed0e09`. The contributor schema and validator copies are byte-identical to those approved blobs. **Documentation blocker:** the contributor folder's duplicate protocol, addendum, and provenance files still contain pre-ratification/pending language, and the canonical addendum file itself retains a pending-status banner despite the ratified protocol and checklist. These frozen protocol artifacts were not edited here; for the approved status and rules, consult `v6-protocol-freeze/docs/annotation_protocol_v6.2.0.md` and its committed ratification checklist. Ratification does not itself authorize a particular provider upload; follow the project's separate data-sharing authorization and applicable provider terms.

No real 780-record annotation is performed by this tooling task. Keep blinded inputs, raw Claude/Gemini responses, normalized private outputs, manifests containing IDs, credentials, and adjudication notes outside Git. Only code, synthetic fixtures, and documentation belong in this repository.

The working raw-output format is specified in [RAW_MODEL_OUTPUT_CONTRACT.md](RAW_MODEL_OUTPUT_CONTRACT.md). The provider prompts are [Claude](CLAUDE_PROMPT.md) and [Gemini](GEMINI_PROMPT.md). Save each raw response unchanged before processing; do not edit it to satisfy the schema.

## Install and verify

From the repository root in PowerShell:

```powershell
python -m pip install -r annotation/requirements-v6-validation.txt
python -m unittest tests.test_postprocess_annotations -v
```

The postprocessor and assembler run both `jsonschema.Draft202012Validator` and the approved Python `validate_record` implementation. They fail closed and do not overwrite existing outputs. The transformation log records raw/input/output SHA-256 digests, prompt digest, external model metadata, time, per-record span counts, derived values, and validator warnings. It does not copy conversation text or quoted spans into the log.

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
