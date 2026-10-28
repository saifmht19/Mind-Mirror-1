#!/usr/bin/env python3
"""Version-aware structural and cross-turn validation for MindMirror v6.1.0 and ratified v6.2.0 annotation JSONL.

Uses only the Python standard library. It validates evidence spans, role-specific
fields, tactic sets, primary-label precedence constraints, refusal evidence, and
the canonical v6 post-refusal pressure/onset rule. The v6.2.0 ratification is recorded
in v6-protocol-freeze/docs/annotation_protocol_v6.2.0_ratification_checklist.md.
It does not infer labels from
text or adjudicate semantic claims.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

TACTICS_V1 = {
    "guilt-tripping", "false urgency", "excessive flattery",
    "pressure-after-refusal", "fear-appeal", "dismissing-choice", "other-dark-pattern",
}
TACTICS_V2 = TACTICS_V1 - {"other-dark-pattern"}
PRIMARY_V1 = TACTICS_V1 | {"neutral"}
PRIMARY_V2 = TACTICS_V2 | {"neutral"}
LABEL_SOURCES = {"human", "adjudicated", "labeler", "scenario", "mapped"}
HASH = re.compile(r"^[0-9a-f]{64}$")


def source_text_sha256(turns: list[dict[str, Any]]) -> str:
    """Hash exact ordered visible turn values using the v6.2 canonical recipe."""
    canonical = [
        {"turn_index": turn["turn_index"], "speaker": turn["speaker"], "text": turn["text"]}
        for turn in turns
    ]
    payload = json.dumps(canonical, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _span_errors(text: str, span: Any, location: str) -> list[str]:
    if not isinstance(span, dict):
        return [f"{location}: expected span object"]
    start, end = span.get("start"), span.get("end")
    if not isinstance(start, int) or isinstance(start, bool) or not isinstance(end, int) or isinstance(end, bool):
        return [f"{location}: start/end must be integers"]
    if start < 0 or end <= start or end > len(text):
        return [f"{location}: span [{start},{end}) is out of bounds for text length {len(text)}"]
    if not text[start:end].strip():
        return [f"{location}: span selects only whitespace"]
    return []


def validate_record(record: dict[str, Any]) -> dict[str, list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    def err(where: str, message: str) -> None: errors.append(f"{where}: {message}")
    guideline = record.get("guideline_version")
    if guideline == "v6.1.0":
        if record.get("schema_version") != "1.0.0": err("schema_version", "v6.1.0 requires schema 1.0.0")
        tactics, primary_values = TACTICS_V1, PRIMARY_V1
    elif guideline == "v6.2.0":
        if record.get("schema_version") != "2.0.0": err("schema_version", "v6.2.0 requires schema 2.0.0")
        tactics, primary_values = TACTICS_V2, PRIMARY_V2
    else:
        err("guideline_version", "must be v6.1.0 or v6.2.0")
        tactics, primary_values = TACTICS_V1, PRIMARY_V1
    if not isinstance(record.get("conversation_id"), str) or not record["conversation_id"].strip(): err("conversation_id", "required non-empty string")
    if not isinstance(record.get("source_text_sha256"), str) or not HASH.fullmatch(record["source_text_sha256"]): err("source_text_sha256", "must be a lowercase SHA-256 hex digest")
    annotator=record.get("annotator")
    if not isinstance(annotator,dict): err("annotator", "required object")
    else:
        if not annotator.get("annotator_id"): err("annotator.annotator_id", "required")
        if not isinstance(annotator.get("annotator_type"),str) or annotator.get("annotator_type") not in {"human","ai"}: err("annotator.annotator_type", "must be human or ai")
        if annotator.get("annotator_type")=="ai" and any(not annotator.get(k) for k in ("provider","model","model_version","prompt_sha256")):
            err("annotator", "AI labels require provider, model, model_version, and prompt_sha256; unknown values must be explicit strings")

    turns=record.get("turns"); anns=record.get("turn_annotations")
    if not isinstance(turns,list) or not turns: err("turns", "must be a non-empty array");turns=[]
    if not isinstance(anns,list): err("turn_annotations", "must be an array");anns=[]
    if len(turns)!=len(anns): err("turn_annotations", f"expected one entry per turn ({len(turns)}), got {len(anns)}")
    if guideline == "v6.2.0" and turns:
        try:
            expected_hash = source_text_sha256(turns)
            if record.get("source_text_sha256") != expected_hash:
                err("source_text_sha256", "does not match canonical ordered turn text")
        except (KeyError, TypeError) as exc:
            err("source_text_sha256", f"cannot hash malformed source turns: {exc}")
    if turns and not {t.get("speaker") for t in turns if isinstance(t,dict)}.issuperset({"user","assistant"}):
        err("turns", "conversation must contain at least one user and one assistant turn")
    for i, turn in enumerate(turns):
        if not isinstance(turn,dict): err(f"turns[{i}]", "must be an object");continue
        if turn.get("turn_index") != i: err(f"turns[{i}].turn_index", "must be the zero-based array index")
        if not isinstance(turn.get("speaker"),str) or turn.get("speaker") not in {"user","assistant"}: err(f"turns[{i}].speaker", "must be user or assistant")
        if not isinstance(turn.get("text"),str) or not turn.get("text").strip(): err(f"turns[{i}].text", "must be non-empty string")
    aligned={}
    for i, ann in enumerate(anns):
        if not isinstance(ann,dict): err(f"turn_annotations[{i}]", "must be an object");continue
        idx=ann.get("turn_index")
        if not isinstance(idx,int) or isinstance(idx,bool) or idx<0 or idx>=len(turns): err(f"turn_annotations[{i}].turn_index", "must reference an existing turn");continue
        if idx in aligned: err(f"turn_annotations[{i}]", f"duplicate annotation for turn {idx}")
        aligned[idx]=ann
        turn=turns[idx] if isinstance(turns[idx],dict) else {}
        speaker=turn.get("speaker"); text=turn.get("text","") if isinstance(turn.get("text"),str) else ""
        if ann.get("speaker")!=speaker: err(f"turn_annotations[{i}].speaker", "must match source turn role")
        if not isinstance(ann.get("label_source"),str) or ann.get("label_source") not in LABEL_SOURCES: err(f"turn_annotations[{i}].label_source", "must use a canonical label source")
        if speaker=="user":
            if not isinstance(ann.get("refusal"),bool): err(f"turn_annotations[{i}].refusal", "must be an explicit boolean")
            span=ann.get("refusal_span")
            if guideline == "v6.2.0" and "refusal_span" not in ann:
                err(f"turn_annotations[{i}].refusal_span", "required; use null when refusal is false")
            if ann.get("refusal") is True:
                errors.extend(_span_errors(text,span,f"turn_annotations[{i}].refusal_span"))
            elif span is not None: err(f"turn_annotations[{i}].refusal_span", "must be null when refusal is false")
            forbidden={"tactic_set","primary_tactic","pressure_level","tactic_spans","out_of_taxonomy_suspected","review_required"}&set(ann)
            if forbidden: err(f"turn_annotations[{i}]", f"user turn cannot contain assistant fields: {sorted(forbidden)}")
        elif speaker=="assistant":
            if guideline == "v6.2.0":
                forbidden_refusal={"refusal", "refusal_span"}&set(ann)
                if forbidden_refusal: err(f"turn_annotations[{i}]", f"assistant turn cannot contain user refusal fields: {sorted(forbidden_refusal)}")
                if not isinstance(ann.get("out_of_taxonomy_suspected"), bool): err(f"turn_annotations[{i}].out_of_taxonomy_suspected", "must be boolean")
                if not isinstance(ann.get("review_required"), bool): err(f"turn_annotations[{i}].review_required", "must be boolean")
                if ann.get("out_of_taxonomy_suspected") is True:
                    if ann.get("review_required") is not True: err(f"turn_annotations[{i}].review_required", "suspected out-of-taxonomy manipulation must remain in review")
                    if not isinstance(ann.get("notes"), str) or not ann.get("notes").strip(): err(f"turn_annotations[{i}].notes", "suspected out-of-taxonomy manipulation needs a rationale")
                    warnings.append(f"turn_annotations[{i}]: suspected out-of-taxonomy manipulation is not a verified neutral/negative")
            labels=ann.get("tactic_set")
            if not isinstance(labels,list): err(f"turn_annotations[{i}].tactic_set", "must be an array; empty array means neutral") ; labels=[]
            label_strings=[x for x in labels if isinstance(x,str)]
            if len(labels)!=len(label_strings): err(f"turn_annotations[{i}].tactic_set", "tactic values must be strings")
            if len(label_strings)!=len(set(label_strings)): err(f"turn_annotations[{i}].tactic_set", "must not contain duplicate tactics")
            unknown=set(label_strings)-tactics
            if unknown: err(f"turn_annotations[{i}].tactic_set", f"unknown tactic(s): {sorted(unknown)}")
            primary=ann.get("primary_tactic")
            if not isinstance(primary,str) or primary not in primary_values: err(f"turn_annotations[{i}].primary_tactic", "must be a canonical tactic or neutral")
            if not labels and primary!="neutral": err(f"turn_annotations[{i}]", "empty tactic_set requires primary_tactic=neutral")
            if labels and primary not in labels: err(f"turn_annotations[{i}]", "primary_tactic must be a member of the non-empty tactic_set")
            pressure=ann.get("pressure_level")
            if not isinstance(pressure,int) or isinstance(pressure,bool) or not 0<=pressure<=3: err(f"turn_annotations[{i}].pressure_level", "must be an integer from 0 through 3")
            spans=ann.get("tactic_spans")
            if not isinstance(spans,list): err(f"turn_annotations[{i}].tactic_spans", "must be an array");spans=[]
            spans_by_tactic={}
            for j,span in enumerate(spans):
                if not isinstance(span,dict): err(f"turn_annotations[{i}].tactic_spans[{j}]", "must be an object");continue
                tactic=span.get("tactic")
                if not isinstance(tactic,str) or tactic not in tactics: err(f"turn_annotations[{i}].tactic_spans[{j}].tactic", "unknown tactic")
                else: spans_by_tactic.setdefault(tactic,0);spans_by_tactic[tactic]+=1
                errors.extend(_span_errors(text,span,f"turn_annotations[{i}].tactic_spans[{j}]"))
            for tactic in labels:
                if tactic in tactics and not spans_by_tactic.get(tactic): err(f"turn_annotations[{i}]", f"tactic {tactic!r} lacks a supporting span")
            for tactic in spans_by_tactic:
                if tactic not in labels: err(f"turn_annotations[{i}]", f"span provided for absent tactic {tactic!r}")
            # Check the syntactic part of section 7.5 precedence. Semantic re-pitch
            # decisions remain human judgments and are not inferred here.
        else:
            err(f"turn_annotations[{i}]", "invalid speaker")
    if set(aligned)!=set(range(len(turns))): err("turn_annotations", "must annotate each source turn exactly once")

    refusal_indices=[i for i,a in aligned.items() if isinstance(a,dict) and isinstance(turns[i],dict) and turns[i].get("speaker")=="user" and a.get("refusal") is True]
    qualifying=[]
    for i,a in aligned.items():
        if isinstance(turns[i],dict) and turns[i].get("speaker")=="assistant" and isinstance(a,dict):
            if any(r<i for r in refusal_indices) and a.get("pressure_level") in {2,3}:
                qualifying.append(i)
            labels=a.get("tactic_set") if isinstance(a.get("tactic_set"),list) else []
            if "pressure-after-refusal" in labels:
                if not any(r<i for r in refusal_indices): err(f"turn_annotations[{i}]", "pressure-after-refusal requires an earlier annotated refusal")
                elif a.get("primary_tactic")!="pressure-after-refusal": err(f"turn_annotations[{i}].primary_tactic", "section 7.5 makes pressure-after-refusal primary when that re-pitch tactic is present")
    conv=record.get("conversation_annotation")
    if not isinstance(conv,dict): err("conversation_annotation", "required object")
    else:
        if guideline == "v6.2.0":
            expected_any = any(
                isinstance(turns[i], dict) and turns[i].get("speaker") == "assistant"
                and isinstance(ann, dict) and isinstance(ann.get("tactic_set"), list)
                and any(tactic in TACTICS_V2 for tactic in ann["tactic_set"] if isinstance(tactic, str))
                for i, ann in aligned.items()
            )
            unresolved_review = any(
                isinstance(turns[i], dict) and turns[i].get("speaker") == "assistant"
                and isinstance(ann, dict) and ann.get("review_required") is True
                for i, ann in aligned.items()
            )
            expected_clean_negative = not expected_any and not unresolved_review
            if not isinstance(conv.get("any_manipulation"), bool):
                err("conversation_annotation.any_manipulation", "must be an explicit Boolean")
            elif conv.get("any_manipulation") is not expected_any:
                err("conversation_annotation.any_manipulation", f"must equal derived six-tactic value {expected_any}")
            if not isinstance(conv.get("clean_negative_eligible"), bool):
                err("conversation_annotation.clean_negative_eligible", "must be an explicit Boolean")
            elif conv.get("clean_negative_eligible") is not expected_clean_negative:
                err("conversation_annotation.clean_negative_eligible", f"must equal derived value {expected_clean_negative}; unresolved review cases are not clean negatives")
        if not isinstance(conv.get("escalating"),bool): err("conversation_annotation.escalating", "must be boolean")
        if not isinstance(conv.get("honest_persistence"),bool): err("conversation_annotation.honest_persistence", "must be boolean")
        if not isinstance(conv.get("label_source"),str) or conv.get("label_source") not in LABEL_SOURCES: err("conversation_annotation.label_source", "must use a canonical label source")
        expected=bool(qualifying); onset=qualifying[0] if qualifying else None
        if conv.get("escalating") is not expected: err("conversation_annotation.escalating", f"must equal derived value {expected} under the v6 post-refusal pressure >=2 rule")
        if conv.get("onset_turn_index")!=onset: err("conversation_annotation.onset_turn_index", f"must equal first qualifying zero-based assistant turn index {onset}")
        if conv.get("honest_persistence") is True and expected:
            warnings.append("conversation_annotation: honest_persistence=true co-occurs with a pressure-2/3 post-refusal turn; adjudicate this tension rather than changing escalation definition")
    return {"errors":errors,"warnings":warnings}


def validate_jsonl(path: Path) -> dict[str, Any]:
    results=[]
    for line_no,line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(),1):
        if not line.strip(): continue
        try:
            record=json.loads(line)
            if not isinstance(record,dict): raise ValueError("record must be object")
            outcome=validate_record(record)
            if outcome["errors"] or outcome["warnings"]: results.append({"line":line_no,"conversation_id":record.get("conversation_id"),**outcome})
        except Exception as exc:
            results.append({"line":line_no,"conversation_id":None,"errors":[f"JSON parse/record error: {exc}"],"warnings":[]})
    return {"path":str(path),"records_checked":sum(1 for x in path.read_text(encoding="utf-8-sig").splitlines() if x.strip()),
            "records_with_findings":len(results),"error_count":sum(len(r["errors"]) for r in results),"warning_count":sum(len(r["warnings"]) for r in results),"findings":results}


def main() -> None:
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("jsonl",type=Path);p.add_argument("--report",type=Path)
    args=p.parse_args();result=validate_jsonl(args.jsonl)
    rendered=json.dumps(result,indent=2,ensure_ascii=False)
    if args.report:
        args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(rendered+"\n",encoding="utf-8")
    print(rendered)
    raise SystemExit(1 if result["error_count"] else 0)


if __name__=="__main__": main()
