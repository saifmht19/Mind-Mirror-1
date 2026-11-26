# 03 - Module 2: Speech Output + 2B Evaluation Harness (Teammate 2)

Two deliverables. **2A (Kokoro TTS)** is on the critical path for the demo; **2B (evaluation/ablation harness)** produces the paper's numbers.

**You own:** `voice/output/` and `voice/eval/`  **Branches:** `vm/output`, `vm/eval`
**Expose:** `voice.output.build() -> Synthesizer`; CLI `python -m voice.eval.run`

> Command syntax: examples use bash-style env prefixes (`VAR=x cmd`); on Windows PowerShell use `$env:VAR="x"; cmd` (see README, "Environment variables in commands").

## Paste into your AI assistant
> You are implementing Module 2 (Speech output with Kokoro TTS) and 2B (evaluation harness) of the MindMirror voice feature. First read voice/AGENTS.md, voice/contracts.py, voice/config.py, voice/docs/01_ARCHITECTURE_AND_CONTRACTS.md and voice/docs/03_MODULE2_SPEECH_OUTPUT_AND_EVAL.md, plus voice/stubs.py (StubSynthesizer, StubDetector) and voice/tests/conformance.py. Implement a `Synthesizer` (Protocol in contracts.py) in voice/output/ using Kokoro, expose build(), then implement the evaluation harness in voice/eval/ that runs the registry's detectors over a JSONL dataset and writes metrics. Edit only voice/output/ and voice/eval/ (plus pinned lines under the M2 header of requirements-voice.txt). Verify all Kokoro/soundfile/sklearn calls against the installed versions' docs. Finish by walking the Definition of Done checklist.

---
## 2A. Kokoro TTS

### Contract
```python
class Synthesizer(Protocol):
    def synthesize(self, text, out_path, *, voice=None, speed=1.0) -> TTSResult: ...        # ONE wav
    def synthesize_stream(self, text, out_dir, *, voice=None, speed=1.0) -> Iterator[TTSResult]: ...  # one per sentence
```
### Behaviour
- Library: **Kokoro** (`kokoro` package; needs `espeak-ng` installed on the system). Check the current README for the exact pipeline API - it has changed between releases - and pin the version. Default voice `config.KOKORO_VOICE`, language `config.KOKORO_LANG_CODE`. First run downloads weights from Hugging Face: document how to pre-download for offline use.
- Output: WAV PCM 16-bit mono **24 000 Hz** (write with `soundfile`, subtype `PCM_16`). `duration_s` must equal the real file duration.
- **Clean the text before speaking** (`clean_for_speech(text) -> str`, pure function, unit-tested): remove markdown (`*`, `_`, `#`, backticks, code fences -> skip code blocks), replace URLs by the word "link", strip emojis, collapse whitespace, keep sentence punctuation. If nothing speakable remains raise `SynthesisError("nothing to speak")`.
- **Sentence splitting** (`split_sentences(text) -> list[str]`, pure, unit-tested): handle `Dr.`, `Mr.`, `e.g.`, decimals like `3.5`, ellipses, quotes, bullet lists, and very long sentences (split at commas/semicolons above ~300 chars).
- `synthesize_stream`: yields one `TTSResult` per sentence, in order, written to `out_dir/chunk_0000.wav`, `chunk_0001.wav`, ... as each is generated (so the caller can start playback early). `TTSResult.text` is the cleaned sentence.
- `synthesize`: concatenates all sentence audio into one WAV at `out_path`, inserting `config.TTS_SENTENCE_GAP_S` of silence between sentences.
- Validate `speed` in [0.5, 2.0] (`ValueError`) and `voice` against the voices actually available (`SynthesisError` otherwise).
- Load the pipeline lazily once behind a `threading.Lock`; serialize synthesis calls. Wrap failures in `SynthesisError`. Never write outside `out_path` / `out_dir`.
- `engine = "kokoro"`.

### Files
```
voice/output/__init__.py   # build()
voice/output/kokoro_tts.py
voice/output/text_clean.py # clean_for_speech, split_sentences
voice/output/cli.py        # python -m voice.output.cli say "text" [--out x.wav] [--play]
voice/output/MODULE_README.md
voice/output/tests/
```
Browser playback belongs to Module 4; your `--play` (sounddevice) is only a developer convenience.

### Tests
Fast: `clean_for_speech` and `split_sentences` table tests (markdown, URL, emoji, abbreviations, decimals, empty input).
Real (`@pytest.mark.real`): conformance `check_synthesizer`; stream yields >= 2 chunks for 2 sentences and files exist; 24 kHz mono 16-bit; `speed=1.5` is shorter than `speed=1.0`; unknown voice -> `SynthesisError`.
Run: `VOICE_TEST_REAL=output pytest voice -m real -q`.

