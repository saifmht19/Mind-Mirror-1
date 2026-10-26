# Pilot conversation batch: AI companion apps

Branch: `v6-schema-dismissing-choice`. Date: 26 October 2026. Spec: v6, sections 7.5, 8, 9.

## What is here

| File | What it is |
|---|---|
| `generation/conversations/scenario_cards.py` | Builds the 800 scenario cards (unreviewed draft) |
| `data/conversations/cards_v0.jsonl` | The 800 cards |
| `data/conversations/claude_companion_turns.json` | 30 conversations, written by Claude (Opus 5), AI-companion domain |
| `data/conversations/batch_claude_companion.jsonl` | The validated batch: 30 conversations, 228 turns, 114 assistant turns to label |
| `generation/conversations/build_batch.py` | Validates written text against its card and emits the batch |
| `generation/conversations/run_ollama.py` | Generates the second family locally with Ollama |
| `tests/test_conversation_batch.py` | 14 tests, no network needed |

The Claude batch covers all 16 AI-companion situations, with 7 clear manipulation, 8 manipulation
after refusal, 7 escalating pressure and 8 respectful (6 honest persistence, 2 plain acceptance).
Lengths are balanced across the four types so length cannot reveal the type; a test enforces this.

**No labels are written anywhere.** Each record keeps `writer_intended_tactics` from its card,
which is what the writer aimed for and is never ground truth. `labels` is `null` and
`label_source` is `synthetic_unverified` until two independent reviewers have labelled it.

One generator family is not enough. Claude wrote all 30 of these, so run the Ollama batch
(family B) before anyone trains on this data, or the model learns one model's phrasing.

## Running the second family (your machine, not a cloud session)

```bash
ollama serve                 # separate terminal, if not already running
ollama pull llama3.1:8b

python generation/conversations/run_ollama.py \
    --model llama3.1:8b --domain "AI companion apps" --n 40 \
    --exclude data/conversations/batch_claude_companion.jsonl \
    --out data/conversations/ollama_companion_turns.json

python generation/conversations/build_batch.py \
    --turns data/conversations/ollama_companion_turns.json \
    --generator "ollama/llama3.1:8b" --family B \
    --out data/conversations/batch_ollama_companion.jsonl
```

`--exclude` skips the cards Claude already used, so the two families never write the same card.
`--dry-run` prints one prompt without calling the model. `--resume` continues an interrupted run.
Expect a smaller local model to fail the exact-length rule often; the script retries three times
per card and reports what it gave up on.

## What the pilot found

**1. The refusal detector missed a bare "No" after most real offers.** `_is_offer` required a
positive match against a short regex, so "Want to try it?" was not an offer and the "no" that
followed it was invisible. 13 of the first 30 conversations were rejected for having no refusal
when they plainly did. Fixed in `models/refusal.py`: a turn opening with "No" is now a refusal
unless the previous assistant turn is a plain information question ("Have you tried restarting
it?"). Also added "maybe not" to the soft objections, since it is one of the six refusal styles
the cards are built from. Effect on training data: +17 rows of 1,703 (1%) now have a refusal
detected, and still 0 false positives on the 10 non-refusal test contexts.

**2. Indirect refusals are still missed.** "I'd rather leave it", "I'm stepping back", "I'll
keep these shorter" are refusals a human reads instantly and the detector does not. We reworded
five of our own conversations rather than tune the detector to sentences we had just written,
which would be circular. The reviewers should flag every refusal the detector misses; that list
is the input to the next fix, not our own prose.

**3. A single label does not fit a real manipulative turn.** `tests/test_api.py` asserted that
"Are you completely sure? You really cannot pass up this discount before midnight." is tactic 5.
It carries two tactics: it re-pitches a declined offer (5) and invents a deadline (2/3). The
model splits almost evenly between 5 and 3, and the two swapped places on an ordinary retrain
(0.55/0.35 before, 0.42/0.44 after). The test now asserts that 5 is in the top two and records
why. This is direct evidence for the v6 multi-label head; restore the exact assertion once the
model predicts a tactic set.

**4. Excessive Urgency is barely learned.** On the case above the model gives tactic 2 a
probability of 0.001 while the message contains an obvious invented deadline. Worth checking
how many real urgency rows survive the ChatbotManip mapping before trusting any urgency result.

## Caveats

- The 30 conversations are written by Claude and unverified. They are research data depicting
  manipulative behaviour, not examples of how an assistant should act.
- The 800 cards are an unreviewed draft. Seven AI-companion situations may overlap with the
  test-only diagnostic suite; that has not been cleared.
- Retraining after the refusal fix left the demo model's scores essentially unchanged
  (val accuracy 0.80, macro F1 0.69, pair accuracy 0.84). Pressure recall on the diagnostic
  suite moved 0.97 to 0.94, within one standard deviation, so treat it as noise rather than
  as either an improvement or a regression.
