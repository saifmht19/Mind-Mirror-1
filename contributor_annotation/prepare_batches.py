#!/usr/bin/env python3
"""Prepare deterministic, blinded MindMirror v6 annotation input batches.

The cleaned source and pilot must be supplied by the project lead. This script
does not infer pilot membership or copy source metadata into contributor inputs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

PROTOCOL_VERSION = "v6.2.0"
PROTOCOL_COMMIT = "afe1f584b8867fa65c8c2e791d4cbc83f915f04f"
EXPECTED_TOTAL = 800
EXPECTED_PILOT = 20
EXPECTED_ANNOTATE = EXPECTED_TOTAL - EXPECTED_PILOT


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_records(path: Path) -> list[dict[str, Any]]:
    raw = path.read_text(encoding="utf-8-sig")
    if path.suffix.lower() == ".json":
        parsed = json.loads(raw)
        if not isinstance(parsed, list):
            raise ValueError(f"{path}: expected a JSON array")
        values = parsed
    else:
        values = []
        for number, line in enumerate(raw.splitlines(), 1):
            if not line.strip():
                continue
            try:
                values.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{number}: invalid JSON: {exc}") from exc
    if any(not isinstance(value, dict) for value in values):
        raise ValueError(f"{path}: every record must be a JSON object")
    return values


def conversation_id(record: dict[str, Any]) -> str:
    value = record.get("conversation_id")
    if not isinstance(value, str) or not value.strip():
        raise ValueError("every source and pilot record needs a non-empty conversation_id")
    return value


def blind_record(source: dict[str, Any]) -> dict[str, Any]:
    turns_in = source.get("turns")
    if not isinstance(turns_in, list) or not turns_in:
        raise ValueError(f"{conversation_id(source)}: turns must be a non-empty list")
    turns = []
    for index, original in enumerate(turns_in):
        if not isinstance(original, dict):
            raise ValueError(f"{conversation_id(source)} turn {index}: expected object")
        speaker = original.get("speaker", original.get("role"))
        text = original.get("text", original.get("content"))
        if speaker not in {"user", "assistant"} or not isinstance(text, str) or not text.strip():
            raise ValueError(f"{conversation_id(source)} turn {index}: invalid speaker or text")
        if "turn_index" in original and original["turn_index"] != index:
            raise ValueError(f"{conversation_id(source)} turn {index}: non-canonical turn_index")
        turns.append({"turn_index": index, "speaker": speaker, "text": text})
    domain = source.get("domain")
    if not isinstance(domain, str) or not domain.strip():
        raise ValueError(f"{conversation_id(source)}: domain must be present for stratified review")
    # Deliberately whitelist only fields visible to either independent annotator.
    return {"conversation_id": conversation_id(source), "domain": domain, "turns": turns}


def load_pilot_ids(path: Path) -> set[str]:
    records = read_records(path)
    ids = [conversation_id(record) for record in records]
    if len(ids) != EXPECTED_PILOT or len(set(ids)) != EXPECTED_PILOT:
        raise ValueError(f"pilot must contain exactly 20 unique conversation IDs; found {len(ids)} records")
    return set(ids)


def prepare(dataset_path: Path, pilot_path: Path, out_dir: Path, batch_size: int) -> dict[str, Any]:
    if not 1 <= batch_size <= 50:
        raise ValueError("batch_size must be between 1 and 50")
    data = read_records(dataset_path)
    pilot_ids = load_pilot_ids(pilot_path)
    if len(data) != EXPECTED_TOTAL:
        raise ValueError(f"expected 800 cleaned source records; found {len(data)}")
    ids = [conversation_id(record) for record in data]
    if len(set(ids)) != EXPECTED_TOTAL:
        raise ValueError("cleaned source must contain 800 unique conversation IDs")
    absent = pilot_ids - set(ids)
    if absent:
        raise ValueError(f"pilot IDs are not in cleaned source: {sorted(absent)}")
    selected = [blind_record(record) for record in data if conversation_id(record) not in pilot_ids]
    if len(selected) != EXPECTED_ANNOTATE:
        raise ValueError(f"expected 780 non-pilot records; found {len(selected)}")

    out_dir.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {
        "format_version": "mindmirror-v6-blinded-input-1.0.0",
        "protocol_version": PROTOCOL_VERSION,
        "protocol_commit_sha": PROTOCOL_COMMIT,
        "protocol_readiness": "pending_research_lead_ratification",
        "source_dataset_sha256": sha256(dataset_path.read_bytes()),
        "pilot_sha256": sha256(pilot_path.read_bytes()),
        "total_dataset": EXPECTED_TOTAL,
        "pilot_excluded": EXPECTED_PILOT,
        "to_annotate": EXPECTED_ANNOTATE,
        "batch_size": batch_size,
        "batches": [],
    }
    for start in range(0, len(selected), batch_size):
        subset = selected[start : start + batch_size]
        name = f"batch_{start // batch_size + 1:03d}.jsonl"
        body = "".join(json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n" for item in subset)
        (out_dir / name).write_text(body, encoding="utf-8", newline="\n")
        manifest["batches"].append({
            "filename": name,
            "count": len(subset),
            "conversation_ids": [item["conversation_id"] for item in subset],
            "sha256": sha256(body.encode("utf-8")),
        })
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True, type=Path, help="cleaned 800-record JSONL")
    parser.add_argument("--pilot", required=True, type=Path, help="frozen 20-record pilot JSON or JSONL")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--batch-size", type=int, default=40)
    args = parser.parse_args()
    try:
        manifest = prepare(args.dataset, args.pilot, args.out, args.batch_size)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    print(f"Prepared {manifest['to_annotate']} blinded non-pilot records in {len(manifest['batches'])} deterministic batches")
    print(f"Protocol {manifest['protocol_version']} ({manifest['protocol_commit_sha']}); status: {manifest['protocol_readiness']}")


if __name__ == "__main__":
    main()
