# MindMirror

MindMirror is a research project studying how conversational assistants respond to user choices and refusals, including potentially manipulative persuasion across multiple turns. The v6 work is a synthetic-data research pipeline; it is not a deployed guardrail product and its current corpus is not human-verified gold-standard data.

## Current research status

- The v6.2.0 annotation protocol is ratified. The pilot vocabulary contains exactly six tactics: guilt-tripping, false urgency, excessive flattery, pressure after refusal, fear appeals, and dismissing user choice. The pilot excludes `other-dark-pattern`; suspected out-of-taxonomy behavior is flagged separately for human review.
- The cleaned 800-conversation corpus and the frozen 20-conversation v6 pilot have been structurally checked. Pilot adjudication remains preliminary and contains unresolved semantic issues; it must not be described as human gold data.
- Two contributors are annotating the non-pilot records independently. The 780 conversation inputs and annotation outputs are private working materials and are not stored in this public repository.
- Scenario grouping and label review are prerequisites for leakage-safe evaluation. Do not finalize train/validation/test splits from unreviewed `group_id`, `pair_id`, `situation`, or generator-intended labels.
- Model training and confirmatory evaluation are not the current annotation workflow. Synthetic-only results cannot establish broad real-world generalization.

## Canonical v6 resources

The ratified protocol and active workflow are maintained on separate branches:

- [Ratified v6.2.0 protocol](https://github.com/saifmht19/Mind-Mirror-1/blob/v6-protocol-freeze/docs/annotation_protocol_v6.2.0.md)
- [Protocol schema and validator](https://github.com/saifmht19/Mind-Mirror-1/tree/v6-protocol-freeze/annotation)
- [Claude/Gemini contributor workflow](https://github.com/saifmht19/Mind-Mirror-1/tree/v6-annotation-contributors/contributor_annotation)
- [Repository cleanup inventory](docs/REPOSITORY_CLEANUP.md)
- [v6 multi-label research specification](https://github.com/saifmht19/Mind-Mirror-1/blob/v6-protocol-freeze/docs/spec_v6_multilabel.md)

Do not edit or infer approval from an old schema or from a successful structural validation. Historical protocol versions and adjudicated records are retained for provenance.

## Repository structure

```text
annotation/       Historical v1/v5 pilot UI and its existing records; not the v6.2 workflow
api/              Earlier demo API
data/              Dataset import, structural audit, schema, and scenario-grouping utilities
docs/              Research specification, scenario grouping, and repository inventory
evaluation/        v6 evaluation-preparation interfaces and metrics; not a training command
generation/        Legacy synthetic-data generation scripts and documentation
models/            Historical baseline/context model code and existing artifacts
taxonomy/          Historical v1 taxonomy
tests/             Automated tests and synthetic fixtures
ui/                Earlier demo UI
```

Private corpora, blind annotation inputs, raw provider outputs, normalized annotation outputs, and full private manifests belong in explicitly authorized private storage, not in this public repository.

## Four-member team setup

1. Clone the repository and read this README plus [the cleanup inventory](docs/REPOSITORY_CLEANUP.md).
2. For v6 protocol review, inspect the `v6-protocol-freeze` branch and its protocol version history.
3. For annotation work, check out `v6-annotation-contributors` and follow its [contributor README](https://github.com/saifmht19/Mind-Mirror-1/blob/v6-annotation-contributors/contributor_annotation/README.md). Each annotator should keep provider input and raw output in the approved private location and preserve raw output unchanged.
4. Do not put conversation text, annotated records, or full manifests in issues, pull requests, shared public branches, or commit messages. Coordinate schema/protocol questions with the research lead; leave disagreements unresolved until reviewed.
5. Before changing shared code or protocol documents, use a focused branch and pull request. Do not work directly on `main` or overwrite either active v6 branch.

## Tests

From the repository root, run the available unit tests:

```bash
python -m unittest discover -s tests -v
```

Some historical API/model tests may require optional dependencies. Install only dependencies documented by the relevant component; do not train models as part of annotation setup. Tests validate software behavior, not semantic correctness of labels.

## Historical and legacy work

The repository contains earlier v1 single-label taxonomy, v5 persistence/demo experiments, and v6 exploratory schema/card work. Their code, artifacts, and notes are preserved for provenance. The root `taxonomy/`, `annotation/`, and `generation/` documentation should be treated as historical unless it explicitly points to the ratified v6.2.0 workflow. Do not merge an obsolete schema or tactic definition into v6.

See [docs/REPOSITORY_CLEANUP.md](docs/REPOSITORY_CLEANUP.md) for the remote branch audit, preservation decisions, and proposed archive layout.
