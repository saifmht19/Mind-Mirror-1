#!/usr/bin/env python3
"""Make deterministic, blinded contributor batches; no APIs and no data mutation."""
import argparse
import hashlib
import json
from pathlib import Path

def read_jsonl(path):
    items = []
    for n, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if line.strip():
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise SystemExit(f"{path}:{n}: invalid JSON: {exc}")
    return items

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dataset", required=True, type=Path)
    p.add_argument("--pilot", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--batch-size", type=int, default=40)
    args = p.parse_args()
    if args.batch_size < 1 or args.batch_size > 50:
        p.error("--batch-size must be 1..50")
    data, pilot = read_jsonl(args.dataset), read_jsonl(args.pilot)
    ids = [x.get("conversation_id") for x in data]
    excluded = [x.get("conversation_id") for x in pilot]
    if len(data) != 800 or len(pilot) != 20:
        raise SystemExit(f"Expected 800 dataset and 20 pilot; got {len(data)} and {len(pilot)}")
    if len(ids) != len(set(ids)) or len(excluded) != len(set(excluded)) or not set(excluded) <= set(ids):
        raise SystemExit("Duplicate IDs or pilot IDs not contained in the dataset")
    selected = [x for x in data if x["conversation_id"] not in set(excluded)]
    if len(selected) != 780:
        raise SystemExit(f"Expected 780 nonpilot records, got {len(selected)}")
    # Strict blinding: user-visible textual turns only; strip annotation and generator fields.
    clean = []
    for x in selected:
        if not isinstance(x.get("turns"), list):
            raise SystemExit(f"No list of turns for {x['conversation_id']}")
        turns = []
        for i, t in enumerate(x["turns"]):
            speaker = t.get("speaker", t.get("role"))
            msg = t.get("text", t.get("content"))
            if speaker not in ("assistant", "user") or not isinstance(msg, str):
                raise SystemExit(f"Nonstandard turn in {x['conversation_id']} index {i}; inspect schema before batching")
            turns.append({"turn_index": t.get("turn_index", i), "speaker": speaker, "text": msg,
                "user_refusal": {"refusal": None,"span_start": None,"span_end": None,"notes": ""} if speaker=="user" else None,
                "assistant_annotation": {"tactic_set": None,"primary_tactic": None,"pressure_level_0_3": None,"tactic_spans": [],"notes": ""} if speaker=="assistant" else None})
        clean.append({"conversation_id": x["conversation_id"],"domain": x.get("domain"),"turns": turns,
            "conversation_annotation": {"escalating": None,"onset_turn_index": None,
                "honest_persistence": None,"adjudication_required": None,"annotator_id": "","notes": ""}})
    args.out.mkdir(parents=True, exist_ok=True)
    manifest = {"source_dataset_sha256": hashlib.sha256(args.dataset.read_bytes()).hexdigest(),
        "pilot_sha256": hashlib.sha256(args.pilot.read_bytes()).hexdigest(),
        "total_dataset": 800, "pilot_excluded": 20, "to_annotate": 780,
        "batch_size": args.batch_size,"batches": []}
    for pos in range(0, len(clean), args.batch_size):
        subset = clean[pos:pos+args.batch_size]
        name = f"batch_{pos//args.batch_size + 1:03d}.jsonl"
        body = "".join(json.dumps(v, ensure_ascii=False) + "\n" for v in subset)
        (args.out/name).write_text(body, encoding="utf-8")
        manifest["batches"].append({"filename": name,"count": len(subset),
            "conversation_ids": [v["conversation_id"] for v in subset],
            "sha256": hashlib.sha256(body.encode("utf-8")).hexdigest()})
    (args.out/"manifest.json").write_text(json.dumps(manifest, indent=2)+"\n", encoding="utf-8")
    print(f"Prepared 780 nonpilot conversations in {len(manifest['batches'])} batches at {args.out}")
    print("IMPORTANT: verify compatibility with Track A's final schema before annotating.")

if __name__ == "__main__":
    main()
