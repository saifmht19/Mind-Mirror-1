# 02 - Module 1: Speech Input (Teammate 1)

**Mission:** turn whatever audio the browser (or a CLI) provides into a clean canonical WAV, and transcribe it
with Whisper, returning word-level timings. Everything downstream depends on getting the format and timestamps right.

**You own:** `voice/input/`  **Branch:** `vm/input`  **Expose:** `voice.input.build() -> SpeechInput`

> Command syntax: examples use bash-style env prefixes (`VAR=x cmd`); on Windows PowerShell use `$env:VAR="x"; cmd` (see README, "Environment variables in commands").

## Paste into your AI assistant
> You are implementing Module 1 (Speech input) of the MindMirror voice feature. First read voice/AGENTS.md, voice/contracts.py, voice/config.py, voice/docs/01_ARCHITECTURE_AND_CONTRACTS.md and voice/docs/02_MODULE1_SPEECH_INPUT.md, plus voice/stubs.py (StubSpeechInput) and voice/tests/conformance.py (check_speech_input). Implement a class that satisfies the `SpeechInput` Protocol using ffmpeg (normalize) and faster-whisper (transcribe) in voice/input/, expose `build()` in voice/input/__init__.py, add a CLI, tests and MODULE_README.md. Edit only voice/input/ (and add pinned lines under the M1 header of requirements-voice.txt). Verify every library call against the installed version's docs. Finish by walking the Definition of Done checklist.

## 1. Contract you must satisfy
```python
class SpeechInput(Protocol):
    def normalize(self, src_path: str, out_path: str) -> str: ...      # any audio -> canonical WAV; returns out_path
    def transcribe(self, audio_path: str) -> Utterance: ...            # canonical WAV -> Utterance
```
`Utterance`, `Segment`, `AudioFormatError`, `TranscriptionError` come from `voice.contracts`.

## 2. `normalize(src_path, out_path)`
- Convert with ffmpeg via `subprocess` (no extra Python dependency):
  `ffmpeg -nostdin -y -v error -i <src> -vn -ac 1 -ar 16000 -sample_fmt s16 -f wav <out>`
- Input can be webm/opus (Chrome/Firefox MediaRecorder), ogg, mp4/m4a (Safari), mp3, wav at any rate/channel count.
- Create parent directories of `out_path`. Write to a temp name then rename, so a crash never leaves a half file.
- Raise `AudioFormatError` when: ffmpeg fails (include the last line of stderr), the output has zero length, or the duration exceeds `config.MAX_UTTERANCE_S`.
- `build()` must check `shutil.which("ffmpeg")` and raise a clear `RuntimeError("ffmpeg not found; install ...")` if missing (a setup error, not a contract error).
- Return `out_path` unchanged.

## 3. `transcribe(audio_path)`
- Library: **faster-whisper**. Model name, device, compute type from `config.WHISPER_MODEL / WHISPER_DEVICE / WHISPER_COMPUTE_TYPE`.
- Load the model **lazily, once**, behind a `threading.Lock`. Serialize `transcribe` calls with a lock as well (safe default).
- Recommended call: `word_timestamps=True`, `vad_filter=True`, `beam_size=5`, `condition_on_previous_text=False`, `language=None` (auto-detect).
- **The segment iterator is lazy.** You must consume it fully (`list(...)`) or nothing is transcribed.
- Build `Utterance`:
  - `audio_path` = the input path; `sample_rate` = 16000; `duration_s` = real duration read from the WAV header (not from Whisper).
  - `segments` = one `Segment` per **word** (start, end, text stripped); sorted; clamp `end_s` to `duration_s`; drop empty words.
  - `transcript` = words joined by single spaces, stripped.
  - `language` = detected code; `asr_model` = `f"faster-whisper:{config.WHISPER_MODEL}"`.
  - `asr_confidence` = mean word probability, clipped to [0,1]; `None` if no words.
