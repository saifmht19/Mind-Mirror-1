# Repository cleanup and branch inventory

Audit date: 2026-10-28. This file is a housekeeping guide, **not** a declaration that any branch has been merged, approved, or deleted. Branch ahead/behind values are relative to `main` at audit time and should be refreshed before acting.

## Working rules

- `main`: stable integration destination; avoid mixing historical v1/v5 instructions with v6 instructions. The existing README includes historical v1 content.
- `v6-protocol-freeze`: **ACTIVE — DO NOT DELETE OR MERGE BLINDLY** while Codex finalizes the six-tactic v6.2.0 contract. The earlier v6.1.0 seven-tactic contract differs.
- `v6-annotation-contributors`: **ACTIVE — PROTECT**. Contributor instructions and batch preparation tooling live here. Actual private conversation batches are not part of the public repository.
- Keep the original 800-conversation source, frozen 20-conversation pilot, independent labels, and adjudication reports immutable. Do not publish private input records.
- Never delete a branch merely because an open PR exists or because its filename resembles another branch. Inspect unique commits and files and preserve provenance.
- Use a PR with tests and reviewer sign-off for integration. Never force-push, silently rename tactic IDs, or train on unlabeled data.

## Branch inventory (relative to main on audit date)

| Branch | Ahead | Behind | Decision |
|---|---:|---:|---|
| `main` | — | — | Keep; integration target |
| `v6-protocol-freeze` | 3 | 0 | **Protect; active protocol work, unresolved compatibility and ratification** |
| `v6-annotation-contributors` | 17 | 2 | **Protect; contributor handoff** |
| `v6-evaluation-prep` | 2 | 0 | Review independent evaluation tests, then merge by PR |
| `v6-scenario-grouping` | 2 | 0 | Review scenario grouping tests, then merge by PR |
| `v6-schema-dismissing-choice` | 8 | 2 | Historic v6 foundation; inspect before consolidation |
| `v6-scenario-cards` | 5 | 2 | Historic scenario authoring; inspect before consolidation |
| `v6-multilabel-plan` | 4 | 2 | Historic v6 plan; inspect before consolidation |
| `v5-demo-model` | 3 | 2 | Historical; unique demo/model artifacts, do not blindly merge weights |
| `v5-paper-skeleton` | 3 | 2 | Historical; preserve manuscript/bibliography changes if useful |
| `v5-step2-paired-data` | 2 | 2 | Historical; preserve pair-generation utilities if useful |
| `v5-step1-honest-persistence` | 1 | 2 | Historical; preserve evaluation/diagnostic insights if useful |

## Suggested safe consolidation sequence

1. **Do not interrupt ongoing Codex work.** Check which branch/worktree is active and exclude it from all cleanup operations.
2. Review PR #1 (evaluation prep) and PR #3 (scenario grouping), including changed files, tests and review status. Draft PRs must be explicitly moved to ready-for-review before an authorized merge.
3. Complete v6.2.0 protocol reconciliation: the pilot has six tactics and excludes `other-dark-pattern`; confirm JSON Schema, validator, contributor prompts and evaluation adapter agree. Keep old protocol versions for traceability. Only merge the approved version.
4. Review the cumulative ancestry/diffs of the v5 and older v6 branches. Identify unique source files, reports, and manuscripts worth preserving. Prefer targeted cherry-picks or documented archival over bulk merging obsolete configurations, generated datasets, binary demo weights, or old v1/v5 schema.
5. Consolidate only reviewed work via separately tested PRs. Run unit tests and a fresh integrity audit afterward.
6. **Only after every unique necessary change is merged or deliberately archived**, delete obsolete *remote* branches. Record their final commit SHAs and destinations before deletion. Preserve `main` and current active/contributor branches.
7. Refresh this inventory after changes; never treat the ahead/behind table as permanently current.

## Known blockers

- The versioned v6.2.0 six-tactic annotation protocol is proposed; research-lead sign-off and compatibility checks are still required.
- The 12 pilot issues remain unresolved; structural schema validity is not equivalent to semantic correctness.
- The 780 blinded conversation batches are private and should remain outside the public repo unless redistribution permission and privacy checks are explicitly satisfied.
- The repository's historical v1 instructions may differ from current v6 workflows; do not treat them as canonical.

## Links

- [Pull requests](https://github.com/saifmht19/Mind-Mirror-1/pulls)
- [Branches](https://github.com/saifmht19/Mind-Mirror-1/branches)
- [Contributor workspace](https://github.com/saifmht19/Mind-Mirror-1/tree/v6-annotation-contributors/contributor_annotation)
- [Protocol branch](https://github.com/saifmht19/Mind-Mirror-1/tree/v6-protocol-freeze)
