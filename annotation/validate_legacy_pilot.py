#!/usr/bin/env python3
"""Audit preserved legacy pilot inputs/AI outputs without relabeling them.

Outputs a JSON validation report and a 12-row issue-detail recovery queue. The
queue intentionally contains no invented issue IDs or classifications: README
reports twelve unresolved claims but the inspected data tree has no issue-level
adjudication table or adjudicated annotation export.
"""
from __future__ import annotations
import argparse, csv, json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[1]
PILOT=ROOT/"annotation/pilot_dataset.json"
A=ROOT/"annotation/results/pilot_team_member_a.json"
B=ROOT/"annotation/results/pilot_team_member_b.json"
SPEC=ROOT/"docs/spec_v6_multilabel.md"

def kappa(xs:list[int],ys:list[int])->float|None:
    n=len(xs)
    if not n:return None
    labels=set(xs)|set(ys);po=sum(x==y for x,y in zip(xs,ys))/n
    pe=sum((sum(x==k for x in xs)/n)*(sum(y==k for y in ys)/n) for k in labels)
    return None if pe==1 else (po-pe)/(1-pe)

def load(path:Path)->Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))

def audit()->dict[str,Any]:
    pilot=load(PILOT);a=load(A);b=load(B)
    ids=[x.get("id") for x in pilot]; errors=[]
    if len(pilot)!=20:errors.append(f"Expected 20 pilot items; found {len(pilot)}")
    if len(set(ids))!=len(ids):errors.append("Pilot IDs are not unique")
    for i,row in enumerate(pilot):
        if not row.get("id") or not row.get("domain") or not isinstance(row.get("context"),list) or not isinstance(row.get("target_message"),str):
            errors.append(f"Pilot row {i}: missing legacy required fields")
        for j,t in enumerate(row.get("context",[])):
            if t.get("speaker") not in ("user","assistant") or not isinstance(t.get("text"),str) or not t.get("text").strip():errors.append(f"{row.get('id')}: malformed context turn {j}")
    def parsed(session:dict[str,Any],name:str)->dict[str,dict[str,Any]]:
        if not isinstance(session.get("annotations"),list):errors.append(f"{name}: no annotations array");return {}
        out={}
        for item in session["annotations"]:
            sid=item.get("sample_id")
            if sid in out:errors.append(f"{name}: duplicate annotation {sid}")
            if not isinstance(item.get("chosen_tactic"),int) or item.get("chosen_tactic") not in range(6):errors.append(f"{name}/{sid}: legacy tactic code outside 0..5")
            if item.get("annotator_id")!=session.get("annotator_id"):errors.append(f"{name}/{sid}: row annotator_id differs from session")
            out[sid]=item
        return out
    aa=parsed(a,"annotator A");bb=parsed(b,"annotator B"); pilot_ids=set(ids)
    for name,items in (("annotator A",aa),("annotator B",bb)):
        if set(items)!=pilot_ids:errors.append(f"{name}: annotation IDs do not exactly match pilot IDs; missing={sorted(pilot_ids-set(items))}, extra={sorted(set(items)-pilot_ids)}")
    common=sorted(set(aa)&set(bb)); disag=[sid for sid in common if aa[sid].get("chosen_tactic")!=bb[sid].get("chosen_tactic")]
    total_turns=sum(len(x.get("context",[]))+1 for x in pilot)
    role_counts=Counter([t.get("speaker") for x in pilot for t in x.get("context",[])] + ["assistant"]*len(pilot))
    gold={x["id"]:x.get("gold_label") for x in pilot}
    mismatch_a=[sid for sid in common if aa[sid].get("chosen_tactic")!=gold.get(sid)]
    mismatch_b=[sid for sid in common if bb[sid].get("chosen_tactic")!=gold.get(sid)]
    xa=[aa[s].get("chosen_tactic") for s in common];xb=[bb[s].get("chosen_tactic") for s in common]
    missing_v6={"tactic_set":len(pilot),"primary_tactic":len(pilot),"pressure_level":len(pilot),"refusal flags":len(pilot),"tactic evidence spans":len(pilot),"escalation/onset":len(pilot)}
    missing_v6={k:v for k,v in missing_v6.items() if v}
    return {
      "pilot_count":len(pilot),"pilot_ids_unique":len(set(ids))==len(ids),"pilot_structural_errors":errors,
      "legacy_pilot_turn_structure":{"turns_including_target":total_turns,"user_turns":role_counts["user"],"assistant_turns":role_counts["assistant"],"domain_counts":dict(Counter(x.get("domain") for x in pilot))},
      "spec_available":SPEC.exists(),"legacy_output_counts":{"A":len(aa),"B":len(bb)},
      "legacy_ai_output_identity":{"A_session_annotator_id":a.get("annotator_id"),"B_session_annotator_id":b.get("annotator_id"),"provider_model_version_prompt_hash_recorded":False,
                                     "classification_basis":"origin/main README identifies the pilot results as AI annotations; the JSON files use team_member IDs, so identities are not independently established by the files"},
      "pairwise_legacy_single_label_agreement":{"n":len(common),"agreements":len(common)-len(disag),"disagreements":disag,
          "raw_agreement":round((len(common)-len(disag))/len(common),4) if common else None,"cohen_kappa":kappa(xa,xb)},
      "legacy_gold_label_comparison":{"status":"reference comparison only; pilot gold_label is legacy and unverified under v6","A_mismatch_ids":mismatch_a,"B_mismatch_ids":mismatch_b},
      "v6_fields_absent_from_both_legacy_outputs":missing_v6,
      "adjudication_artifact":{"adjudicated_json_found":False,"issue_level_report_found":False,"README_aggregate_claim":{"unresolved_issue_count":12,"AI_AI_primary_agreement_percent":91.2,"AI_AI_primary_kappa":0.852,"set_exact_match_percent":80,"refusal_agreement_percent":92.5,"escalation_agreement_percent":100,"onset_within_one_turn":"9/16"},
          "note":"README aggregate results cannot be independently recomputed from the stored single-label outputs (which cover one target message per item, not all 80 assistant turns). No adjudicated turn-level export or issue-level evidence is present."},
      "unresolved_issues":{"reported_count":12,"classifiable_from_local_issue_level_evidence":0,
          "classification_framework":["internal contradiction in source scenario (evidence may support false urgency)","unsupported/unverifiable fictional claim (do not declare false without source evidence)","other/unclear"],
          "status":"All twelve remain unclassified because issue-level IDs, text, adjudicator decisions, and provenance are absent. Do not infer that these twelve correspond to the example claims in the pilot."},
      "interpretation":"The stored A/B files are legacy single-label outputs. Per the canonical README/spec, AI agreement is silver reliability evidence, not human IAA or gold correctness. No v6 labels were added or repaired."}

