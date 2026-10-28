# Protocol artifact provenance

The baseline artifacts were fetched from `saifmht19/Mind-Mirror-1` branch `v6-protocol-freeze` at commit `afe1f584b8867fa65c8c2e791d4cbc83f915f04f` on 2026-10-28. The protocol, addendum, schema, and validator were then revised as a pre-ratification candidate and committed on the same branch at `2ba3414fd1f53eb014e84745a3d8b5a841fc7902`. The current contributor copies correspond to these new candidate blobs; the v6.2.0 status remains pending research-lead ratification.

| Contributor copy | Canonical path at `2ba3414fd1f53eb014e84745a3d8b5a841fc7902` | Candidate blob SHA |
|---|---|---|
| `annotation_protocol_v6.2.0.md` | `docs/annotation_protocol_v6.2.0.md` | `6ec1aa2f0926e31e5795fc91a168a62351d2b581` |
| `spec_v6.2_annotation_addendum.md` | `docs/spec_v6.2_annotation_addendum.md` | `6544217888b53467af064bc312b2f6690c7ccc9b` |
| `mindmirror_v6_annotation.v2.schema.json` | `annotation/schema/mindmirror_v6_annotation.v2.schema.json` | `3630bd0b9a8925bab6810716c87f12b25b12fab2` |
| `validate_v6_annotations.py` | `annotation/validate_v6_annotations.py` | `4d80dd473aea58bfb594a61e738967d233ed0e09` |

The baseline source artifacts explicitly said v6.2.0 was pending research-lead ratification. This correction does not itself ratify it. Do not begin annotation or treat a passing test as approval. Record the new protocol commit and blob SHAs after push; preserve the v6.1.0 files and all existing records.
