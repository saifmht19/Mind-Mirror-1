#!/usr/bin/env python3
"""Compare two independent v6.2 annotation outputs for one blinded batch.

The script never edits annotator outputs. It checks ID/order/turn preservation,
optionally runs Track A's validator, writes aggregate AI-AI agreement metrics,
and creates a human-review queue without including conversation text.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

FIELDS = (
    "refusal", "refusal_span", "tactic_set", "primary_tactic", "pressure_level",
    "tactic_spans", "out_of_taxonomy_suspected", "review_required",
)
TACTICS = {
    "guilt-tripping", "false urgency", "excessive flattery",
    "pressure-after-refusal", "fear-appeal", "dismissing-choice",
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f"{path}:{line_no}: each JSONL row must be an object")
        records.append(row)
    return records


def canonical_source_hash(turns: list[dict[str, Any]]) -> str:
    """SHA-256 of UTF-8 JSON for ordered turns, compact and non-ASCII-preserving."""
    payload = json.dumps(turns, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def jsonl_bytes(records: list[dict[str, Any]]) -> bytes:
    return ("".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in records)).encode("utf-8")


def _canonical(value: Any) -> str:
    if isinstance(value, list) and value and all(isinstance(v, str) for v in value):
        return json.dumps(sorted(value), ensure_ascii=False, separators=(",", ":"))
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _validate_v62_shape(record: dict[str, Any]) -> list[str]:
    errors = []
    if record.get("schema_version") != "2.0.0" or record.get("guideline_version") != "v6.2.0":
        errors.append("schema/guideline version must be 2.0.0/v6.2.0")
    turns, anns = record.get("turns"), record.get("turn_annotations")
    if not isinstance(turns, list) or not isinstance(anns, list) or len(turns) != len(anns):
        return errors + ["turns and turn_annotations must be aligned arrays"]
    if record.get("source_text_sha256") != canonical_source_hash(turns):
        errors.append("source_text_sha256 does not match canonical ordered turns")
    for i, (turn, ann) in enumerate(zip(turns, anns)):
        if not isinstance(turn, dict) or not isinstance(ann, dict):
            errors.append(f"turn {i} and annotation must be objects")
            continue
        if turn.get("turn_index") != i or ann.get("turn_index") != i:
            errors.append(f"turn {i} index mismatch")
        if turn.get("speaker") != ann.get("speaker"):
            errors.append(f"turn {i} speaker mismatch")
        if turn.get("speaker") == "assistant":
            labels = ann.get("tactic_set")
            if not isinstance(labels, list) or len(labels) != len(set(labels)) or not set(labels) <= TACTICS:
                errors.append(f"assistant turn {i} has invalid v6.2 tactic_set")
            if not labels and ann.get("primary_tactic") != "neutral":
                errors.append(f"assistant turn {i}: empty tactic_set requires neutral primary")
            if labels and ann.get("primary_tactic") not in labels:
                errors.append(f"assistant turn {i}: primary tactic must be in tactic_set")
            if ann.get("pressure_level") not in (0, 1, 2, 3):
                errors.append(f"assistant turn {i}: pressure_level must be 0..3")
            if not isinstance(ann.get("out_of_taxonomy_suspected"), bool) or not isinstance(ann.get("review_required"), bool):
                errors.append(f"assistant turn {i}: review flags must be booleans")
            if ann.get("out_of_taxonomy_suspected") and not ann.get("review_required"):
                errors.append(f"assistant turn {i}: suspected out-of-taxonomy case must remain in review")
        elif turn.get("speaker") == "user":
            if not isinstance(ann.get("refusal"), bool):
                errors.append(f"user turn {i}: refusal must be boolean")
        else:
            errors.append(f"turn {i}: speaker must be user or assistant")
    return errors


def validate_output(record: dict[str, Any], validator: Path | None) -> list[str]:
    errors = _validate_v62_shape(record)
    if validator is not None:
        with tempfile.TemporaryDirectory(prefix="mindmirror-v62-check-", dir=Path(__file__).parents[1]) as temp:
            temp_path = Path(temp) / "one_record.jsonl"
            temp_path.write_text(json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8")
            proc = subprocess.run([sys.executable, str(validator), str(temp_path)],
                                  text=True, capture_output=True, check=False)
            if proc.returncode != 0:
                errors.append("Track A validator rejected record: " + proc.stdout.strip()[-1000:])
    return errors


def compare(batch_path: Path, a_path: Path, b_path: Path, out_dir: Path,
            validator: Path | None = None) -> dict[str, Any]:
    batch, a_records, b_records = load_jsonl(batch_path), load_jsonl(a_path), load_jsonl(b_path)
    ids = [r.get("conversation_id") for r in batch]
    if len(ids) != len(set(ids)) or any(not isinstance(i, str) or not i for i in ids):
        raise ValueError("input batch must have unique non-empty conversation_id values")
    if [r.get("conversation_id") for r in a_records] != ids:
        raise ValueError("annotator A IDs/order must exactly match the input batch")
    if [r.get("conversation_id") for r in b_records] != ids:
        raise ValueError("annotator B IDs/order must exactly match the input batch")

    disagreement_rows: list[dict[str, Any]] = []
    n_units = Counter()
    matches = Counter()
    validation = {"annotator_a": [], "annotator_b": []}
    for pos, (source, ra, rb) in enumerate(zip(batch, a_records, b_records)):
        cid = ids[pos]
        source_turns = source.get("turns")
        if not isinstance(source_turns, list):
            raise ValueError(f"input record {cid}: turns must be an array")
        if ra.get("turns") != source_turns or rb.get("turns") != source_turns:
            raise ValueError(f"{cid}: one or both outputs changed source turns")
        source_hash = canonical_source_hash(source_turns)
        record_validation = {}
        for label, record in (("annotator_a", ra), ("annotator_b", rb)):
            if record.get("source_text_sha256") != source_hash:
                raise ValueError(f"{cid}: {label} source_text_sha256 mismatch")
            errs = validate_output(record, validator)
            record_validation[label] = errs
            if errs:
                validation[label].append({"conversation_id": cid, "errors": errs})

        turn_a, turn_b = ra.get("turn_annotations", []), rb.get("turn_annotations", [])
        if len(turn_a) != len(source_turns) or len(turn_b) != len(source_turns):
            raise ValueError(f"{cid}: annotation arrays must align with source turns")
        differences = []
        for i, (turn, aa, ab) in enumerate(zip(source_turns, turn_a, turn_b)):
            speaker = turn.get("speaker")
            for field in FIELDS:
                if speaker == "user" and field not in {"refusal", "refusal_span"}:
                    continue
                if speaker == "assistant" and field in {"refusal", "refusal_span"}:
                    continue
                n_units[field] += 1
                va, vb = aa.get(field), ab.get(field)
                equal = _canonical(va) == _canonical(vb)
                if equal:
                    matches[field] += 1
                else:
                    differences.append({"turn_index": i, "speaker": speaker, "field": field,
                                        "annotator_a": va, "annotator_b": vb})
        ca, cb = ra.get("conversation_annotation", {}), rb.get("conversation_annotation", {})
        for field in ("escalating", "onset_turn_index", "honest_persistence"):
            n_units[field] += 1
            if _canonical(ca.get(field)) == _canonical(cb.get(field)):
                matches[field] += 1
            else:
                differences.append({"field": f"conversation.{field}",
                                    "annotator_a": ca.get(field), "annotator_b": cb.get(field)})
        review = any(
            ann.get("review_required") is True or ann.get("out_of_taxonomy_suspected") is True
            for record in (ra, rb) for ann in record.get("turn_annotations", [])
            if isinstance(ann, dict)
        )
        if differences or review or any(record_validation.values()):
            disagreement_rows.append({
                "conversation_id": cid,
                "queue_reasons": (["annotator_disagreement"] if differences else []) + (["review_flagged"] if review else []) +
                                 (["schema_validation_failure"] if any(x["conversation_id"] == cid for who in validation.values() for x in who) else []),
                "differences": differences,
                "adjudication_status": "pending",
            })
    report = {
        "batch": batch_path.name,
        "records": len(batch),
        "agreement": {field: {"n": n_units[field], "exact_agreement": matches[field] / n_units[field] if n_units[field] else None}
                      for field in sorted(n_units)},
        "interpretation": "AI-AI agreement only; not human inter-annotator agreement or adjudication.",
        "schema_validation_failures": validation,
        "review_queue_count": len(disagreement_rows),
        "conversation_text_included": False,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "comparison.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (out_dir / "disagreement_queue.jsonl").write_bytes(jsonl_bytes(disagreement_rows))
    return report


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--batch", type=Path, required=True)
    p.add_argument("--annotator-a", type=Path, required=True)
    p.add_argument("--annotator-b", type=Path, required=True)
    p.add_argument("--out-dir", type=Path, required=True)
    p.add_argument("--validator", type=Path, help="Track A validator to invoke after adapting its CLI to stdin")
    args = p.parse_args()
    report = compare(args.batch, args.annotator_a, args.annotator_b, args.out_dir, args.validator)
    print(json.dumps(report, indent=2))
    if any(report["schema_validation_failures"].values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()

