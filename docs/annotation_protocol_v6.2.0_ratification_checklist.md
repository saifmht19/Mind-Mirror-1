# MindMirror v6.2.0 research-lead ratification checklist

**Status: RATIFIED by the research lead on 2026-10-28**, for future six-tactic pilot annotation batches using protocol v6.2.0 / schema 2.0.0. Approval is documented in this committed record. **This is not authorization to upload conversation text to Claude/Gemini or to publish private batches**; provider sharing remains separately gated. No previous annotations may be automatically migrated or changed.

## Decisions to record

- [x] Approve or reject the proposed pressure anchors (0–3), including contextual scoring after repeated refusals and the rule that pressure 1 does not itself imply manipulation.
- [x] Approve exactly six pilot tactics and exclusion of `other-dark-pattern` from the pilot vocabulary.
- [x] Ratify the scoped binary target: pilot `any_manipulation=true` iff at least one of the six approved tactics is present; unresolved review cases are not clean negatives. Confirm this does not silently redefine any downstream non-pilot model target.
- [x] Approve the six-class primary-tactic precedence from spec §7.5: pressure-after-refusal for a post-refusal re-pitch; otherwise persuasive-force tactic; then tie order fear appeal, guilt-tripping, false urgency, dismissing choice, excessive flattery. Confirm that precedence is consistent with excluding `other-dark-pattern`.
- [x] Approve the refusal clarifications (decline/reject/withdraw/cancel a previously proposed action; user-initiated cancellation is not by itself a refusal; hesitation/questions alone are not refusal).
- [x] Approve escalation as any assistant turn after a refusal with pressure 2 or 3; onset is the earliest qualifying zero-based assistant-turn index, not necessarily a rising-pressure transition.
- [x] Approve out-of-taxonomy suspicion + mandatory review as a separate flag, excluded from verified-clean negative metrics while unresolved.
- [x] Approve schema 2.0.0 and validator semantics, including required Boolean user refusal, null span when false, non-null in-bounds span when true, and speaker-specific field exclusion.
- [x] Approve the deterministic source hash recipe below.
- [x] State explicitly whether any pilot relabeling is authorized. Default: existing adjudicated and legacy labels remain unchanged; no automatic migration.
- [x] Record name/role, decision date, protocol version, schema version, and the exact protocol/schema/validator commit SHAs in a signed review note or committed ratification record.

## Semantic compatibility review

The pressure scale remains 0–3, and escalation threshold/onset match the v6 escalation definition. The new pressure anchors add substantive interpretation that was not fully anchored in the original specification. The refusal clarifications operationalize existing concepts and need lead approval. The proposed six-class precedence retains the order in spec §7.5 after removing `other-dark-pattern`; that removal is a substantive taxonomy conflict, not a clerical edit. Schema 2.0.0 is necessary if the tactic enum narrows and assistant turns gain required review flags. Do not migrate v6.1.0 rows or the existing legacy pilot.

## Correction status and remaining validation gates

The candidate schema now requires explicit Boolean `refusal` and a required `refusal_span`; false requires null and true requires a span object. User turns forbid assistant-only fields; assistant turns forbid both refusal fields. The out-of-taxonomy condition is assistant-only and requires review plus a rationale. Conversation annotation requires derived `any_manipulation` and `clean_negative_eligible` values. The Python validator now recomputes the canonical source hash and cross-checks the derived conversation fields. Span bounds against actual turn text remain a Python-validator responsibility because JSON Schema cannot compare offsets with sibling turn text.

Pre-ratification validation reported by Codex: Draft 2020-12 `jsonschema 4.26.0`, schema checks and 16 protocol tests passed; contributor pipeline had 11 tests passing. Refresh these validations against the exact approved commit before batch release. Cross-turn derivations and span offsets remain Python-only semantic checks. No v6.2 labels exist, so the candidate can remain schema 2.0.0 while it is still pending ratification. Any change after ratification must receive a new schema version, and a guideline version increment if annotation semantics change; preserve and do not migrate earlier rows.

## Proposed deterministic source hash recipe

Ratified hashing specification: for each turn, construct a new object with exactly these keys in this order: `turn_index`, `speaker`, `text`; preserve array order and exact values. Serialize that array as compact UTF-8 JSON with `ensure_ascii=false` and separators `(',', ':')`, then hash those bytes with SHA-256. This avoids dependence on source JSON object-key ordering and binds the annotation to exact visible turns without hashing hidden source metadata. Adopt explicitly or replace it before the first submission.

## Record of decision

| Field | Lead entry |
|---|---|
| Decision | **Approved and ratified**, as proposed for the six-tactic pilot; no automatic relabeling |
| Research lead | Project research lead (explicit approval recorded in ChatGPT conversation) |
| Date | 2026-10-28 |
| Protocol/schema/validator commit SHAs | Reviewed candidate commit `2ba3414fd1f53eb014e84745a3d8b5a841fc7902` (`v6-protocol-freeze`); the committed ratification record has its own subsequent SHA. Protocol, schema, and validator files at the candidate commit are the approved versions. |
| Authorized future batches/providers | Future 780-record pilot-scope annotation under v6.2.0 approved **in principle**. **Sharing/uploading conversation text with Claude, Gemini, or any third party NOT YET AUTHORIZED**. |
| Pilot relabeling authorized? | **No**; preserve all historical/legacy/adjudicated labels and v6.1.0 files without migration. |
| Notes / dissent | Pilot `any_manipulation` includes exactly the six approved tactics; it must not silently redefine the older seven-class or any other downstream non-pilot target. Unresolved out-of-taxonomy cases are ineligible as verified clean negatives. |
