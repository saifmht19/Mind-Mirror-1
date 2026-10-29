# MindMirror v6 — Annotation integrity and research readiness

> Moved unchanged from the root README so the README can introduce the app. Only headings and links were adjusted.

> **Research status:** The v6 synthetic-conversation dataset and its AI-assisted pilot are **not human-verified gold-standard data**. The earlier v1 single-label taxonomy ([taxonomy_v1.md](taxonomy_v1.md)) is historical; v6 uses its own multi-label specification in [`spec_v6_multilabel.md`](spec_v6_multilabel.md).

- **Freeze annotation rules before scaling.** Finalize and version the v6 taxonomy, refusal criteria, primary-label precedence, pressure scale, tactic-span rules, and the operational definition of escalation. Keep an immutable copy of the pilot guidelines and a dated revision/changelog. Record the guideline version used for every annotation batch.
- **Retain provenance and independent judgments.** Preserve original conversation text and both independent AI annotation files unchanged. Keep adjudicated labels, disagreement reports, unresolved cases, model identities, and validation reports as separate derived artifacts. AI–AI agreement is not human inter-annotator agreement.
- **Verify before expansion.** Independently validate the adjudicated 20-conversation pilot against the original JSONL and full v6 specification, including turn indices, canonical tactic IDs, multi-label consistency, exact zero-based half-open evidence spans, and escalation/onset logic. The reported adjudication left **12 unresolved issues** requiring review; these must not be silently converted into certain labels.
- **Avoid evaluation leakage.** Review scenario-grouping conflicts before making group-aware train/validation/test splits. Do not treat `card_id`, lexical similarity, or generator-intended labels as verified ground truth. Keep related scenario variants in the same split.
- **Document evidence limits.** The 800 synthetic conversations have not yet received verified turn-level labels. AI-adjudicated labels should be described as *silver-standard*. Independent human review of a representative sample and testing on external/held-out data are strongly recommended before confirmatory evaluation or publication claims.

**Important:** If the guidelines change after pilot adjudication, document what changed and reannotate or revalidate affected examples under the new version. Do not mix annotation batches based on different definitions without tracking their versions.


## v6 pilot findings (AI-adjudicated; preliminary)

The 20-conversation pilot contains **160 turns (80 user / 80 assistant)** across four domains. The AI-adjudicated report records **51 user-refusal turns**, **44 tactic-positive assistant turns**, **16/20 conversations meeting the v6 post-refusal high-pressure rule**, and **3 conversations with candidate honest persistence**. These are **pilot-specific counts, not population prevalence**.

| Tactic (multi-label) | Assistant-turn count |
|---|---:|
| Pressure after refusal | 35 |
| False urgency | 10 |
| Guilt-tripping | 9 |
| Dismissing user choice | 8 |
| Fear appeals | 6 |
| Excessive flattery | 5 |

Two independent AI annotators achieved **91.2% primary-tactic agreement (Cohen's κ = 0.852)**, **80% exact tactic-set match**, **92.5% user-refusal agreement**, and **100% agreement on the conversation-level post-refusal high-pressure flag** on this selected pilot. They **did not consistently agree on onset** (onsets within one turn index: **9/16**). These are **AI–AI** reliability observations, not evidence of label correctness or human agreement. The final adjudication retains **12 externally/semantically unresolved issues**, not necessarily structural errors.

**Escalation terminology:** In the current pilot, `escalating` means **at least one assistant turn after a user refusal has pressure 2 or 3**, with onset at the first qualifying assistant turn. It **does not imply increasing pressure over time**. Analyze actual pressure growth, sustained pressure, and post-refusal high pressure as distinct measures. Do not silently reinterpret the existing schema flag.

## Research checklist before training and publication

- [ ] **Verify against the full v6 spec.** Check adjudicated annotations against [`spec_v6_multilabel.md`](spec_v6_multilabel.md) (the adjudicator did not have this document), original messages, exact span offsets, canonical tactic IDs, primary-label rules, and refusal/onset derivation. Run automated checks after every annotation batch.
- [ ] **Triage all 12 unresolved pilot issues.** Distinguish internally contradicted deadlines from unsupported or unverifiable fictional product claims. Document whether a determination is evidence-backed, uncertain, or requires scenario-author metadata. Do not invent external facts about fictional apps.
- [ ] **Freeze a versioned annotation protocol.** Specify refusal versus initial choice or cancellation; first mild re-offer versus coercive persistence; reasonable warnings versus fear appeals; evidence standard for false urgency; context-dependent pressure levels; and overlapping, minimal supporting spans. Keep revision history and revalidate affected labels after edits.
- [ ] **Retain independent annotation provenance.** Keep both original AI labels, disagreement fields, adjudicator decisions, model family/version, prompts, dates, schema versions, input hashes, and final silver-standard output separate. Correct misidentified annotator IDs in derived metadata only.
- [ ] **Balance and assess the full dataset.** Pilot counts show many more post-refusal pressure examples than other tactics; verify class support, domain diversity, respectful persuasion hard negatives, realistic dialogue, refusal patterns, and potential annotation shortcuts across all 800. Do not infer full-dataset proportions from the pilot.
- [ ] **Resolve scenario grouping before splitting.** Prior audit reported **555 candidate edges, 50 contradictory-signal edges, and 392 conversations without candidate links**. Treat these as review candidates, not confirmed pairs. Keep scenario/template variants together across train/validation/test and account for generator leakage.
- [ ] **Recover provenance where possible.** The audit reported missing generator-family metadata on **705 records**, and missing model/date on **155 records each**. Record unknown provenance as unknown rather than fabricating it. The standalone wellness domain mentioned in the v6 spec was not represented in the four-domain 800-conversation set.
- [ ] **Scale labeling with quality controls.** Keep the 20 pilot conversations separate as a calibration set; independently label the other conversations under the frozen protocol. Review disagreements and uncertainty; ideally obtain **independent human validation** on a stratified subset, especially ambiguous and rare tactics. Never call AI-only adjudication human gold standard.
- [ ] **Evaluate the actual research claim.** Compare single-turn and context-aware baselines, history-window ablations, refusal-conditioned features, escalation/pressure-change baselines, and long-context alternatives. Include held-out generator/domain tests, external manipulation and honest-persuasion benchmarks, per-tactic precision/recall, class supports, uncertainty, significance, and error analysis. Avoid claims of generalization from synthetic-only testing.
- [ ] **Document limitations in the paper.** Report synthetic data provenance, selection and generator biases, AI–AI agreement versus human reliability, unresolved claims, label subjectivity, scenario grouping decisions, and the difference between post-refusal high pressure and true escalation.

**Publication gate:** Structural JSONL validation alone is not evidence that labels are semantically correct or that the dataset is ready for confirmatory evaluation. Finalize the protocol, independently validate labels, make leakage-safe splits, and test on genuinely held-out/external data before publication claims.