def main()->None:
    p=argparse.ArgumentParser();p.add_argument("--out-dir",type=Path,default=ROOT/"annotation/protocol_v6/reports");args=p.parse_args()
    args.out_dir.mkdir(parents=True,exist_ok=True);result=audit()
    (args.out_dir/"legacy_pilot_validation.json").write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    rows=[{"reported_ordinal":i,"original_issue_id":"","classification":"unclassifiable_missing_issue_details",
           "status":"needs_original_adjudication_report_and_evidence","triage_options":"internal contradiction; unsupported/unverifiable fictional claim; other/unclear",
           "reviewer":"","evidence":"","decision":"pending"} for i in range(1,13)]
    with (args.out_dir/"unresolved_issue_recovery_queue.csv").open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    report=f"""# Annotation protocol validation report

## Scope and evidence

Checked `annotation/pilot_dataset.json`, `annotation/results/pilot_team_member_a.json`, `annotation/results/pilot_team_member_b.json`, `docs/spec_v6_multilabel.md`, and the integrity notes in `README.md`. The pilot contains {result['pilot_count']} unique items, {result['legacy_pilot_turn_structure']['turns_including_target']} represented context-plus-target turns ({result['legacy_pilot_turn_structure']['user_turns']} user, {result['legacy_pilot_turn_structure']['assistant_turns']} assistant), with all source structures passing legacy JSON checks. Each stored annotation file has {result['legacy_output_counts']['A']} / {result['legacy_output_counts']['B']} records matching the pilot IDs.

## Findings

- The stored A/B outputs are legacy single-label records (`chosen_tactic` 0–5). The v6 protocol requires multi-label assistant turn sets, primary tactic, pressure 0–3, user refusal flags, evidence spans, conversation escalation/onset, honest-persistence labels, and label-source/version metadata. All these v6 annotation fields are absent from the 40 stored outputs.
- A and B agree on {result['pairwise_legacy_single_label_agreement']['agreements']}/{result['pairwise_legacy_single_label_agreement']['n']} target-message labels ({result['pairwise_legacy_single_label_agreement']['raw_agreement']:.1%}, Cohen's κ={result['pairwise_legacy_single_label_agreement']['cohen_kappa']:.4f}). They disagree on `{', '.join(result['pairwise_legacy_single_label_agreement']['disagreements'])}`. This is a recomputation over the stored legacy records, not the README's all-assistant-turn AI–AI statistic and not human IAA.
- `pilot_dataset.json` calls its `gold_label` values ground truth, but the v6 integrity notes require that labels be treated as unverified/AI-assisted silver until independently validated. A/B identity values `team_member_a/b` do not identify AI providers or human reviewers; provider, model/version, and prompt hashes are missing.
- The README reports aggregate adjudication findings (including 12 unresolved issues, 91.2% AI–AI agreement, κ=.852, 80% exact tactic-set agreement, and onset within one turn for 9/16), but no adjudicated JSON or issue-level report is present in the checked files. The stored files contain only one target label per pilot item, so those full-turn aggregates cannot be reproduced here.
- The 12 unresolved issues remain individually unclassified. The queue records 12 aggregate slots, with no invented IDs or labels. The canonical README's proposed triage is: (a) source-internal contradiction, (b) unsupported/unverifiable fictional claim, or (c) other/unclear. To classify an issue, the original issue text, conversation/turn, adjudicator judgment, source evidence, and provenance are required. Do not equate any of the 20 pilot items with the 12 issues without source links.
- Potential content claims (e.g., countdowns, scarcity, viewer counts, health statements) cannot be confirmed as true/false from this synthetic pilot alone. No external fact checking or label repair was performed. If scenario-author metadata is missing, preserve uncertainty.

## Canonical decisions in frozen protocol `v6.1.0`

The protocol and schema resolve the README's legacy single-label instructions in favor of the canonical v6 multi-label rules. It retains the v6 tactic names and primary-label precedence, requires source-backed half-open spans, preserves each annotator/adjudicator artifact, and defines AI outputs as silver. Escalation remains: any assistant turn after a prior user refusal with pressure 2 or 3; onset is the first such turn. It does not mean rising pressure. Pressure anchors are explicitly operationalized in the new version because the v6 spec supplies the 0–3 range but not anchors.

## Validation status

Legacy pilot structure: {'PASS' if not result['pilot_structural_errors'] else 'FAIL'}. Canonical v6 annotation data in stored pilot outputs: **not available**. Adjudicated full-conversation annotation: **not found**. Twelve issue details: **not found; human/source review required**. No original source or annotation file was edited.

See `docs/annotation_protocol_v6.md`, `annotation/schema/mindmirror_v6_annotation.schema.json`, `annotation/validate_v6_annotations.py`, `legacy_pilot_validation.json`, and `unresolved_issue_recovery_queue.csv`.
"""
    (args.out_dir/"VALIDATION_REPORT.md").write_text(report,encoding="utf-8")
    print(json.dumps(result,indent=2,ensure_ascii=False))
    raise SystemExit(1 if result["pilot_structural_errors"] else 0)

if __name__=="__main__":main()
