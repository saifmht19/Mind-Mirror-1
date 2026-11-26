# 06 - Git, Integration and Testing (everyone reads this)

> Command syntax: examples use bash-style env prefixes (`VAR=x cmd`); on Windows PowerShell use `$env:VAR="x"; cmd` (see README, "Environment variables in commands").

## 1. Branch model
- `main`: untouched until the very end.
- **`voice-manipulation`**: the integration branch (git branch names cannot contain spaces). **Protected**: PRs only, >= 1 approval from the CODEOWNER of the touched files, CI/`pytest voice -q` green, linear history (squash merge).
- Feature branches (one per owner, optional sub-branches): `vm/input`, `vm/output`, `vm/eval`, `vm/features`, `vm/fusion`, `vm/orchestrator`, e.g. `vm/input-whisper-timestamps`.
- Create yours: `git checkout voice-manipulation && git pull && git checkout -b vm/<module>`.
- Rebase before opening a PR: `git fetch && git rebase origin/voice-manipulation`. Never force-push a branch other people use. Never push to `main`.
- Commit message: `[module] imperative summary` (e.g. `[input] consume lazy whisper segments`).
- **Do not commit**: `.voice_runtime/`, `.env`, model weights (`*.pt *.onnx *.bin *.safetensors`), **any voice recording** (the repo is public; real test clips stay git-ignored and are shared privately), research-corpus text or annotation data (kept out of the public repo by design).

## 2. Ownership (enforced by `.github/CODEOWNERS`)
Shared files - `contracts.py config.py registry.py stubs.py adapters.py requirements-voice.txt tests/ docs/` - belong to the **Integrator**. Existing project files (`backend/`, existing `frontend/` pages, `requirements.txt`, ...) are changed only as listed in the README table. Everyone else changes them only through an issue + Integrator PR. Each teammate owns exactly the directories listed in `voice/README.md`.
`requirements-voice.txt`: add lines only under your own header, exact pins; run `pip check`; the Integrator installs the combined file into a **fresh venv** at every gate.

## 3. Phases and gates
**Phase 0 - Scaffold (Integrator, first).**
1. Create `voice-manipulation` from `main`, copy in this kit (it adds `voice/`, `requirements-voice.txt`, `.github/`), fill real GitHub handles in `.github/CODEOWNERS`, enable branch protection. Add `.voice_runtime/` to the root `.gitignore` and append `voice/.env.example` to the root `.env.example`.
2. Fill `voice/adapters.py` from the existing `backend/` code: wrap the simulator (`build_generator`, IP-3), the Gemini text detector, and the Gemini context detector **with IP-1 `notes`, IP-2 `build_prompt` and IP-4 output mapping** (tactics, pressure, refusals, evidence, running risk, `raw`).
3. Verify: `pytest voice -q` green; and with `VOICE_IMPL_GENERATOR=real VOICE_IMPL_DETECTOR=real MINDMIRROR_DETECTOR=context` (PowerShell: set each with `$env:NAME="value"`) a manual call works and its `TurnScore` matches what the web app shows for the same conversation.
4. Tag `voice-scaffold-v1`. **Gate G0:** all four teammates run `pytest voice -q` green on their own machines.

**Phase 1 - Parallel build (everyone, no cross-dependencies).** Each module works against stubs/fixtures only.
**Gate G1 (per module):** the module's Definition of Done is fully ticked, PR approved, merged into `voice-manipulation`.

**Phase 2 - Integration (Teammate 4 + Integrator).** Flip components to real **one at a time, in this order**, running the e2e happy path after each flip and pasting the result in a PR/issue:
1. `VOICE_IMPL_INPUT=real`  2. `VOICE_IMPL_OUTPUT=real`  3. `VOICE_IMPL_FEATURES=real`  4. `VOICE_IMPL_DETECTOR=real` + `VOICE_IMPL_GENERATOR=real` with `MINDMIRROR_DETECTOR=context_voice`.
Then the Integrator mounts the router in `backend/main.py` (2 lines, README table) and confirms the existing backend tests, `npm test` and `npm run build` still pass.
**Gate G2:** all-real e2e run succeeds from the browser; failure-matrix checks (kill a component) still degrade gracefully; fresh-venv install works from `requirements.txt` + `requirements-voice.txt`.

**Phase 3 - Evaluation and hardening.** Teammate 2 runs the ablation (`text` vs `context` vs `context_voice`), Teammate 3 reviews feature/cue behaviour on real clips, Teammate 4 records latency per stage. **Gate G3:** results tables + latency report committed under `voice/docs/results/`; README updated; Integrator opens the final PR `voice-manipulation` -> `main`.

## 4. Test commands
| Command | Purpose | When |
|---|---|---|
| `pytest voice -q` | everything not marked `real` (stubs + unit tests); **must always be green** | before every commit/PR |
| `VOICE_TEST_REAL=input pytest voice -m real -q` (PowerShell: `$env:VOICE_TEST_REAL="input"; .\.venv\Scripts\python.exe -m pytest voice -m real -q`) | real Module 1 conformance + tests | M1 owner, before PR |
| `VOICE_TEST_REAL=output ...` / `features` / `detector` | same for M2 / M3 / detectors | owners, before PR |
| `VOICE_TEST_REAL=input,output,features,detector pytest voice -m real -q` | full real suite | Phase 2 gate |
The conformance functions in `voice/tests/conformance.py` are the shared definition of "correct". Owners may add stricter tests inside their own directories but must not weaken or edit the shared ones.

## 5. Contract change process
1. Open an issue titled `contract: <what and why>` with the exact proposed diff to `contracts.py`.
2. All four owners comment approve/reject within one working day. Any blocker is discussed live.
3. The Integrator makes **one PR** that bumps `CONTRACT_VERSION`, updates contracts, stubs, conformance tests and docs together.
4. Everyone rebases the same day. No module merges against an outdated contract version.

## 6. Reviewing AI-generated code (everyone)
- Run it. Read the diff. If you can't explain a block, simplify it.
- AI often recalls **outdated library APIs**: check calls against the installed version's docs; pin the version.
- Confirm it did not edit files outside your directory, add unpinned dependencies, add import-time model loading, print instead of log, hard-code paths/keys, or silently swallow exceptions.
- Check that tests actually assert behaviour (not just "does not crash") and that they fail when you break the code.
- No secrets, no weights, no recordings of other people without consent.

## 7. Common integration failures and the check that catches them
| Failure | Caught by |
|---|---|
| Wrong sample rate / channels / width | `check_speech_input`, `check_synthesizer` |
| Segment timestamps wrong origin | `check_speech_input` (segments inside duration, sorted) |
| NaN or missing features | `VoiceFeatures` validator, `check_feature_extractor` |
| Detector changes behaviour with `voice=None` | `check_detector`, M3 regression test on `build_prompt` |
| Module loads model at import | PR checklist item + reviewer runs `python -X importtime -c "import voice.<module>"` |
| One stage failure breaks the whole turn | M4 failure-matrix tests |
| Real vs stub drift | registry swap test in Phase 2 |

## 8. Final release checklist (Integrator)
- [ ] G0-G3 passed; `pytest voice -q` green on a clean clone; all-real run green
- [ ] `voice/README.md` quick start works from scratch in a fresh venv
- [ ] Every module has a MODULE_README.md; results and latency in `voice/docs/results/`
- [ ] `CONTRACT_VERSION` consistent across docs, `/api/health`, and tag
- [ ] No TODO/NotImplementedError left in shipped code paths (placeholders removed)
- [ ] `.gitignore` respected; no secrets/weights/audio committed
