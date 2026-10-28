# Protocol artifact provenance and ratification history

The baseline artifacts were fetched from `saifmht19/Mind-Mirror-1` branch `v6-protocol-freeze` at commit `afe1f584b8867fa65c8c2e791d4cbc83f915f04f` on 2026-10-28. The protocol, addendum, schema, and validator were then revised as a pre-ratification candidate and committed on the same branch at `2ba3414fd1f53eb014e84745a3d8b5a841fc7902`. The table below is preserved as historical provenance for those pre-ratification snapshots; its former pending-status statements are superseded by the committed ratification record at `v6-protocol-freeze` commit `71cbc4600e7b6eda7bec637a921bda32326d572c`.

## Historical pre-ratification candidate snapshot

| Contributor copy | Canonical path at `2ba3414fd1f53eb014e84745a3d8b5a841fc7902` | Candidate blob SHA |
|---|---|---|
| `annotation_protocol_v6.2.0.md` | `docs/annotation_protocol_v6.2.0.md` | `6ec1aa2f0926e31e5795fc91a168a62351d2b581` |
| `spec_v6.2_annotation_addendum.md` | `docs/spec_v6.2_annotation_addendum.md` | `6544217888b53467af064bc312b2f6690c7ccc9b` |
| `mindmirror_v6_annotation.v2.schema.json` | `annotation/schema/mindmirror_v6_annotation.v2.schema.json` | `3630bd0b9a8925bab6810716c87f12b25b12fab2` |
| `validate_v6_annotations.py` | `annotation/validate_v6_annotations.py` | `4d80dd473aea58bfb594a61e738967d233ed0e09` |

This table preserves the original candidate blob SHAs; do not rewrite or reinterpret them. The subsequent ratification record approved the v6.2.0 rules for future batches and did not migrate prior labels. Provider/data-sharing approval is distinct: the ratification checklist states that uploads to Claude or Gemini are not yet authorized.

## Ratified source and contributor snapshot

- Ratification record and status: `v6-protocol-freeze/docs/annotation_protocol_v6.2.0_ratification_checklist.md`, commit `71cbc4600e7b6eda7bec637a921bda32326d572c`.
- Ratified protocol: `v6-protocol-freeze/docs/annotation_protocol_v6.2.0.md`, blob `445e043a30982f9251b5eddb632e200de3e4f7ba`.
- The contributor protocol/addendum snapshots retain the rule text from candidate commit `2ba3414fd1f53eb014e84745a3d8b5a841fc7902`; this update changes their status/provenance language only. The schema description and validator module docstring now identify ratification; schema keywords/constraints and validator executable logic are unchanged. The deterministic source-text hash algorithm, batch hashes, and historical annotations remain unchanged.
- Approved upstream schema and validator blobs remain `3630bd0b9a8925bab6810716c87f12b25b12fab2` and `4d80dd473aea58bfb594a61e738967d233ed0e09`.
- Documentation-reconciled contributor snapshot blobs are:

| Contributor snapshot | Snapshot blob SHA | Change from approved source |
|---|---|---|
| `protocol/annotation_protocol_v6.2.0.md` | `a15682578a23a67b20e1a3517e3e271298168c99` | Ratification status and provenance wording only |
| `protocol/spec_v6.2_annotation_addendum.md` | `ddf7bbc3647026d0541ac700de2c4c1da0b99ff8` | Ratification status and provenance wording only |
| `protocol/mindmirror_v6_annotation.v2.schema.json` | `e71960b2e800509cc0f6e139d4d185b15a93dc70` | Description text only; schema semantics unchanged |
| `protocol/validate_v6_annotations.py` | `583002c0e4d53f9ab9a15537e4060d38e38ac948` | Module docstring only; validator logic unchanged |
| `CLAUDE_PROMPT.md` | `96746f8bf440e899e74c28ebde6879da036ad96e` | Pinned ratification reference and provider-sharing gate |
| `GEMINI_PROMPT.md` | `ba2434f694ea77d4c081d5975ae97a9e9a5b91e0` | Pinned ratification reference and provider-sharing gate |
| `README.md` | `83e212ba6eb1ed19d780427ac31c1fb842aacd3f` | Current ratification and authorization status |
| `READINESS_BLOCKERS.md` | `33cfe8960b12b0b2fff629f38e2386962494842e` | Current ratification and authorization status |
| `distribution_manifest.json` | `3c457d1a41a017d7b789e73e71ea39d185b0e0a2` | Status/ratification pointer; all batch SHA-256 values preserved |
| `V6.2_RATIFICATION_CHECKLIST.md` | `4bfc4419b9f47623c3bd5243a36475428e57083a` | Historical checklist retained with superseded-status banner |
- Preserve v6.1.0 files and every existing annotation record. Do not infer provider upload approval from protocol ratification.
