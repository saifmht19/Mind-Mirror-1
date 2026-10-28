#!/usr/bin/env python3
"""Assemble independently normalized 5–10-record chunks into original batch order."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from postprocess_annotations import ProcessingError, _index, _read_jsonl, _validate_output


def assemble(batch_path: Path, chunk_paths: list[Path], output_path: Path,
             schema_path: Path, validator_path: Path) -> tuple[int, str]:
    if not chunk_paths:
        raise ProcessingError("supply one or more chunk JSONL files")
    if output_path.exists():
        raise ProcessingError(f"refusing to overwrite existing output: {output_path}")
    batch = _read_jsonl(batch_path)
    originals = _index(batch, "input batch")
    merged: dict[str, dict[str, Any]] = {}
    for chunk_path in chunk_paths:
        rows = _read_jsonl(chunk_path)
        if not 5 <= len(rows) <= 10:
            raise ProcessingError(f"{chunk_path}: chunk must contain 5–10 records, got {len(rows)}")
        chunk = _index(rows, str(chunk_path))
        repeated = set(merged) & set(chunk)
        if repeated:
            raise ProcessingError(f"duplicate IDs across chunks: {sorted(repeated)}")
        for cid, record in chunk.items():
            if cid not in originals:
                raise ProcessingError(f"{chunk_path}: unknown conversation ID {cid!r}")
            if record.get("turns") != originals[cid].get("turns"):
                raise ProcessingError(f"{chunk_path}: source text/turn structure modified for {cid}")
            merged[cid] = record
    missing = set(originals) - set(merged)
    if missing:
        raise ProcessingError(f"incomplete chunks; missing IDs: {sorted(missing)}")
    records = [merged[row["conversation_id"]] for row in batch]
    _validate_output(records, schema_path, validator_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("".join(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n" for r in records), encoding="utf-8", newline="\n")
    digest = hashlib.sha256(output_path.read_bytes()).hexdigest()
    return len(records), digest


def main() -> None:
    root = Path(__file__).resolve().parent
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--batch", required=True, type=Path)
    p.add_argument("--chunk", required=True, action="append", type=Path,
                   help="normalized 5–10 conversation JSONL chunk; repeat in any order")
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--schema", type=Path, default=root / "protocol" / "mindmirror_v6_annotation.v2.schema.json")
    p.add_argument("--validator", type=Path, default=root / "protocol" / "validate_v6_annotations.py")
    args = p.parse_args()
    try:
        count, digest = assemble(args.batch, args.chunk, args.output, args.schema, args.validator)
    except (ProcessingError, OSError) as exc:
        p.exit(2, f"error: {exc}\n")
    print(f"Assembled {count} records in original batch order; sha256={digest}")


if __name__ == "__main__":
    main()