### Performance (record in MODULE_README.md)
Time-to-first-chunk and real-time factor on CPU for a 3-sentence reply. Target: first chunk < 2 s.

### Pitfalls
espeak-ng missing (on Windows install it from the espeak-ng releases and make sure it is on PATH); torch tensor vs numpy when writing files; sample-rate mismatch (24 kHz, not 22.05/16 kHz); sentences that exceed Kokoro's per-pass limit; empty chunk after cleaning; Windows file locks when overwriting a playing wav.

---
## 2B. Evaluation / ablation harness (`voice/eval/`)

### Goal
Compare detectors `text`, `context`, `context_voice` on the same data and produce tables for the paper. The harness uses detectors **only** through `registry.get_detector(name, impl="real")` and voice only through `registry.get_feature_extractor`.

### Dataset format (JSONL, one conversation per line)
```json
{"id":"ex001",
 "turns":[{"role":"user","text":"...","audio_path":"clips/ex001_u0.wav"},
          {"role":"assistant","text":"..."}],
 "target_index":1,
 "label":1,
 "tactics":["guilt_tripping"],
 "voice_role":"user",
 "escalation_onset_index":null}
```
`target_index` = the assistant turn to judge; `label` = gold 0/1; `tactics` optional; `voice_role` is `"user"`, `"dataset_speaker"` or `null` (no audio). Audio is optional: with no audio, `context_voice` must equal `context` and the report says so.
**Do not commit datasets or audio.** The research corpus is intentionally kept out of the public repo; reference it by local path only, and never put corpus text into docs, tests or sample files. Write one small adapter per source dataset in `voice/eval/datasets/<name>.py` that yields `EvalExample` (define it in `voice/eval/schema.py`, pydantic, frozen).

### Run
```
python -m voice.eval.run --data <path-to>/set.jsonl --detectors text,context,context_voice \
       --out .voice_runtime/results/ --limit 200 --max-qps 2 [--no-cache]
```
Per example: build `Turn`s; if user turns have `audio_path`, extract `VoiceFeatures` for each (role from `voice_role`) and attach to `Turn.voice`; then call each detector as `analyze(history_before_target, target_turn, voice_of_triggering_user_turn)`.

### Outputs (`.voice_runtime/results/<run_id>/`, git-ignored; copy the final tables you cite into `voice/docs/results/`)
- `predictions.jsonl`: per example and detector: score, flagged, tactics, used_voice, latency_ms, error.
- `metrics.csv` and `summary.md`: accuracy, precision, recall, F1, AUROC (on `manipulation_score`), macro-F1 over tactics (if present), **95% bootstrap CI** (1000 resamples, fixed seed) and **paired bootstrap** delta of each detector vs `context`.
- `config.json`: git SHA, contract version, detector names, model versions, seed, timestamp, dataset hash, counts of errors/skipped.
- **Report `voice_role` as its own column and never pool `user` with `dataset_speaker` results.**

### Engineering requirements
- Disk cache `.voice_runtime/results/.cache/` keyed by sha256 of (detector name, serialized inputs incl. voice cues) so reruns never re-call Gemini; `--no-cache` disables.
- Rate limiting (`--max-qps`) with exponential backoff on API errors; a failed example is recorded with `error` and excluded from metrics but **counted and reported**.
- Deterministic: sorted processing, fixed seed, no hidden randomness.
- Must run with `VOICE_IMPL_DETECTOR=stub` on a tiny sample file (include `voice/eval/sample_data/tiny.jsonl`, 10 examples) so it is testable without network.

### Tests
Metrics against hand-computed tiny cases; paired bootstrap sanity (identical detectors -> delta 0); cache hit on second run; error rows excluded but counted; end-to-end run on `tiny.jsonl` with stubs.

## Definition of Done
- [ ] 2A: `build()` passes `check_synthesizer` with `VOICE_TEST_REAL=output`; 24 kHz mono 16-bit WAV; streaming works
- [ ] `clean_for_speech` / `split_sentences` have table tests incl. edge cases
- [ ] CLI `say` works; time-to-first-chunk and RTF recorded
- [ ] 2B: `python -m voice.eval.run` works on `tiny.jsonl` with stubs and writes all outputs
- [ ] Cache, rate limit, error accounting, paired bootstrap implemented and tested
- [ ] `voice_role` is a reported dimension and never pooled
- [ ] MODULE_README.md for both parts; requirements pinned under the M2 header; `pip check` clean
