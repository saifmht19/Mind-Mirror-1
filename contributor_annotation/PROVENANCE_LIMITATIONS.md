# Annotation provenance limitations

## Five-conversation technical trial

The locally retained five-record trial outputs are provisional technical-validation artifacts. They are not gold labels and must not be used as verified ground truth. The contributor-reported provider/model labels were “Claude Sonnet 5.5” and “Gemini 3.6 Flash”; exact provider UI or API model identifiers were not available in the local run records. The normalized records therefore preserve an explicit unverified-version marker rather than asserting either label as a verified identifier.

The trial transformation logs contain prompt-file SHA-256 values that match the current Claude and Gemini prompt snapshots. This confirms which prompt bytes the local postprocessor was given. It does not independently establish that those exact bytes were submitted to either provider. Obtain provider-side run records or contributor confirmation tied to the exact prompt artifact before treating prompt provenance as verified.

The raw responses contain conversation IDs, turns, turn annotations, and conversation annotations, but no provider, model/version, or prompt metadata. Their source, output, and normalized-file digests are recorded only in private local transformation logs and are intentionally not copied here or into Git.

The raw responses, normalized outputs, transformation logs, and comparison queue remain private local artifacts. Preserve the raw bytes unchanged. Any correction or provenance enrichment must be recorded as a separate derived artifact; do not relabel the trial outputs or promote them to gold status.

## Before scaling annotation

For each provider run, retain the unmodified provider response, exact prompt artifact and digest, provider-reported model/version identifier, run timestamp, and annotator identity in the private run record. If any item cannot be established, mark it unverified and keep the normalized output provisional. Do not infer a model version from a product label or date.
