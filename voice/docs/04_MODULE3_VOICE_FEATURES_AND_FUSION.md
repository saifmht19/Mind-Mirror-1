# 04 - Module 3: Voice Features + Fusion Detector (Teammate 3)

**Mission:** (3a) turn a user's audio into a fixed set of numeric voice features, and (3b) feed them into the
existing Gemini context detector as *weak, relative evidence* so we get the third model: `context_voice`.
This is the research core; precision of definitions matters more than volume of features.

**You own:** `voice/features/` and `voice/fusion/`  **Branches:** `vm/features`, `vm/fusion`
**Expose:** `voice.features.build() -> FeatureExtractor`, `voice.fusion.build() -> Detector` (name `context_voice`)

> Command syntax: examples use bash-style env prefixes (`VAR=x cmd`); on Windows PowerShell use `$env:VAR="x"; cmd` (see README, "Environment variables in commands").

## Paste into your AI assistant
> You are implementing Module 3 (voice features + fusion detector) of the MindMirror voice feature. First read voice/AGENTS.md, voice/contracts.py, voice/config.py, voice/docs/01_ARCHITECTURE_AND_CONTRACTS.md and voice/docs/04_MODULE3_VOICE_FEATURES_AND_FUSION.md, plus voice/stubs.py, voice/tests/fixtures.py (synthetic clip with known ground truth) and voice/tests/conformance.py. Implement (a) a `FeatureExtractor` using librosa with the exact feature definitions in the doc and (b) a `context_voice` `Detector` that wraps `adapters.build_context_detector()` and passes a rendered cue block via its `notes=` argument. Edit only voice/features/ and voice/fusion/ (plus pinned lines under the M3 header of requirements-voice.txt). Verify librosa/opensmile calls against installed versions. Finish by walking the Definition of Done checklist.

---
## 3a. Feature extraction

### Contract
```python
class FeatureExtractor(Protocol):
    def extract(self, audio_path, segments=None, *, role="user") -> VoiceFeatures: ...
```
Input is the canonical WAV (16 kHz mono). Stateless and deterministic. `VoiceFeatures.features` must contain **exactly** the keys in `VOICE_FEATURE_NAMES` (13). Unavailable => `None`, **never NaN/inf**.

### Exact definitions (use these; do not invent variants - eval and fusion depend on them)
Framing: load with `librosa.load(path, sr=16000, mono=True)`. RMS: frame 25 ms (400), hop 10 ms (160).
1. **Speech frames:** `rms > max(0.1 * percentile(rms, 95), 1e-4)`, then median-filter 5 frames. If there are no speech frames => return all features `None` (valid result; do not raise).
2. **Speech span:** first speech frame start to last speech frame end (seconds). Leading and trailing silence are *not* pauses.
3. **Internal pause:** a maximal run of non-speech frames strictly inside the span with duration >= `config.PAUSE_MIN_S` (0.25 s). Always energy-based, regardless of `segments`, so live and dataset audio use one definition.
4. `pause_count` = number of internal pauses (float). `mean_pause_s` = mean duration (None if 0 pauses). `pause_ratio` = total pause time / span (0.0 if no pauses).
5. **f0:** `librosa.pyin(y, fmin=65, fmax=400, sr=16000, frame_length=1024, hop_length=160)` restricted to speech frames; voiced = not NaN. `f0_mean_hz`, `f0_std_hz`, `f0_range_hz = p95 - p5`. If fewer than 10 voiced frames => the three are `None`.
6. **Energy:** `rms_mean`, `rms_std` over speech frames (linear scale; not loudness-normalized).
7. `voiced_ratio` = voiced frames / speech frames.
8. **Rates (need `segments`):** `word_count` = whitespace tokens across all segment texts. `speech_rate_wps = word_count / span`; `articulation_rate_wps = word_count / (span - total_pause_time)` (None if denominator <= 0). **If `segments` is None/empty => both `None` (never guess).**
9. `jitter_local`, `shimmer_local`: optional, from `opensmile` (eGeMAPSv02) if installed, else `None`.
10. `extractor = "librosa-pyin"`, `version = "1.0.0"`, `duration_s` = real file duration, `role` echoed, `audio_path` echoed.

### Ground truth to test against
`voice/tests/fixtures.py::synth_speechlike` creates a 3 s clip with f0 = 150 Hz and exactly 2 pauses (0.30 s and 0.40 s).
`SPEECHLIKE_TRUTH` holds the expected values. Strict conformance requires: f0_mean within 10 % of 150, `pause_count == 2`, mean pause within 0.08 s of 0.35, pause ratio within 0.06 of 0.2917, word rates `None` without segments, and `6 words / 2.4 s = 2.5` (+/-0.3) with the provided segments. (A quick librosa check of this fixture gives f0 ~ 150.2, pauses 0.29 s and 0.39 s - well within tolerance.)
Real clips from Module 1 (`voice/tests/fixtures/real/`, git-ignored and shared privately; these tests **skip** when the clips are absent): assert direction only (`hesitant` has higher pause_ratio than `neutral`; `fast` has higher speech_rate than `hesitant`; `raised` has higher f0_mean than `neutral` *if the same speaker*).

### Files
```
voice/features/__init__.py       # build() -> extractor
voice/features/extractor.py
voice/features/framing.py        # speech-frame / pause logic (pure functions, unit-tested)
voice/features/cli.py            # python -m voice.features.cli extract clip.wav [--segments segs.json]
voice/features/MODULE_README.md
voice/features/tests/
```

