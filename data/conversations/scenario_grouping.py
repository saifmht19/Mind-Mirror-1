#!/usr/bin/env python3
"""Conservative scenario-link proposals and deterministic leakage-safe split helpers.

No links are accepted automatically. TF-IDF is a candidate signal only; card_id
and manipulation labels are never used. Split assignment requires human-verified
scenario keys and keeps rows without such keys unassigned.
"""
from __future__ import annotations
import argparse, csv, hashlib, itertools, json, re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def norm(value: Any) -> str:
    return " ".join(re.findall(r"\w+", str(value or "").casefold()))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows=[]
    with path.open(encoding="utf-8-sig") as f:
        for no,line in enumerate(f,1):
            if not line.strip(): continue
            row=json.loads(line)
            if not isinstance(row,dict): raise ValueError(f"{path}:{no}: expected JSON object")
            rows.append(row)
    return rows


def read_similarity(path: Path | None) -> list[dict[str,str]]:
    if path is None or not path.exists(): return []
    with path.open(encoding="utf-8-sig",newline="") as f: return list(csv.DictReader(f))


def build_proposals(records: list[dict[str,Any]], similarity_rows: list[dict[str,str]]) -> tuple[list[dict[str,Any]],list[dict[str,Any]],list[dict[str,Any]]]:
    by_id={str(r.get("conversation_id")):r for r in records}
    if len(by_id)!=len(records): raise ValueError("Duplicate or missing conversation_id; resolve before grouping")
    links: dict[tuple[str,str],dict[str,Any]]={}
    def add(a: str,b: str,signal: str,score: Any="") -> None:
        if a==b or a not in by_id or b not in by_id: return
        x,y=sorted((a,b)); e=links.setdefault((x,y),{"signals":set(),"similarity":None})
        e["signals"].add(signal)
        if score not in (None,""):
            value=float(score)
            if not 0<=value<=1: raise ValueError(f"Invalid cosine similarity {value}")
            e["similarity"]=max(value,e["similarity"] or 0.0)
    for row in similarity_rows:
        a,b=row.get("conversation_1",""),row.get("conversation_2","")
        if a in by_id and b in by_id: add(a,b,"tfidf_candidate",row.get("similarity",""))
    # Treat all metadata as fallible evidence. card_id and labels are expressly excluded.
    for field in ("group_id","pair_id","situation"):
        buckets=defaultdict(list)
        for r in records:
            value=norm(r.get(field))
            if value:
                # Repeated scenario IDs across domains are evidence to inspect,
                # not a reason to merge; preserve them as contradictory edges.
                bucket_key=(value,) if field in ("group_id","pair_id") else (norm(r.get("domain")),value)
                buckets[bucket_key].append(str(r["conversation_id"]))
        for members in buckets.values():
            for a,b in itertools.combinations(sorted(members),2): add(a,b,"same_"+field)
    edge_rows=[]
    for (a,b),e in sorted(links.items()):
        x,y=by_id[a],by_id[b]; sig=e["signals"]; conflicts=[]
        if x.get("domain")!=y.get("domain"): conflicts.append("different_domain")
        if x.get("group_id") and y.get("group_id") and x["group_id"]!=y["group_id"] and "same_pair_id" in sig:
            conflicts.append("same_pair_different_group")
        if x.get("pair_id") and y.get("pair_id") and x["pair_id"]!=y["pair_id"] and "same_group_id" in sig:
            conflicts.append("same_group_different_pair")
        if x.get("situation") and y.get("situation") and norm(x["situation"])!=norm(y["situation"]) and ("same_group_id" in sig or "same_pair_id" in sig):
            conflicts.append("shared_id_different_situation")
        metadata_signals={s for s in sig if s!="tfidf_candidate"}
        # Priority tier communicates review order, never probability or acceptance.
        priority="conflict_manual_review" if conflicts else "corroborated_manual_review" if len(metadata_signals)>=2 else "single_signal_manual_review"
        edge_rows.append({"conversation_1":a,"conversation_2":b,"domain_1":x.get("domain",""),"domain_2":y.get("domain",""),
            "review_priority":priority,"tfidf_cosine":e["similarity"] if e["similarity"] is not None else "",
            "evidence":";".join(sorted(sig)),"conflicts":";".join(sorted(set(conflicts))),
            "group_id_1":x.get("group_id") or "","group_id_2":y.get("group_id") or "",
            "pair_id_1":x.get("pair_id") or "","pair_id_2":y.get("pair_id") or "",
            "situation_1":x.get("situation") or "","situation_2":y.get("situation") or "",
            "decision":"pending_human_review","reviewer_id":"","reviewer_notes":""})
    # Only corroborated metadata links create *proposed* connected components.
    # Similarity-only and single-metadata-signal edges stay individual review items.
    parent={cid:cid for cid in by_id}
    def find(cid: str) -> str:
        while parent[cid]!=cid:
            parent[cid]=parent[parent[cid]];cid=parent[cid]
        return cid
    def union(a: str,b: str) -> None:
        ra,rb=find(a),find(b)
        if ra!=rb: parent[max(ra,rb)]=min(ra,rb)
    for row in edge_rows:
        s=set(row["evidence"].split(";"));
        corroborated=(("same_group_id" in s and ("same_pair_id" in s or "same_situation" in s)) or
                      ("same_pair_id" in s and "same_situation" in s))
        if corroborated and not row["conflicts"] and row["domain_1"]==row["domain_2"]:
            union(row["conversation_1"],row["conversation_2"])
    components=defaultdict(list)
    for cid in by_id: components[find(cid)].append(cid)
    proposal_rows=[]
    for members in components.values():
        if len(members)<2: continue
        members=sorted(members); proposal="PROP-"+hashlib.sha256("\n".join(members).encode()).hexdigest()[:12]
        member_edges=[r for r in edge_rows if r["conversation_1"] in members and r["conversation_2"] in members]
        signals=sorted({s for r in member_edges for s in r["evidence"].split(";") if s and s!="tfidf_candidate"})
        for cid in members:
            c=by_id[cid]
            proposal_rows.append({"proposed_group_id":proposal,"conversation_id":cid,"domain":c.get("domain",""),
                "members_count":len(members),"supporting_metadata_signals":";".join(signals),
                "status":"unconfirmed_human_review_required","reviewer_id":"","reviewer_notes":""})
    linked={cid for r in edge_rows for cid in (r["conversation_1"],r["conversation_2"])}
    coverage=[{"conversation_id":str(c["conversation_id"]),"domain":c.get("domain",""),
        "group_id_present":"yes" if c.get("group_id") else "no","pair_id_present":"yes" if c.get("pair_id") else "no",
        "situation_present":"yes" if c.get("situation") else "no","has_candidate_edge":"yes" if str(c["conversation_id"]) in linked else "no"} for c in records]
    return edge_rows,proposal_rows,coverage


