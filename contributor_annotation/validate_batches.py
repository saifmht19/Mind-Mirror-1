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


def read_source_records(path: Path) -> list[dict[str, Any]]:
    raw = path.read_text(encoding="utf-8-sig")
    if path.suffix.lower() == ".json":
        values = json.loads(raw)
        if not isinstance(values, list):
            raise ValueError(f"{path}: expected a JSON array")
    else:
        values = []
        for line_number, line in enumerate(raw.splitlines(), 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number}: expected object")
            values.append(value)
    if any(not isinstance(value, dict) for value in values):
        raise ValueError(f"{path}: every record must be an object")
    return values


def source_projection(source: dict[str, Any]) -> dict[str, Any]:
    cid = source.get("conversation_id")
    domain = source.get("domain")
    raw_turns = source.get("turns")
    if not isinstance(cid, str) or not cid or not isinstance(domain, str) or not domain:
        raise ValueError("source record needs conversation_id and domain")
    if not isinstance(raw_turns, list) or not raw_turns:
        raise ValueError(f"{cid}: source turns must be non-empty")
    turns = []
    for index, turn in enumerate(raw_turns):
        if not isinstance(turn, dict):
            raise ValueError(f"{cid}/{index}: source turn must be an object")
        speaker = turn.get("speaker", turn.get("role"))
        text = turn.get("text", turn.get("content"))
        if speaker not in {"user", "assistant"} or not isinstance(text, str) or not text.strip():
            raise ValueError(f"{cid}/{index}: invalid source speaker or text")
        if "turn_index" in turn and turn["turn_index"] != index:
            raise ValueError(f"{cid}/{index}: non-canonical source turn index")
        turns.append({"turn_index": index, "speaker": speaker, "text": text})
    return {"conversation_id": cid, "domain": domain, "turns": turns}


def validate(out_dir: Path, dataset_path: Path, pilot_path: Path) -> dict[str, int]:
    manifest_path = out_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("format_version") != "mindmirror-v6-blinded-input-1.0.0":
        raise ValueError("unknown or missing input format version")
    if manifest.get("batch_size") != 40:
        raise ValueError("manifest must use batch size 40")
    if manifest.get("total_dataset") != 800 or manifest.get("pilot_excluded") != 20 or manifest.get("to_annotate") != 780:
        raise ValueError("manifest must declare 800 total, 20 excluded, and 780 to annotate")
    if hashlib.sha256(dataset_path.read_bytes()).hexdigest() != manifest.get("source_dataset_sha256"):
        raise ValueError("source dataset SHA-256 differs from manifest")
    if hashlib.sha256(pilot_path.read_bytes()).hexdigest() != manifest.get("pilot_sha256"):
        raise ValueError("pilot SHA-256 differs from manifest")
    source = read_source_records(dataset_path)
    pilot = read_source_records(pilot_path)
    source_ids = [item.get("conversation_id") for item in source]
    pilot_ids = [item.get("conversation_id") for item in pilot]
    if len(source) != 800 or len(set(source_ids)) != 800:
        raise ValueError("source must contain 800 unique conversation IDs")
    if len(pilot) != 20 or len(set(pilot_ids)) != 20 or not set(pilot_ids) <= set(source_ids):
        raise ValueError("pilot must contain 20 unique IDs, all present in the source")
    pilot_id_set = set(pilot_ids)
    expected = {item["conversation_id"]: source_projection(item)
                for item in source if item["conversation_id"] not in pilot_id_set}
    batches = manifest.get("batches")
    if not isinstance(batches, list) or not batches:
        raise ValueError("manifest has no batches")
    seen: set[str] = set()
    ordered_ids: list[str] = []
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
        expected_count = min(40, 780 - (expected_number - 1) * 40)
        if len(records) != expected_count:
            raise ValueError(f"{expected_name}: expected {expected_count} records for batch size 40")
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
            ordered_ids.append(cid)
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
    if seen != set(expected):
        raise ValueError("batch IDs do not equal the source IDs after exact pilot exclusion")
    if ordered_ids != list(expected):
        raise ValueError("batch order differs from deterministic source order")
    for batch in batches:
        for record in read_jsonl(out_dir / batch["filename"]):
            cid = record["conversation_id"]
            if cid not in expected:
                raise ValueError(f"{cid}: batch contains a pilot or unknown conversation ID")
            if record != expected[cid]:
                raise ValueError(f"{record['conversation_id']}: batch content differs from source projection")
    return {"batches": len(batches), "records": len(seen)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("batch_dir", type=Path)
    parser.add_argument("--dataset", required=True, type=Path, help="original cleaned 800-record JSONL")
    parser.add_argument("--pilot", required=True, type=Path, help="exact frozen 20-record pilot")
    args = parser.parse_args()
    try:
        result = validate(args.batch_dir, args.dataset, args.pilot)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    print(f"PASS: {result['records']} blinded records across {result['batches']} batches")


if __name__ == "__main__":
    main()