### Pitfalls
`pyin` is slow on long audio - run it only on the speech region and cap at `MAX_UTTERANCE_S`; octave errors (don't "fix" them silently, document); stereo/other sample rates (you receive canonical audio, but resample defensively with librosa); NaN leaking into `features` (convert to None); microphone gain makes absolute `rms` meaningless across sessions - that is why fusion only uses **relative** deltas; do not analyze Kokoro audio.

---
## 3b. Fusion detector (`context_voice`)

### Idea
Compare this user turn's voice with the same user's **own earlier turns** in the session and describe notable shifts in one short text block that is given to Gemini as **weak evidence**. If there is no baseline or no notable shift, behave exactly like the existing `context` detector.

### Baseline (`voice/fusion/baseline.py`)
`compute_baseline(history) -> Optional[dict[str, float]]`
- Collect `.voice` from **user** turns in `history[:-1]` (exclude the triggering user turn) where `voice.role == "user"` and not all features are `None`.
- Need **>= 2** such turns, otherwise return `None` ("no baseline yet").
- Per-feature **median** ignoring `None`.
`compute_deltas(voice, baseline) -> dict[str, Optional[float]]`
- Relative delta `(x - base) / base` for: `f0_mean_hz f0_std_hz f0_range_hz rms_mean rms_std speech_rate_wps articulation_rate_wps mean_pause_s` (None if `base <= 1e-6` or either side `None`).
- Absolute delta `x - base` for: `pause_count pause_ratio voiced_ratio jitter_local shimmer_local`.

### Cue rendering (`voice/fusion/render.py`)
`render_voice_notes(voice, baseline) -> Optional[str]` returns `None` when baseline is `None` or no cue passes its threshold.
Thresholds (constants at the top of the file; tune later, keep them in one place):
relative features: |delta| >= 0.15; `pause_ratio` abs >= 0.08; `pause_count` abs >= 2; others ignored for rendering in v1.
Pick at most **3** cues, ordered by |delta| (relative) then by feature order in `VOICE_FEATURE_NAMES`.
Wording (exact template, so results are reproducible):
```
VOCAL CUES (the user's most recent spoken message compared with their own earlier messages in this session):
- speech rate down 24%
- pauses up (pause ratio 0.31 vs 0.12)
These cues are weak, noisy evidence about the user's reaction. Never infer a specific emotion from them.
Judge manipulation from the text; use the cues only to adjust confidence about pressure or escalation.
```
Cue phrases: "<feature label> up/down N%" for relative features (labels: pitch, pitch variability, pitch range, loudness, loudness variability, speech rate, articulation rate, pause length), and "pauses up/down (pause ratio X vs Y)" / "more/fewer pauses (N vs M)" for the absolute ones.

### The detector (`voice/fusion/detector.py`)
```python
class ContextVoiceDetector:
    name = "context_voice"
    def __init__(self, context_detector): ...        # build() passes adapters.build_context_detector()
    def analyze(self, history, turn, voice=None):
        if voice is None:
            s = ctx.analyze(history, turn, None)
            return s.model_copy(update={"detector": "context_voice", "used_voice": False})
        notes = render_voice_notes(voice, compute_baseline(history))
        s = ctx.analyze(history, turn, None, notes=notes)          # IP-1 in adapters.py
        return s.model_copy(update={"detector": "context_voice", "used_voice": notes is not None})
```
Rules: with `voice=None` (or `notes=None`) the prompt and result must be **identical** to `context`. Keep `tactics`, `pressure`, `user_refusal`, `evidence`, `running_risk` and `raw` exactly as the context detector returned them (`model_copy` only `detector`, `used_voice`, `explanation`); never recompute the project's running-risk formula. Gemini receives only this text block, never audio or raw features. `used_voice` is true only when `notes` was actually sent. Wrap errors in `DetectionError`. Add one sentence to `explanation` when voice was used.
Dependency: the Integrator must implement IP-1/IP-2 in `adapters.py`. Until then develop against a fake context detector in your tests (a class recording the `notes` it received).

### Tests (3b)
Baseline: <2 prior turns => `None`; median correctness; excludes triggering turn and `role != "user"` voices.
Deltas: relative vs absolute; `None` handling; zero baseline.
Render: golden-string tests for at least 5 scenarios (no cue, one cue, three cues cap, tie-break order, pause cues).
Detector: `voice=None` passes through unchanged; notes forwarded exactly; `used_voice` honest; inputs not mutated; conformance `check_detector` with a fake context detector; and (with Integrator IP-2 done) a regression test that `build_prompt(..., notes=None)` is unchanged.

### Optional experiments (only after the required parts are merged)
E1 send raw audio to Gemini multimodal; E2 trained late fusion (logistic regression on context score + deltas); E3 emotion embeddings. Each must implement `Detector`; adding a new `DetectorName` requires a contract change (doc 06). Do not add them to the registry yourself.

## Definition of Done
- [ ] `voice.features.build()` passes strict conformance (`VOICE_TEST_REAL=features`) on the synthetic fixture
- [ ] All 13 keys always present; no NaN/inf anywhere; no-speech clip returns all `None` without raising
- [ ] Feature definitions identical to section 3a (unit tests for framing/pause logic)
- [ ] Real-clip directional checks pass
- [ ] Baseline, deltas, renderer, detector tests pass, incl. golden strings and `voice=None` equivalence
- [ ] `extract()` of a 10 s clip measured and recorded (target < 3 s on CPU)
- [ ] CLI works; MODULE_README.md lists every definition, threshold and known limitation
- [ ] Requirements pinned under the M3 header; `pip check` clean