def assign_group_splits(records: list[dict[str,Any]], group_field: str="verified_scenario_id",
                         seed: str="mindmirror-v6", ratios: tuple[float,float,float]=(.8,.1,.1)) -> dict[str,str]:
    """Deterministically assign *verified* scenario keys; missing keys stay unassigned."""
    if len(ratios)!=3 or any(x<0 for x in ratios) or abs(sum(ratios)-1)>1e-9:
        raise ValueError("ratios must be nonnegative train/validation/test fractions summing to 1")
    cuts=(ratios[0],ratios[0]+ratios[1]); out={}; seen=set()
    for row in records:
        cid=str(row.get("conversation_id","")); key=row.get(group_field)
        if cid in seen: raise ValueError(f"Duplicate conversation_id: {cid}")
        seen.add(cid)
        if not cid: raise ValueError("conversation_id is required")
        if key in (None,""): out[cid]="unassigned"; continue
        digest=hashlib.sha256(f"{seed}\0{key}".encode()).digest()
        u=int.from_bytes(digest[:8],"big")/2**64
        out[cid]="train" if u<cuts[0] else "validation" if u<cuts[1] else "test"
    return out


def find_split_leakage(records: list[dict[str,Any]], assignments: dict[str,str], group_field: str="verified_scenario_id") -> dict[str,list[str]]:
    """Return verified groups assigned across multiple splits; ignore unassigned rows."""
    splits=defaultdict(set)
    for row in records:
        key=row.get(group_field); cid=str(row.get("conversation_id","")); split=assignments.get(cid,"unassigned")
        if key not in (None,"") and split not in (None,"unassigned"): splits[str(key)].add(str(split))
    return {key:sorted(values) for key,values in splits.items() if len(values)>1}