- **No speech => `transcript == ""`, `segments == []`, no exception.** Guard against Whisper hallucinating text on silence/noise (VAD filter + drop output when every segment has a high `no_speech_prob`, e.g. > 0.6).
- Wrap any model failure in `TranscriptionError`.
- Timestamps are seconds from the start of the file you were given.

## 4. Files to create
```
voice/input/__init__.py      # build() -> returns the real SpeechInput
voice/input/ffmpeg_utils.py  # normalize logic
voice/input/whisper_asr.py   # transcribe logic
voice/input/cli.py           # CLI
voice/input/MODULE_README.md
voice/input/tests/test_normalize.py, test_transcribe.py
voice/tests/fixtures/real/   # real speech clips + MANIFEST.json (git-ignored, shared privately; see section 7)
```

## 5. CLI (required)
```
python -m voice.input.cli normalize  <src> <out.wav>      # prints out path
python -m voice.input.cli transcribe <audio.wav>          # prints Utterance as JSON
python -m voice.input.cli record --seconds 8 --out x.wav  # optional: mic via sounddevice, then normalize+transcribe
```

## 6. Tests (put in `voice/input/tests/`)
Fast (no model): webm/m4a/mp3 -> canonical (create them from the synthetic fixture with ffmpeg); 44.1 kHz stereo -> mono 16 kHz;
garbage bytes -> `AudioFormatError`; 61 s audio -> `AudioFormatError`; output is written atomically.
Real (`@pytest.mark.real`): the conformance check passes; a silent WAV gives `transcript==""`; a real speech clip from the
manifest has word error rate < 0.30; segments monotonic and inside the duration; two threads calling `transcribe` at once don't crash.
Run: `VOICE_TEST_REAL=input pytest voice -m real -q`.

## 7. Secondary deliverable: real speech fixtures (needed by Teammate 3) - PRIVACY FIRST
The repository is **public**. A voice recording is personal data, so **do not commit recordings**. `voice/tests/fixtures/real/` is git-ignored.
Record 6 short clips (3-10 s, canonical 16 kHz after normalize) of **yourself or teammates who explicitly agreed**, with no personal information in the words:
`neutral.wav`, `hesitant.wav` (long pauses), `fast.wav` (rushed), `raised.wav` (higher pitch/louder), `silence.wav` (5 s room noise), `noisy.wav`.
Share them privately with Teammate 3 (shared drive / direct transfer), each to be placed in `voice/tests/fixtures/real/` locally, together with a
`MANIFEST.json`: `[{"file":"neutral.wav","transcript":"...","speaker":"T1","notes":"calm, normal pace"}]`.
Tests that need these clips must **skip** (not fail) when the folder is empty, so a fresh clone stays green.

## 8. Performance targets (record measured values in MODULE_README.md)
Real-time factor for `small`/int8 on CPU < 1.0 (ideally < 0.5); `build()` < 1 s; first transcribe (model load) reported separately.

## 9. Pitfalls
ffmpeg missing on PATH (esp. Windows: e.g. `winget install Gyan.FFmpeg`, reopen the terminal, check `ffmpeg -version`) - document the install you used; lazy generator not consumed; Whisper text on silence; timestamps from a
resampled copy; Safari audio is mp4/aac; Chrome sometimes labels audio blobs `video/webm`; paths with spaces (pass argv list, never a shell string).

## 10. Non-goals
Streaming/partial transcripts, speaker diarization, translation, noise suppression, any UI.

## 11. Definition of Done
- [ ] `build()` returns an object that passes `check_speech_input` with `VOICE_TEST_REAL=input`
- [ ] `import voice.input` instant; model loads lazily on first `transcribe`
- [ ] All error paths raise the contract exceptions; no-speech returns `""`
- [ ] Word-level segments, sorted, within duration; `duration_s` from the file
- [ ] CLI works on a real recording (paste output in the PR)
- [ ] Real fixtures + MANIFEST committed
- [ ] RTF and model-load time measured and written in MODULE_README.md
- [ ] Requirements pinned under the M1 header; `pip check` clean
