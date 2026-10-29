# MindMirror Live Simulator Implementation Plan

Goal: Add local Ollama chat and independent Gemini analysis to the existing React/FastAPI application.
Architecture: Add a simulator router/service and a separate LiveSimulator component, reuse existing Analysis response, Results and charts. Conversations remain browser-managed; no server reset endpoint needed.
Spec: User task of 29 October 2026. Preserve all research files and existing uncommitted work.

- [x] Verify official Ollama install, actual hardware, service, llama3.2:3b and custom Modelfile.
- [x] Write failing tests for validated history, STOP DEMO bypass, offline/timeout handling and role mapping.
- [x] Implement bounded loopback-only Ollama service, scenario allowlist, neutral control, metadata and routes.
- [x] Write UI workflow tests for automatic detection, independent payload, stopping/reset and duplicate-send prevention.
- [x] Add side-by-side simulator UI using existing result components; retain prior analysis with clear version labels on detector failure.
- [x] Capture real saved examples through existing Gemini validation with provenance; label replay as prerecorded.
- [x] Run full regressions, production build and actual local generation→Gemini checks; document exact outcomes.

Ruling: execute immediately without design approval gates as explicitly requested. Local GPU inspection reports Intel Iris Xe and ~16 GB RAM, not the RTX 4060 described in the task. Start with requested 3B model and measure CPU latency. No training or dataset edits.


Verification ledger: official signed Ollama installer 0.40.13; llama3.2:3b and mindmirror-simulator created. Actual hardware Intel Iris Xe, 16 GB RAM; ollama ps reports 100% CPU. Local first response 15.4s. Three actual generation→Gemini checks succeeded: neutral [0], fictional end-chat [1] false-urgency, continuation [1,0] with no continuing pressure. Three real validated recordings saved with independent provenance; none fabricated.
Browser QA: real live neutral exchange and detection, STOP DEMO, reset, prerecorded selection all verified. Prior review finding fixed: preserve 1600-character assistant replies when resending history. Conservative context budget and send-capacity check added. Original detector, research pipelines and datasets unchanged.
Final full suite: 105 Python tests and 12 frontend tests passed at this point; production build passed with existing bundle-size warning. Latest UI-only disclosure/scroll changes receive final frontend rerun.
