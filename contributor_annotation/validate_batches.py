#!/usr/bin/env python3
"""Check deterministic blinded batch files against their manifest and source IDs."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

EXPECTED_FIELDS = {"conversation_id", "domain", "turns"}
FORBIDDEN_KEYS = {
    "card_id", "group_id", "pair_id", "situation", "scenario_type",
    "respectful_kind", "writer_intended_tactics", "target_tactics", "labels",
    "generator_model", "generator_family", "generated_on", "label_source",
}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{line_number}: each line must be an object")
        records.append(value)
    return records


def validate(out_dir: Path) -> dict[str, int]:
    manifest_path = out_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("format_version") != "mindmirror-v6-blinded-input-1.0.0":
        raise ValueError("unknown or missing input format version")
    if manifest.get("total_dataset") != 800 or manifest.get("pilot_excluded") != 20 or manifest.get("to_annotate") != 780:
        raise ValueError("manifest must declare 800 total, 20 excluded, and 780 to annotate")
    batches = manifest.get("batches")
    if not isinstance(batches, list) or not batches:
        raise ValueError("manifest has no batches")
    seen: set[str] = set()
    actual_batch_files = {path.name for path in out_dir.glob("batch_*.jsonl")}
    declared_batch_files = {item.get("filename") for item in batches if isinstance(item, dict)}
    if actual_batch_files != declared_batch_files:
        raise ValueError(f"batch file mismatch: undeclared={sorted(actual_batch_files-declared_batch_files)}, missing={sorted(declared_batch_files-actual_batch_files)}")
    for expected_number, item in enumerate(batches, 1):
        expected_name = f"batch_{expected_number:03d}.jsonl"
        if item.get("filename") != expected_name:
            raise ValueError(f"batch order/name must be deterministic; expected {expected_name}")
        path = out_dir / expected_name
        raw = path.read_bytes()
        if digest(raw) != item.get("sha256"):
            raise ValueError(f"{expected_name}: SHA-256 mismatch")
        records = read_jsonl(path)
        if len(records) != item.get("count") or len(records) != len(item.get("conversation_ids", [])):
            raise ValueError(f"{expected_name}: count/ID manifest mismatch")
        for record, listed_id in zip(records, item["conversation_ids"]):
            if set(record) != EXPECTED_FIELDS:
                raise ValueError(f"{expected_name}: unexpected visible fields {sorted(set(record)-EXPECTED_FIELDS)}")
            if FORBIDDEN_KEYS.intersection(record):
                raise ValueError(f"{expected_name}: contains hidden metadata")
            cid = record.get("conversation_id")
            if not isinstance(cid, str) or cid != listed_id or cid in seen:
                raise ValueError(f"{expected_name}: missing, mismatched, or repeated ID {cid!r}")
            seen.add(cid)
            turns = record.get("turns")
            if not isinstance(turns, list) or not turns:
                raise ValueError(f"{expected_name}/{cid}: empty or malformed turns")
            for index, turn in enumerate(turns):
                if not isinstance(turn, dict) or set(turn) != {"turn_index", "speaker", "text"}:
                    raise ValueError(f"{expected_name}/{cid}/{index}: non-canonical turn fields")
                if turn.get("turn_index") != index or turn.get("speaker") not in {"user", "assistant"}:
                    raise ValueError(f"{expected_name}/{cid}/{index}: invalid index or speaker")
                if not isinstance(turn.get("text"), str) or not turn["text"].strip():
                    raise ValueError(f"{expected_name}/{cid}/{index}: missing text")
    if len(seen) != 780:
        raise ValueError(f"expected 780 unique non-pilot IDs, found {len(seen)}")
    return {"batches": len(batches), "records": len(seen)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("batch_dir", type=Path)
    args = parser.parse_args()
    try:
        result = validate(args.batch_dir)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    print(f"PASS: {result['records']} blinded records across {result['batches']} batches")


if __name__ == "__main__":
    main()
