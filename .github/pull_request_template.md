## Module / what this PR does
<!-- e.g. [input] ffmpeg normalize + faster-whisper transcribe -->

## Checklist (all must be ticked)
- [ ] Branch is `vm/<module>[-topic]`, rebased on latest `voice-manipulation`, targeting `voice-manipulation`
- [ ] I only changed files I own (or `requirements-voice.txt` under my own header, exact pins)
- [ ] `contracts.py` is untouched
- [ ] `pytest voice -q` is green
- [ ] Conformance passes for my real implementation: `VOICE_TEST_REAL=<kind> pytest voice -m real -q` (paste the tail below)
- [ ] `import voice.<module>` is instant (no model loading / network / subprocess at import)
- [ ] CLI demo works (paste command + output below)
- [ ] `voice/<module>/MODULE_README.md` updated (run instructions, env vars, measured latency, limitations, assumptions)
- [ ] No secrets, no model weights, no voice recordings, no corpus/annotation data committed (public repo)
- [ ] I reviewed all AI-generated code and verified third-party API usage against current docs
- [ ] Definition of Done in my module doc is fully ticked

## Evidence
```
<test output / CLI output / latency numbers>
```

## Known limitations / follow-ups
