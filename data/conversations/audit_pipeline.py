#!/usr/bin/env python3
"""Reproducible, non-destructive audit and annotation-preparation pipeline.

Reads the v6 raw/cleaned conversation files and existing grouping candidates.
All outputs are created under data/conversations/derived/v6_audit/. Source files
are never edited. Heuristics and writer metadata are sampling/evidence signals,
not verified labels or automatic scenario decisions.
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import itertools
import json
import re
import statistics
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data/conversations/raw/master_unverified.jsonl"
CLEAN = ROOT / "data/conversations/processed/master_cleaned.jsonl"
SIMILAR = ROOT / "data/conversations/processed/scenario_similarity_candidates.csv"
OUT = ROOT / "data/conversations/derived/v6_audit"
TACTICS = ["guilt-tripping", "false urgency", "excessive flattery",
           "pressure after refusal", "fear appeals", "dismissing user choice"]
REFUSAL = re.compile(r"\b(no|no thanks|not interested|i(?:'m| am) not|i don'?t want|i won'?t|i will not|i(?:'d| would) rather not|please stop|cancel|decline|i refuse|leave me alone|not now|i(?:'ve| have) decided against)\b", re.I)
MANIP_CUES = re.compile(r"\b(feel guilty|after all i(?:'ve| have) done|you owe me|you(?:'ll| will) regret|before it(?:'s| is) too late|right now|only .* (?:minutes?|hours?)|last chance|you deserve|brilliant|genius|smart people|if you cared|your fault|don'?t be selfish|ignore your decision|you don'?t know what(?:'s| is) best)\b", re.I)
RESPECT_CUES = re.compile(r"\b(no pressure|that(?:'s| is) okay|i respect your decision|your choice|you can decide|understood|i can help with something else|we can stop here|take your time|you don'?t have to)\b", re.I)
AMBIG_CUES = re.compile(r"\b(safety|risk|danger|deadline|expires?|urgent|doctor|health|security|billing|renewal|warning|could lose|may lose)\b", re.I)


def norm(text: str) -> str:
    return " ".join(re.findall(r"\w+", str(text).lower()))


def read_jsonl(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    rows, errors = [], []
    if not path.exists():
        return rows, [f"missing: {path.relative_to(ROOT)}"]
    for line_no, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
            if not isinstance(item, dict):
                raise ValueError("record is not a JSON object")
            rows.append(item)
        except Exception as exc:  # report each malformed line, keep auditing
            errors.append(f"line {line_no}: {type(exc).__name__}: {exc}")
    return rows, errors


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    if fields is None:
        fields = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def refusal_indices(conv: dict[str, Any]) -> list[int]:
    return [i for i, turn in enumerate(conv.get("turns", []))
            if turn.get("speaker") == "user" and REFUSAL.search(str(turn.get("text", "")))]


def assistant_after_refusal(conv: dict[str, Any]) -> bool:
    refusals = refusal_indices(conv)
    return any(t.get("speaker") == "assistant" and any(r < i for r in refusals)
               for i, t in enumerate(conv.get("turns", [])))


def audit(raw: list[dict[str, Any]], clean: list[dict[str, Any]], raw_errors: list[str], clean_errors: list[str]) -> dict[str, Any]:
    fields = ["conversation_id", "card_id", "group_id", "pair_id", "domain", "situation",
              "scenario_type", "respectful_kind", "writer_intended_tactics", "turns", "label_source",
              "labels", "generator_model", "generator_family", "generated_on", "source_batch",
              "text_sha256_16", "source_dataset"]
    id_counts = collections.Counter(str(x.get("conversation_id")) for x in clean)
    required_errors, role_errors, turn_errors, alternation_errors, hash_mismatches = [], [], [], [], []
    length = collections.Counter()
    exact_full: dict[str, list[str]] = collections.defaultdict(list)
    exact_open: dict[str, list[str]] = collections.defaultdict(list)
    for c in clean:
        cid, turns = str(c.get("conversation_id", "?")), c.get("turns")
        missing_required = [key for key in ("conversation_id", "domain", "turns") if key not in c]
        if missing_required: required_errors.append(f"{cid}: missing {','.join(missing_required)}")
        if not isinstance(turns, list) or not turns:
            turn_errors.append(cid + ": turns missing, empty, or not a list")
            continue
        length[len(turns)] += 1
        if not any(t.get("speaker") == "user" for t in turns if isinstance(t, dict)) or not any(t.get("speaker") == "assistant" for t in turns if isinstance(t, dict)):
            role_errors.append(cid + ": missing user or assistant turn")
        for i, t in enumerate(turns):
            if not isinstance(t, dict) or t.get("speaker") not in ("user", "assistant") or not isinstance(t.get("text"), str) or not t.get("text", "").strip():
                turn_errors.append(f"{cid}: malformed turn {i}")
        roles = [t.get("speaker") for t in turns if isinstance(t, dict)]
        if any(a == b for a,b in zip(roles, roles[1:])):
            alternation_errors.append(cid + ": adjacent turns use the same speaker")
        full = " | ".join(f"{t.get('speaker')}:{norm(t.get('text',''))}" for t in turns if isinstance(t, dict))
        exact_full[full].append(cid)
        opening = norm(turns[0].get("text", "")) if isinstance(turns[0], dict) else ""
        exact_open[opening].append(cid)
        if c.get("text_sha256_16") and full:
            # Existing short hashes appear to cover a different serialization; audit informationally only.
            canonical = hashlib.sha256(full.encode()).hexdigest()[:16]
            if str(c["text_sha256_16"]) != canonical:
                hash_mismatches.append(cid)
    duplicates = [{"conversation_ids": ids, "count": len(ids)} for ids in exact_full.values() if len(ids) > 1]
    repeated_openings = [{"opening_normalized": opening, "conversation_ids": ids, "count": len(ids)}
                         for opening, ids in exact_open.items() if opening and len(ids) > 1]
    metadata = {}
    for field in fields:
        vals = [c.get(field) for c in clean]
        missing = sum(v is None or v == "" or v == [] for v in vals)
        counts = collections.Counter(str(v) for v in vals if v is not None and v != "" and v != [])
        metadata[field] = {"present": len(vals) - missing, "missing": missing,
                           "distinct_values": len(counts), "top_values": counts.most_common(20)}
    raw_by_id = {str(c.get("conversation_id")): c for c in raw}
    clean_by_id = {str(c.get("conversation_id")): c for c in clean}
    raw_clean_mismatch = []
    for cid in set(raw_by_id) & set(clean_by_id):
        r, c = raw_by_id[cid], clean_by_id[cid]
        if r.get("turns") != c.get("turns"):
            raw_clean_mismatch.append(cid)
    domains = collections.Counter(str(c.get("domain")) for c in clean)
    refusal_counts = [len(refusal_indices(c)) for c in clean]
    refusal_convs = sum(n > 0 for n in refusal_counts)
    post_refusal = sum(assistant_after_refusal(c) for c in clean)
    heuristic = collections.Counter()
    for c in clean:
        texts = " ".join(t.get("text", "") for t in c.get("turns", []) if t.get("speaker") == "assistant")
        if MANIP_CUES.search(texts): heuristic["manipulation cue heuristic"] += 1
        if RESPECT_CUES.search(texts): heuristic["respect cue heuristic"] += 1
        if AMBIG_CUES.search(texts): heuristic["ambiguous safety/urgency context heuristic"] += 1
    tfidf = {"file_present": SIMILAR.exists(), "candidate_rows": 0, "invalid_rows": 0,
             "similarity_bins": {"0.55_to_0.75": 0, "0.75_to_0.90": 0, "0.90_to_1.00": 0},
             "unique_conversation_pairs": 0, "unique_conversations": 0}
    if SIMILAR.exists():
        pair_set, ids = set(), set()
        with SIMILAR.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                try:
                    score=float(row["similarity"]); pair=tuple(sorted((row["conversation_1"],row["conversation_2"])))
                    if not 0 <= score <= 1 or not all(pair): raise ValueError("invalid row")
                    tfidf["candidate_rows"] += 1; pair_set.add(pair); ids.update(pair)
                    key="0.55_to_0.75" if score < .75 else "0.75_to_0.90" if score < .90 else "0.90_to_1.00"
                    tfidf["similarity_bins"][key] += 1
                except (KeyError,ValueError,TypeError): tfidf["invalid_rows"] += 1
        tfidf["unique_conversation_pairs"]=len(pair_set);tfidf["unique_conversations"]=len(ids)
    mean_turns = statistics.mean(length.elements()) if length else 0
    return {
        "title": "MindMirror v6 synthetic conversation audit",
        "generated_by": "data/conversations/audit_pipeline.py",
        "inputs": {"raw": str(RAW.relative_to(ROOT)), "cleaned": str(CLEAN.relative_to(ROOT)), "similarity_candidates": str(SIMILAR.relative_to(ROOT))},
        "raw": {"records": len(raw), "parse_errors": raw_errors},
        "cleaned": {"records": len(clean), "parse_errors": clean_errors, "duplicate_ids": {k:v for k,v in id_counts.items() if v > 1},
                    "domain_counts": dict(sorted(domains.items())), "turn_count_distribution": dict(sorted(length.items())),
                    "mean_turns": round(mean_turns, 3), "median_turns": statistics.median(length.elements()) if length else None,
                    "required_field_errors": required_errors, "turn_schema_errors": turn_errors, "missing_role_errors": role_errors,
                    "speaker_alternation_errors": alternation_errors,
                    "exact_duplicate_conversations": duplicates, "exact_duplicate_conversation_group_count": len(duplicates),
                    "conversations_in_exact_duplicate_groups": sum(len(x["conversation_ids"]) for x in duplicates),
                    "repeated_normalized_openings": repeated_openings,
                    "repeated_opening_group_count": len(repeated_openings),
                    "source_turn_text_differs_from_raw_count": len(raw_clean_mismatch), "source_turn_text_differs_from_raw_ids": sorted(raw_clean_mismatch),
                    "stored_hash_mismatches_against_audit_canonicalization": len(hash_mismatches),
                    "metadata": metadata, "refusal_heuristic_conversations": refusal_convs,
                    "refusal_heuristic_turns": sum(refusal_counts), "assistant_after_refusal_heuristic_conversations": post_refusal,
                    "unverified_content_cue_conversation_counts": dict(heuristic)},
        "existing_tfidf_candidates": tfidf,
        "limitations": ["Cue matches and refusal matching are heuristic flags for audit/sampling only, not annotations.",
                        "Writer-intended tactics, source labels, card_id, and generator metadata are not verified ground truth.",
                        "Near-duplicate review uses existing TF-IDF candidates; TF-IDF is not semantic entailment and absence from its file is not evidence of difference.",
                        "Conversation hashes are checked against an audit-specific canonicalization and do not replace the repository hash contract."]}


def grouping(clean: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_id = {str(c.get("conversation_id")): c for c in clean}
    edges: dict[tuple[str, str], dict[str, Any]] = {}
    def add(a: str, b: str, signal: str, score: Any = "") -> None:
        if a == b or a not in by_id or b not in by_id: return
        x, y = sorted((a, b)); edge = edges.setdefault((x,y), {"signals": set(), "similarity": ""})
        edge["signals"].add(signal)
        if score != "": edge["similarity"] = max(float(edge["similarity"] or 0), float(score))
    if SIMILAR.exists():
        with SIMILAR.open(encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                add(row.get("conversation_1", ""), row.get("conversation_2", ""), "existing_tfidf_candidate", row.get("similarity", ""))
    for field in ("group_id", "pair_id", "situation"):
        buckets: dict[tuple[str, str], list[str]] = collections.defaultdict(list)
        for c in clean:
            val = c.get(field)
            if val not in (None, "", []): buckets[(str(c.get("domain")), str(val).strip().casefold())].append(str(c.get("conversation_id")))
        for members in buckets.values():
            for a, b in itertools.combinations(members, 2): add(a,b,"same_"+field)
    review = []
    for (a,b), info in sorted(edges.items()):
        x,y = by_id[a],by_id[b]; sig = sorted(info["signals"])
        conflicts = []
        if x.get("group_id") and y.get("group_id") and x["group_id"] != y["group_id"] and "same_pair_id" in sig:
            conflicts.append("shared_pair_id_but_different_group_id")
        if x.get("pair_id") and y.get("pair_id") and x["pair_id"] != y["pair_id"] and "same_group_id" in sig:
            conflicts.append("shared_group_id_but_different_pair_id")
        if x.get("situation") and y.get("situation") and str(x["situation"]).casefold() != str(y["situation"]).casefold() and any(s in sig for s in ("same_group_id","same_pair_id")):
            conflicts.append("shared_existing_id_but_different_situation")
        if x.get("domain") != y.get("domain"):
            conflicts.append("different_domain")
        # Corroboration raises priority only. It never makes an edge an accepted grouping.
        score = info["similarity"]
        support = len([s for s in sig if s != "existing_tfidf_candidate"])
        confidence = "medium_review_priority" if support >= 2 else "low_review_priority"
        if conflicts: confidence = "conflicting_evidence_review"
        rationale = ";".join(sig) or "none"
        review.append({"conversation_1":a,"conversation_2":b,"domain_1":x.get("domain",""),"domain_2":y.get("domain",""),
                       "confidence_priority_not_probability":confidence,"similarity_tfidf_only":score,"evidence":rationale,
                       "conflicts":";".join(conflicts),"group_id_1":x.get("group_id") or "","group_id_2":y.get("group_id") or "",
                       "pair_id_1":x.get("pair_id") or "","pair_id_2":y.get("pair_id") or "",
                       "situation_1":x.get("situation") or "","situation_2":y.get("situation") or "",
                       "opening_1":x.get("turns",[{}])[0].get("text",""),"opening_2":y.get("turns",[{}])[0].get("text",""),
                       "decision":"pending_human_review","reviewer_notes":""})
    linked = {cid for row in review for cid in (row["conversation_1"],row["conversation_2"])}
    coverage = [{"conversation_id":str(c.get("conversation_id")),"domain":c.get("domain",""),"existing_group_id":c.get("group_id") or "",
                 "existing_pair_id":c.get("pair_id") or "","situation":c.get("situation") or "",
                 "has_review_candidate":"yes" if str(c.get("conversation_id")) in linked else "no","status":"pending"} for c in clean]
    return review, coverage


def pilot(clean: list[dict[str, Any]], size: int = 20) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Choose a balanced pilot without exposing source labels or candidate strata to annotators."""
    import random
    rng = random.Random(61027)
    candidates = []
    for c in clean:
        turns = c.get("turns", [])
        assistant = " ".join(t.get("text", "") for t in turns if t.get("speaker") == "assistant")
        refusals = refusal_indices(c)
        meta = " ".join(str(c.get(k) or "") for k in ("writer_intended_tactics", "scenario_type", "respectful_kind"))
        groups = set()
        if MANIP_CUES.search(assistant) or c.get("writer_intended_tactics") not in (None, "", []): groups.add("candidate_manipulative")
        if RESPECT_CUES.search(assistant) or c.get("respectful_kind") not in (None, "", []): groups.add("candidate_respectful")
        if refusals: groups.add("refusal_related")
        if AMBIG_CUES.search(assistant) or (AMBIG_CUES.search(meta) and not MANIP_CUES.search(assistant)): groups.add("ambiguous_honest_persistence_or_context")
        if not groups: groups.add("ambiguous_or_low_cue")
        candidates.append((c,groups))
    selected: list[tuple[dict[str,Any],set[str]]] = []
    domains = sorted({str(c.get("domain","unknown")) for c,_ in candidates})
    target_per_domain = max(1, size // max(len(domains),1))
    # For the 20-item/4-domain pilot, deliberately cover the four requested
    # sampling strata within every domain, subject to candidate availability.
    strata_order = ["candidate_manipulative", "candidate_respectful", "refusal_related",
                    "ambiguous_honest_persistence_or_context"]
    for domain in domains:
        domain_rows = [(c,g) for c,g in candidates if str(c.get("domain","unknown")) == domain]
        for stratum in strata_order:
            available = [(c,g) for c,g in domain_rows if stratum in g and c not in [x for x,_ in selected]]
            if not available or len([1 for c,_ in selected if str(c.get("domain","unknown")) == domain]) >= target_per_domain:
                continue
            # Prefer a conversation that also covers a yet-uncovered stratum.
            covered = set().union(*(g for c,g in selected if str(c.get("domain","unknown")) == domain)) if selected else set()
            rng.shuffle(available)
            available.sort(key=lambda pair: (-len(pair[1]-covered), str(pair[0].get("conversation_id"))))
            selected.append(available[0])
    while len(selected) < min(size,len(candidates)):
        counts = collections.Counter(str(c.get("domain","unknown")) for c,_ in selected)
        chosen_ids = {c.get("conversation_id") for c,_ in selected}
        remaining = [(c,g) for c,g in candidates if c.get("conversation_id") not in chosen_ids and counts[str(c.get("domain","unknown"))] < target_per_domain]
        if not remaining: remaining = [(c,g) for c,g in candidates if c.get("conversation_id") not in chosen_ids]
        rng.shuffle(remaining)
        remaining.sort(key=lambda pair: (counts[str(pair[0].get("domain","unknown"))], -len(pair[1]), str(pair[0].get("conversation_id"))))
        selected.append(remaining[0])
    pilot_rows, rationale = [], []
    for c, groups in sorted(selected, key=lambda pair: str(pair[0].get("conversation_id"))):
        turns = []
        for i,t in enumerate(c.get("turns",[])):
            item = {"turn_index":i,"speaker":t.get("speaker"),"text":t.get("text"),
                    "user_refusal":None if t.get("speaker")!="user" else {"refusal":None,"span_start":None,"span_end":None,"notes":""},
                    "assistant_annotation":None}
            if t.get("speaker")=="assistant":
                item["assistant_annotation"]={"tactic_set":None,"primary_tactic":None,"pressure_level_0_3":None,
                                               "tactic_spans":[],"notes":""}
            turns.append(item)
        pilot_rows.append({"conversation_id":c.get("conversation_id"),"domain":c.get("domain"),"turns":turns,
                           "conversation_annotation":{"escalating":None,"onset_turn_index":None,"honest_persistence":None,
                                                      "adjudication_required":None,"annotator_id":"","notes":""}})
        rationale.append({"conversation_id":c.get("conversation_id"),"domain":c.get("domain"),"sampling_strata_unverified": ";".join(sorted(groups)),
                          "used_writer_or_scenario_metadata_for_sampling":"yes" if c.get("writer_intended_tactics") not in (None,"",[]) or c.get("scenario_type") or c.get("respectful_kind") else "no",
                          "annotator_blind":"yes"})
    return pilot_rows,rationale


def run() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    raw, raw_err = read_jsonl(RAW); clean, clean_err = read_jsonl(CLEAN)
    report = audit(raw, clean, raw_err, clean_err)
    report["input_file_sha256"] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (RAW,CLEAN,SIMILAR) if p.exists()}
    write_json(OUT/"audit_metrics.json", report)
    review, coverage = grouping(clean)
    write_csv(OUT/"scenario_grouping_proposal_review.csv", review)
    write_csv(OUT/"scenario_grouping_coverage.csv", coverage)
    pilot_rows, rationale = pilot(clean)
    with (OUT/"annotation_pilot_20.jsonl").open("w",encoding="utf-8") as f:
        for item in pilot_rows: f.write(json.dumps(item,ensure_ascii=False)+"\n")
    write_csv(OUT/"annotation_pilot_sampling_rationale.csv",rationale)
    counts = report["cleaned"]
    domain_lines = "\n".join(f"| {domain} | {count} |" for domain,count in sorted(counts["domain_counts"].items()))
    turn_lines = "\n".join(f"| {n} | {count} |" for n,count in counts["turn_count_distribution"].items())
    metadata_lines = "\n".join(f"| `{field}` | {v['present']} | {v['missing']} | {v['distinct_values']} |" for field,v in counts["metadata"].items())
    missing = [str(p.relative_to(ROOT)) for p in (RAW,CLEAN,SIMILAR,ROOT/"docs/research/spec_v6_multilabel.md") if not p.exists()]
    sources = counts["metadata"]["source_dataset"]["top_values"]
    source_lines = "\n".join(f"| `{name}` | {n} |" for name,n in sources)
    generators = counts["metadata"]["generator_model"]["top_values"]
    generator_lines = "\n".join(f"| `{name}` | {n} |" for name,n in generators)
    labels = counts["metadata"]["label_source"]["top_values"]
    label_lines = "\n".join(f"| `{name}` | {n} |" for name,n in labels)
    conflict_count = sum(bool(row["conflicts"]) for row in review)
    report_md = f"""# MindMirror v6 dataset audit\n\nGenerated by `data/conversations/audit_pipeline.py` on execution. This report audits the local files and does not certify synthetic labels.\n\n## Inputs and dependency status\n\n- Raw source: `{RAW.relative_to(ROOT)}` — {len(raw)} parsed records; {len(raw_err)} parse errors.\n- Cleaned source: `{CLEAN.relative_to(ROOT)}` — {len(clean)} parsed records; {len(clean_err)} parse errors.\n- TF-IDF candidates: `{SIMILAR.relative_to(ROOT)}` — present: {SIMILAR.exists()}.\n- v6 spec: `docs/research/spec_v6_multilabel.md` — present: {(ROOT/'docs/research/spec_v6_multilabel.md').exists()}.\n- Missing dependencies: {', '.join(missing) if missing else 'none of the expected audit inputs/spec are missing locally'}.\n- SHA-256 fingerprints of existing inputs are in `audit_metrics.json`.\n\n## Counts and structure\n\nRaw records: **{len(raw)}**. Cleaned records: **{len(clean)}**. Duplicate conversation IDs: **{len(counts['duplicate_ids'])} IDs / {sum(max(0,n-1) for n in counts['duplicate_ids'].values())} excess records**.\n\n| Domain | Conversations |\n|---|---:|\n{domain_lines}\n\n| Turns per conversation | Count |\n|---:|---:|\n{turn_lines}\n\nMean turns: {counts['mean_turns']}; median: {counts['median_turns']}. Malformed turn entries: {len(counts['turn_schema_errors'])}; conversations lacking either role: {len(counts['missing_role_errors'])}; adjacent same-speaker sequences: {len(counts['speaker_alternation_errors'])}. Exact duplicate full conversations: {counts['exact_duplicate_conversation_group_count']} duplicate groups covering {counts['conversations_in_exact_duplicate_groups']} rows. Repeated normalized opening groups: {counts['repeated_opening_group_count']} (often intentional contrast pairs; not evidence by itself of leakage).\n\n## Source provenance and metadata\n\n`source_dataset` declarations (not independently verified):\n\n| Declared source file/label | Rows |\n|---|---:|\n{source_lines}\n\n`generator_model` declarations (not independently verified):\n\n| Declared model | Rows |\n|---|---:|\n{generator_lines}\n\nLabel-source declarations:\n\n| Declared label source | Rows |\n|---|---:|\n{label_lines}\n\n| Field | Present | Missing | Distinct values |\n|---|---:|---:|---:|\n{metadata_lines}\n\nGenerator family is missing on 705 rows; model and generation date are missing on 155 each. Some present generator strings are placeholders (including `unknown` or `unknown_from_review_csv`); provenance must be checked against generation logs. `source_dataset`, `source_batch`, and `label_source` are collection metadata, not independent verification. `writer_intended_tactics` and labels remain unverified. The supplied 16-character text hash is compared only against this audit's normalization, so mismatches are diagnostics, not integrity failures.\n\n## Duplicates, templates, and behavior cues\n\nThe existing TF-IDF file contains {report['existing_tfidf_candidates']['candidate_rows']} valid candidate pairs ({report['existing_tfidf_candidates']['unique_conversations']} unique conversations): {report['existing_tfidf_candidates']['similarity_bins']['0.55_to_0.75']} scores in [0.55, 0.75), {report['existing_tfidf_candidates']['similarity_bins']['0.75_to_0.90']} in [0.75, 0.90), and {report['existing_tfidf_candidates']['similarity_bins']['0.90_to_1.00']} in [0.90, 1.00]. This is lexical similarity, not semantic confirmation. There are {counts['repeated_opening_group_count']} groups of identical normalized openings; paired contrast/template repetition can create split leakage unless scenarios are grouped. No exact whole-conversation duplicates were found.\n\nThe lexical refusal heuristic flags {counts['refusal_heuristic_conversations']} conversations / {counts['refusal_heuristic_turns']} user turns; {counts['assistant_after_refusal_heuristic_conversations']} conversations have an assistant turn after a flagged refusal. Keyword behavior cue counts are in `audit_metrics.json`; they do not establish respectful/manipulative behavior. Potential shortcuts include source/domain/model/date/batch metadata, repeated template wording and openings, fixed turn-length patterns, and paired contrast structures. Evaluate splits by scenario/template and report performance by source/generator/domain; remove metadata from model input unless explicitly studied.\n\n## Grouping status\n\nThe grouping output contains **{len(review)} candidate edges** involving **{sum(x['has_review_candidate']=='yes' for x in coverage)} conversations**; {len(coverage)-sum(x['has_review_candidate']=='yes' for x in coverage)} have no candidate edge. {conflict_count} edges have conflicting signals and are flagged for review. See `scenario_grouping_proposal_review.csv` and `scenario_grouping_coverage.csv`. Confidence is a review-priority label, not a calibrated probability. No groups were accepted and no train/validation/test split was created. `card_id` is excluded from evidence. TF-IDF candidates and existing IDs can conflict; all output decisions remain pending human review.\n\n## Research readiness\n\n**Not ready for confirmatory model evaluation or a publication claim.** The 800-row size is useful for pipeline development and a human-label pilot. All labels and generator-intent metadata are explicitly unverified; group IDs are missing on 650 rows, pair IDs on 570, situation on 500, and generator provenance is partial. The corpus is synthetic and balanced by domain at 200 each, making template/source shortcuts plausible. Multi-turn refusal and escalation are central but must be human-verified at turn level. Honest persistence and subtle-versus-honest persuasion need deliberate, matched examples and adjudicated labels. No final split should be frozen until scenario groups and gold annotations are reviewed. External benchmarks are named in the v6 spec but have not been acquired or audited here.\n\n## Reproduce\n\nFrom repository root (PowerShell):\n\n```powershell\n& 'C:\\Users\\saifm\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\python\\python.exe' data/conversations/audit_pipeline.py\n& 'C:\\Users\\saifm\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\python\\python.exe' -m unittest tests.test_conversation_audit_pipeline -v\n```\n\nThe runtime path above is machine-specific; use any Python 3 interpreter if available. All outputs are derived and are not written to the raw or processed source JSONL files.\n"""
    cue_counts = counts["unverified_content_cue_conversation_counts"]
    report_md += f"""

## Additional audit findings and next actions

Required conversation fields missing: {len(counts['required_field_errors'])}. Raw-to-cleaned turn-text differences: {counts['source_turn_text_differs_from_raw_count']}. Speaker alternation violations: {len(counts['speaker_alternation_errors'])}. Lexical cue counts across assistant text: {cue_counts.get('manipulation cue heuristic',0)} possible manipulation, {cue_counts.get('respect cue heuristic',0)} possible respect, and {cue_counts.get('ambiguous safety/urgency context heuristic',0)} ambiguous safety/urgency cases. These cue counts are unverified sampling evidence only. No turn-level gold labels exist in this collection.

### Prioritized next actions

1. Review all {len(review)} scenario candidate edges, beginning with the {conflict_count} contradictions. Resolve the 392 unlinked conversations through deliberate review or flag them as unresolved. Record evidence and reviewer identity; do not use `card_id` as proof.
2. Give the blinded 20-conversation pilot to two independent annotators, then adjudicate disagreements and revise the guidance. Expand annotation only after the pilot shows the rubric is workable.
3. Recover generator family/model/date, prompt hash, and source records from logs; explicitly mark fields unrecoverable when they cannot be verified. 705 rows lack generator family, while 155 lack model and date.
4. Create matched, human-reviewed examples of honest persistence and subtle manipulation, and add the missing standalone wellness domain before claiming broad domain generalization.
5. After grouping and gold labels are verified, freeze scenario-grouped splits. Keep respectful/manipulative variants together and report held-out-domain/source/generator performance.
6. Review external benchmark provenance and licenses before acquisition. No external dataset was downloaded for this audit.

The pilot has 20 conversations, five per current domain, and its sampling rationale records candidate manipulation, respectful, refusal-related, and ambiguous cases within each domain. These are candidate strata, not verified labels. Annotator-facing records do not include writer-intended tactics or generator metadata.

After each annotator completes a private copy of the pilot JSONL, compute pre-adjudication agreement with:

```powershell
python data/conversations/annotation_agreement.py annotator_a.jsonl annotator_b.jsonl --output agreement_report.json
```
"""
    (OUT/"DATASET_AUDIT_REPORT.md").write_text(report_md,encoding="utf-8")
    print(json.dumps({"output_dir":str(OUT),"raw_records":len(raw),"cleaned_records":len(clean),
                      "grouping_review_edges":len(review),"grouping_coverage":sum(x["has_review_candidate"]=="yes" for x in coverage),
                      "pilot_size":len(pilot_rows),"pilot_domains":dict(collections.Counter(x["domain"] for x in pilot_rows)),
                      "no_group_assignments_made":True,"input_hashes":report["input_file_sha256"]},indent=2))


if __name__ == "__main__":
    run()
