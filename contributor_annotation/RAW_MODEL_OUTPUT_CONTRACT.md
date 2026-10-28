# Raw v6.2.0 model output contract

This is an intermediate format for the deterministic postprocessor. It is not schema 2.0.0 and must not be described as validated annotation. Save the provider's unmodified response as UTF-8 JSONL, one object per input conversation. A JSON code fence, commentary line, omitted turn, or truncated object is an error; preserve the original response and correct the export as a separate raw file.

Each row contains exactly these top-level keys:

```json
{
  "conversation_id": "dummy-001",
  "turns": [
    {"turn_index": 0, "speaker": "user", "text": "DUMMY: No, thank you."},
    {"turn_index": 1, "speaker": "assistant", "text": "DUMMY: Understood."}
  ],
  "turn_annotations": [
    {"turn_index": 0, "speaker": "user", "refusal": true,
     "refusal_span": {"quote": "No, thank you."}},
    {"turn_index": 1, "speaker": "assistant", "tactic_set": [],
     "primary_tactic": "neutral", "pressure_level": 0, "tactic_spans": [],
     "out_of_taxonomy_suspected": false, "review_required": false}
  ],
  "conversation_annotation": {"honest_persistence": false}
}
```

The example is invented solely to show structure; it is not a dataset record. Replace every `DUMMY` string only in a test fixture, never in submitted source text.

## Field rules

- `turns` must exactly reproduce the input row's ordered `turns` array, including every text code point and the turn indexes and speakers. Do not normalize whitespace or Unicode.
- A user turn has explicit Boolean `refusal` and a present `refusal_span`. Use `null` when false. When true, use `{"quote":"exact substring"}`. If the substring occurs more than once in that turn, add `"context_quote":"a unique exact larger substring containing it once"`. Quotes must be verbatim; no offsets.
- An assistant turn has explicit `tactic_set`, `primary_tactic`, integer `pressure_level`, `tactic_spans`, `out_of_taxonomy_suspected`, and `review_required`. Every tactic span has `tactic` and exact `quote`, with `context_quote` only when needed to identify a repeated quote. Unsupported labels, missing evidence, and unresolved quote ambiguity fail closed.
- `conversation_annotation.honest_persistence` is an explicit semantic judgment and may not be inferred by the postprocessor. The postprocessor derives `any_manipulation`, `clean_negative_eligible`, `escalating`, and `onset_turn_index`. If a raw model row includes any of those derived fields, the tool checks them and rejects disagreement; it never silently changes the judgment.
- `notes` may be added to a turn or conversation annotation as text. Suspected out-of-taxonomy cases require assistant-turn `notes` explaining the concern.
- Do not include schema/guideline version, hashes, provider/model metadata, timestamps, numeric offsets, `annotator`, or other postprocessor-owned fields. Supply actual provider/model/version values to the command-line tool from the provider UI or run record; never guess them.

## Failure handling

The postprocessor rejects missing, duplicate, or extra conversation IDs; missing records/turns/semantic fields; source changes; malformed or unsupported labels; quote mismatch; ambiguous repeated quotes without a unique context; inconsistent supplied derived values; and schema or approved Python-validator errors. On failure, it writes no normalized output. Keep the raw response unchanged, route the issue to the human-review queue, and request a corrected response as a new file. Never add a semantic judgment to make a row pass.
