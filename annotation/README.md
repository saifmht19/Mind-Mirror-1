# Legacy pilot annotation UI

> **Historical v1/v5 workflow.** This interactive single-label tool and the files under `annotation/results/` are not the ratified MindMirror v6.2.0 multi-label workflow. Do not use its labels as v6 gold labels or add v6 annotations here.

This directory retains the earlier pilot interface, dataset, and existing reviewer outputs for historical reproducibility. They are preserved unchanged. The v6.2.0 protocol, schema, validators, and current contributor instructions are maintained on the separate `v6-protocol-freeze` and `v6-annotation-contributors` branches.

For the canonical v6 workflow:

- [Ratified v6.2.0 protocol](https://github.com/saifmht19/Mind-Mirror-1/blob/v6-protocol-freeze/docs/annotation_protocol_v6.2.0.md)
- [Contributor workflow](https://github.com/saifmht19/Mind-Mirror-1/tree/v6-annotation-contributors/contributor_annotation)

The old commands below are retained only as historical reference. Their result files are already tracked in the repository; do not overwrite them.

```bash
python annotation/labeler.py --list-tactics
python annotation/labeler.py --name YourName
```
