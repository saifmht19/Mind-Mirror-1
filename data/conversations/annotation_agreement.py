#!/usr/bin/env python3
"""Calculate pre-adjudication agreement for two annotated pilot JSONL files.

Input format matches annotation_pilot_20.jsonl after each annotator fills the
blank fields independently. This script never fills labels or adjudicates.
"""
import argparse
import json
from pathlib import Path
from typing import Any

TACTICS = ["guilt-tripping", "false urgency", "excessive flattery",
           "pressure after refusal", "fear appeals", "dismissing user choice"]


def load(path: Path) -> dict[str, dict[str, Any]]:
    data = {}
    for n,line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(),1):
        if not line.strip(): continue
        row=json.loads(line); cid=row["conversation_id"]
        if cid in data: raise ValueError(f"Duplicate conversation_id {cid} in {path}:{n}")
        data[cid]=row
    return data


def kappa(a: list[Any], b: list[Any]) -> float | None:
    if not a: return None
    labels=set(a)|set(b); n=len(a)
    observed=sum(x==y for x,y in zip(a,b))/n
    expected=sum((sum(x==k for x in a)/n)*(sum(y==k for y in b)/n) for k in labels)
    return None if expected == 1 else (observed-expected)/(1-expected)


def calculate(a: dict[str,Any], b: dict[str,Any]) -> dict[str,Any]:
    if set(a)!=set(b): raise ValueError("Annotator files must contain identical conversation IDs")
    primary_a=[]; primary_b=[]; tactic_pairs={t:([],[]) for t in TACTICS}
    exact_sets=[]; jaccards=[]; escalation_a=[]; escalation_b=[]; onset_distances=[]
    for cid in sorted(a):
        ra,rb=a[cid],b[cid]
        if len(ra.get("turns",[]))!=len(rb.get("turns",[])): raise ValueError(f"Turn count mismatch for {cid}")
        for ta,tb in zip(ra["turns"],rb["turns"]):
            if ta.get("turn_index")!=tb.get("turn_index") or ta.get("speaker")!=tb.get("speaker"):
                raise ValueError(f"Turn alignment mismatch for {cid}")
            if ta.get("speaker")=="assistant":
                aa=ta.get("assistant_annotation") or {}; ab=tb.get("assistant_annotation") or {}
                pa,pb=aa.get("primary_tactic"),ab.get("primary_tactic")
                if pa is not None and pb is not None:
                    primary_a.append(pa);primary_b.append(pb)
                sa,sb=aa.get("tactic_set"),ab.get("tactic_set")
                if sa is not None and sb is not None:
                    sa,sb=set(sa),set(sb); exact_sets.append(sa==sb)
                    jaccards.append(1.0 if not sa and not sb else len(sa&sb)/len(sa|sb))
                    for tactic,(xs,ys) in tactic_pairs.items(): xs.append(tactic in sa);ys.append(tactic in sb)
        ca=ra.get("conversation_annotation",{});cb=rb.get("conversation_annotation",{})
        ea,eb=ca.get("escalating"),cb.get("escalating")
        if ea is not None and eb is not None: escalation_a.append(ea);escalation_b.append(eb)
        oa,ob=ca.get("onset_turn_index"),cb.get("onset_turn_index")
        if oa is not None and ob is not None: onset_distances.append(abs(int(oa)-int(ob)))
    def raw_agreement(xs,ys): return sum(x==y for x,y in zip(xs,ys))/len(xs) if xs else None
    return {"conversation_count":len(a),"assistant_turn_primary_n":len(primary_a),
            "primary_tactic":{"cohen_kappa":kappa(primary_a,primary_b),"raw_agreement":raw_agreement(primary_a,primary_b)},
            "per_tactic_binary_cohen_kappa":{t:{"cohen_kappa":kappa(*pair),"raw_agreement":raw_agreement(*pair),"n":len(pair[0])} for t,pair in tactic_pairs.items()},
            "tactic_set":{"exact_match_rate":sum(exact_sets)/len(exact_sets) if exact_sets else None,
                          "mean_jaccard":sum(jaccards)/len(jaccards) if jaccards else None,"n":len(exact_sets)},
            "escalating":{"cohen_kappa":kappa(escalation_a,escalation_b),"raw_agreement":raw_agreement(escalation_a,escalation_b),"n":len(escalation_a)},
            "onset":{"within_one_turn_rate":sum(x<=1 for x in onset_distances)/len(onset_distances) if onset_distances else None,"n":len(onset_distances)},
            "note":"Pre-adjudication agreement only. Null means insufficient or degenerate labels; report supports and raw agreement alongside kappa."}


def main() -> None:
    p=argparse.ArgumentParser()
    p.add_argument("annotator_a",type=Path);p.add_argument("annotator_b",type=Path)
    p.add_argument("--output",type=Path,default=Path("agreement_report.json"))
    args=p.parse_args(); result=calculate(load(args.annotator_a),load(args.annotator_b))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps(result,indent=2,ensure_ascii=False))


if __name__=="__main__": main()