def exact_and_template_stats(records: list[dict[str,Any]]) -> dict[str,Any]:
    full=defaultdict(list); openings=defaultdict(list)
    for r in records:
        cid=str(r.get("conversation_id")); turns=r.get("turns",[])
        key=" | ".join(norm(t.get("speaker"))+":"+norm(t.get("text")) for t in turns if isinstance(t,dict))
        if key: full[key].append(cid)
        if turns and isinstance(turns[0],dict): openings[norm(turns[0].get("text"))].append(cid)
    f=[v for v in full.values() if len(v)>1]; o=[v for k,v in openings.items() if k and len(v)>1]
    return {"exact_duplicate_full_conversation_groups":len(f),"rows_in_exact_duplicate_groups":sum(map(len,f)),
            "identical_normalized_opening_groups":len(o),"rows_in_repeated_opening_groups":sum(map(len,o))}


def write_csv(path: Path, rows: list[dict[str,Any]]) -> None:
    fields=list(rows[0]) if rows else []
    with path.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)


def main() -> None:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--master",type=Path,required=True);p.add_argument("--similarity",type=Path)
    p.add_argument("--output-dir",type=Path,required=True)
    args=p.parse_args(); records=read_jsonl(args.master); sims=read_similarity(args.similarity)
    edges,groups,coverage=build_proposals(records,sims); args.output_dir.mkdir(parents=True,exist_ok=True)
    write_csv(args.output_dir/"scenario_relationship_review.csv",edges)
    write_csv(args.output_dir/"proposed_scenario_groups.csv",groups)
    write_csv(args.output_dir/"grouping_coverage.csv",coverage)
    conflicts=Counter(c for row in edges for c in row["conflicts"].split(";") if c)
    stats={"records":len(records),"candidate_edges":len(edges),"candidate_covered_records":sum(r["has_candidate_edge"]=="yes" for r in coverage),
        "unlinked_records":sum(r["has_candidate_edge"]=="no" for r in coverage),"confirmed_groups":0,
        "proposed_unconfirmed_group_count":len({r["proposed_group_id"] for r in groups}),"members_in_proposed_groups":len(groups),
        "review_priority_counts":dict(Counter(r["review_priority"] for r in edges)),"conflict_counts":dict(conflicts),
        "existing_tfidf_candidate_rows":sum("tfidf_candidate" in r["evidence"].split(";") for r in edges),
        "duplicates_and_templates":exact_and_template_stats(records),
        "integrity":"Group proposals remain unconfirmed; no official split manifest generated. TF-IDF-only edges never create proposed groups; card_id and labels are not read."}
    (args.output_dir/"grouping_summary.json").write_text(json.dumps(stats,indent=2)+"\n",encoding="utf-8")
    report=f"""# Scenario grouping and leakage review\n\nAudited {len(records)} conversations. The outputs are review proposals only; no scenario membership was confirmed and no official split was written.\n\n- Pairwise candidate relationships: {len(edges)} ({stats['candidate_covered_records']} conversations covered; {stats['unlinked_records']} unlinked).\n- TF-IDF candidate links: {stats['existing_tfidf_candidate_rows']}; lexical similarity is not sufficient to merge scenarios.\n- Contradictory relationship edges: {sum(conflicts.values())}; contradiction types: {dict(conflicts)}.\n- Unconfirmed metadata-supported proposed groups: {stats['proposed_unconfirmed_group_count']} across {stats['members_in_proposed_groups']} records.\n- Exact duplicate full-conversation groups: {stats['duplicates_and_templates']['exact_duplicate_full_conversation_groups']}; repeated normalized opening groups: {stats['duplicates_and_templates']['identical_normalized_opening_groups']}.\n\n`scenario_relationship_review.csv` holds pairwise evidence and decisions pending human review. `proposed_scenario_groups.csv` contains deterministic proposal IDs based only on corroborated, nonconflicting metadata; those IDs are unconfirmed and must not be used for a release split without review. `grouping_coverage.csv` lists every record. All split helpers require an explicit human-verified scenario key; records missing that key are returned as `unassigned`.\n\nRisks: existing group/pair/situation metadata conflict and are incomplete; the similarity candidate method is lexical; identical openings indicate template reuse but may be intentional respectful/manipulative variants. Keep variants together only after scenario identity is reviewed. Use the group-aware helper on verified keys for experiments, but do not freeze official train/validation/test assignments yet.\n\nReproduce: `python data/conversations/scenario_grouping.py --master <cleaned.jsonl> --similarity <scenario_similarity_candidates.csv> --output-dir <derived-dir>`\n"""
    (args.output_dir/"GROUPING_REPORT.md").write_text(report,encoding="utf-8")
    print(json.dumps(stats,indent=2))

if __name__=="__main__": main()
