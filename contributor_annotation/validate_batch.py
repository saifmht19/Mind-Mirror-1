#!/usr/bin/env python3
"""Validate one annotation batch against its blinded original without altering inputs."""
import argparse
import json
from pathlib import Path

TACTICS={"guilt-tripping","false-urgency","excessive-flattery","pressure-after-refusal","fear-appeals","dismissing-user-choice"}

def records(p):
    out=[]
    for i,line in enumerate(p.read_text(encoding="utf-8-sig").splitlines(),1):
        if line.strip():
            try: out.append(json.loads(line))
            except ValueError as e: raise SystemExit(f"{p}:{i}: {e}")
    return out

def check_span(text, start, end):
    return isinstance(start,int) and not isinstance(start,bool) and isinstance(end,int) and not isinstance(end,bool) and 0<=start<end<=len(text)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--input",required=True,type=Path)
    ap.add_argument("--output",required=True,type=Path)
    ap.add_argument("--annotator",required=True,choices=["AI_ANNOTATOR_A","AI_ANNOTATOR_B"])
    a=ap.parse_args()
    source=records(a.input); done=records(a.output); errors=[]
    sm={x.get("conversation_id"):x for x in source}
    dm={x.get("conversation_id"):x for x in done}
    if len(sm)!=len(source) or len(dm)!=len(done):errors.append("Duplicate conversation IDs")
    if set(sm)!=set(dm):errors.append(f"Missing IDs: {set(sm)-set(dm)}; extra IDs: {set(dm)-set(sm)}")
    for cid in set(sm)&set(dm):
        s=sm[cid];d=dm[cid]
        if s.get("domain")!=d.get("domain"):errors.append(f"{cid}: domain changed")
        st=s.get("turns",[]);dt=d.get("turns",[])
        if len(st)!=len(dt):errors.append(f"{cid}: turn count changed");continue
        for x,y in zip(st,dt):
            idx=x.get("turn_index")
            if any(x.get(k)!=y.get(k) for k in ("turn_index","speaker","text")):
                errors.append(f"{cid}:{idx}: source turn changed");continue
            txt=x["text"]
            if x["speaker"]=="user":
                z=y.get("user_refusal")
                if not isinstance(z,dict) or not isinstance(z.get("refusal"),bool):errors.append(f"{cid}:{idx}: invalid refusal");continue
                if z["refusal"] and not check_span(txt,z.get("span_start"),z.get("span_end")):errors.append(f"{cid}:{idx}: invalid refusal span")
                if not z["refusal"] and (z.get("span_start") is not None or z.get("span_end") is not None):errors.append(f"{cid}:{idx}: nonnull false-refusal span")
            else:
                z=y.get("assistant_annotation")
                if not isinstance(z,dict):errors.append(f"{cid}:{idx}: no assistant annotation");continue
                ts=z.get("tactic_set");primary=z.get("primary_tactic");pressure=z.get("pressure_level_0_3")
                if not isinstance(ts,list) or len(set(ts))!=len(ts) or not set(ts)<=TACTICS:errors.append(f"{cid}:{idx}: invalid tactic set");continue
                if (ts and primary not in ts) or (not ts and primary!="neutral"):errors.append(f"{cid}:{idx}: invalid primary")
                if type(pressure)!=int or pressure not in range(4):errors.append(f"{cid}:{idx}: invalid pressure")
                spans=z.get("tactic_spans")
                if not isinstance(spans,list):errors.append(f"{cid}:{idx}: no spans");continue
                supported=set()
                for span in spans:
                    if not isinstance(span,dict) or span.get("tactic") not in ts or not check_span(txt,span.get("span_start"),span.get("span_end")):errors.append(f"{cid}:{idx}: invalid tactic span")
                    else:supported.add(span["tactic"])
                if set(ts)!=supported:errors.append(f"{cid}:{idx}: missing evidence for {set(ts)-supported}")
        c=d.get("conversation_annotation")
        if not isinstance(c,dict) or c.get("annotator_id")!=a.annotator:errors.append(f"{cid}: wrong annotator_id")
        elif not isinstance(c.get("escalating"),bool) or not isinstance(c.get("honest_persistence"),bool):errors.append(f"{cid}: missing conversation booleans")
        elif c["escalating"] and c.get("onset_turn_index") is None:errors.append(f"{cid}: missing onset")
        elif not c["escalating"] and c.get("onset_turn_index") is not None:errors.append(f"{cid}: unexpected onset")
    if errors:
        print("FAILED with",len(errors),"errors")
        for e in errors[:100]:print("-",e)
        raise SystemExit(1)
    print(f"PASS: {len(done)} annotations align to source (structural checks). Semantic validity requires the frozen protocol.")

if __name__=="__main__":main()
