# Step 2 notes: paired training data, mapping v2, two-reviewer verification

Branch: `v5-step2-paired-data`. Date: 26 October 2026. Spec reference: MindMirror spec v5, sections 7.2, 8, 9, 10.

## What was added
| File | Purpose |
|---|---|
| `generation/generate_pairs.py` | Generates matched honest / pressure follow-up pairs with an LLM. Splits by pair so a pair never straddles train and test. Records generator provider, model, date, and prompt hash. |
| `annotation/review_sheet.py` | Blind two-reviewer verification: export CSVs without labels, compute Cohen's kappa, list disagreements for a third adjudicator, write a verified JSONL. |
| `annotation/review/reviewer_A.csv`, `reviewer_B.csv` | Blank blind sheets for the 50-record diagnostic suite. Send one to each reviewer. |
| `data/import_chatbotmanip.py --mapping v2` | Opt-in remap. Default stays v1. |
| `tests/test_step2_tools.py` | 8 tests (no API calls). |

## Mapping v2 effect (priority subset, tactics 0-5)
| | v1 (default) | v2 |
|---|---|---|
| Priority rows | 554 | 425 |
| Real rows for Flattery (4) | 65 | 0 |
| Real rows for Repeated Pressure (5) | 64 | 0 |
| Rows sent to 9 (other) | 66 | 195 |

Why: only 22% of the rows mapped from "Reciprocity Pressure" to Tactic 5 contain a user refusal, and "Negging" is insulting, not flattering. v2 removes the mislabeled rows but leaves tactics 4 and 5 with generated data only, so v2 needs the paired data below (and a Flattery generator) before it can be used for headline results.

## ChatbotManip provenance (checked 26 October 2026)
Conversations are simulated between a chatbot and a simulated user, then labeled by human annotators at conversation level (Contro, Deol, He, Brandao, arXiv:2506.12090, June 2025). They are **LLM-simulated**, not natural conversations. The importer comment calling the data non-commercial comes from the dataset's own LICENSE.txt; re-read that file before any release.

## What you need to do
1. **Generate paired data.** The environment that built this branch has no API keys. On your machine, run once per generator family (at least two):
   ```bash
   export OPENAI_API_KEY=...
   python generation/generate_pairs.py --provider openai --model gpt-4o-mini --pairs-per-domain 15
   export GEMINI_API_KEY=...
   python generation/generate_pairs.py --provider gemini --model gemini-2.0-flash --pairs-per-domain 15
   ```
   Output goes to `data/generated/` (gitignored). Every record is `llm_generated_unverified`.
2. **Verify the diagnostic suite.** Give `annotation/review/reviewer_A.csv` to one teammate and `reviewer_B.csv` to another. Each fills `reviewer_label` (0-5) without talking to the other. Then:
   ```bash
   python annotation/review_sheet.py agree --input data/diagnostic/diagnostic_suite_v0.jsonl \
       --a annotation/review/reviewer_A.csv --b annotation/review/reviewer_B.csv \
       --adjudication-out annotation/review/adjudication.csv
   ```
   A third person fills `adjudicated_label` for disagreements, then run `finalize`.
3. **Pick the mapping** (v1 or v2) before the next training run.

## Not done yet
- Group-aware splits for the existing ChatbotManip, generated, and urgency data (the old splitter is random per sample).
- A re-pitch feature (does the reply push the declined offer?) and DeBERTa.
- Real results on verified data. Nothing in this branch produces a paper-ready number.
