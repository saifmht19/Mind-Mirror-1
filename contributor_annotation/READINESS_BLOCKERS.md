# Contributor batch readiness (2026-10-28)

## Decision

The Track A artifact identifies itself as protocol `v6.1.0` and is committed at
`4e8d652e0692e183ba6946fea966f4bdafd5afb4`. It is frozen as a versioned document,
but **is not yet approved for the planned large-scale 780-record annotation run**.
The protocol itself says two operational choices should be ratified before that
run: the pressure-level 0–3 anchors and the primary-label rule for an
`other-dark-pattern`-only turn. Approval must be recorded by the research lead;
any resulting text change must get a new protocol version and commit SHA. This
branch therefore records the dependency but does not copy or silently bless the
protocol, schema, or validator as production-ready.

Track A also reports 12 unresolved issues in the legacy pilot while the
issue-level evidence and adjudicated output are unavailable. Those issues must
remain open. The legacy pilot's single-label labels are not v6 gold labels and
cannot substitute for the frozen 20-record conversation pilot used for
exclusion.

## Source availability and sharing

The required `data/conversations/processed/master_cleaned.jsonl` is absent from
the inspected contributor branch and current preparation worktree. The
contributor branch also lacks the expected frozen 20-record pilot JSONL; the
committed `annotation/pilot_dataset.json` is a different, legacy single-turn
format and has no mapping to the 800 conversation IDs. No records have been
fabricated or selected as substitutes.

GitHub reports the repository as public but with no declared repository
license. Public visibility alone does not establish authorization to redistribute
the locally processed conversation corpus or send it to third-party providers.
No source dataset or pilot records are included in this preparation commit.
Obtain written project authorization and the exact canonical files before
running the batch builder or uploading batches to Claude/Gemini.

## What the tooling is ready to do

`prepare_batches.py` accepts the exact cleaned 800-record JSONL and an exact
20-record pilot JSON/JSONL, excludes by `conversation_id`, and writes
deterministic batches of at most 50 with a SHA-256 manifest. Visible records are
whitelisted to `conversation_id`, `domain`, and canonical ordered turns
(`turn_index`, `speaker`, `text`); generator fields, writer intent, scenario
metadata, and labels are stripped. Both providers should receive the same batch
files byte-for-byte. `validate_batches.py` checks the batch manifest, counts,
hashes, unique IDs, blind-field whitelist, and turn structure.

These are **unrun against the real corpus** because the required inputs are not
available. The manifest marks protocol readiness as blocked. The Track A
annotation-output validator must be copied and run only after protocol approval;
the current legacy contributor output validator uses non-canonical tactic
spellings and must not be used for v6 output.

## Release checklist

1. Research lead ratifies the pressure anchors and `other-dark-pattern` primary
   rule, or issues a revised protocol version. Keep all 12 legacy issues open.
2. Supply the canonical cleaned corpus and exact frozen pilot; verify 800/20
   records and matching unique IDs.
3. Establish sharing authorization for the dataset and third-party annotation
   providers before adding conversation text to this public branch or provider
   prompts.
4. Run the builder, validate every batch, independently reproduce the same
   SHA-256 manifest, then distribute identical inputs to both annotators.
5. Validate returned annotations with the matching Track A schema/validator;
   preserve each annotator's output and adjudicate disagreements separately.
