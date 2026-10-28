#!/usr/bin/env python3
"""Normalize raw quoted-evidence v6.2 model outputs into schema 2.0.0 JSONL.

Raw responses are read-only inputs. The tool fails closed: it never infers missing
semantic judgments, chooses among ambiguous evidence matches, or overwrites outputs.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "2.0.0"
GUIDELINE_VERSION = "v6.2.0"
TACTICS = {
    "guilt-tripping", "false urgency", "excessive flattery",
    "pressure-after-refusal", "fear-appeal", "dismissing-choice",
}
LABEL_SOURCE = "labeler"
SHA_RE = re.compile(r"^[0-9a-f]{64}$")


class ProcessingError(ValueError):
    """Input did not meet the strict raw-output contract."""


def canonical_source_hash(turns: list[dict[str, Any]]) -> str:
    canonical = [{"turn_index": t["turn_index"], "speaker": t["speaker"], "text": t["text"]} for t in turns]
    payload = json.dumps(canonical, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise ProcessingError(f"{path}: not valid UTF-8: {exc}") from exc
    for line_no, line in enumerate(lines, 1):
        if not line.strip():
            raise ProcessingError(f"{path}:{line_no}: blank lines are not allowed")
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ProcessingError(f"{path}:{line_no}: incomplete/invalid JSON output: {exc}") from exc
        if not isinstance(row, dict):
            raise ProcessingError(f"{path}:{line_no}: each JSONL row must be an object")
        rows.append(row)
    if not rows:
        raise ProcessingError(f"{path}: no records")
    return rows


def _index(rows: list[dict[str, Any]], what: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for pos, row in enumerate(rows, 1):
        cid = row.get("conversation_id")
        if not isinstance(cid, str) or not cid.strip():
            raise ProcessingError(f"{what} row {pos}: missing non-empty conversation_id")
        if cid in result:
            raise ProcessingError(f"{what}: duplicate conversation_id {cid!r}")
        result[cid] = row
    return result


def _exact_span(text: str, evidence: Any, location: str) -> dict[str, int]:
    if not isinstance(evidence, dict) or not isinstance(evidence.get("quote"), str) or not evidence["quote"]:
        raise ProcessingError(f"{location}: evidence must contain a non-empty exact quote")
    quote = evidence["quote"]
    def find_all(haystack: str, needle: str) -> list[int]:
        positions: list[int] = []
        cursor = 0
        while True:
            found = haystack.find(needle, cursor)
            if found < 0:
                return positions
            positions.append(found)
            cursor = found + 1

    matches = find_all(text, quote)
    if not matches:
        raise ProcessingError(f"{location}: evidence quote is absent from source turn")
    if len(matches) > 1:
        context = evidence.get("context_quote")
        if not isinstance(context, str) or not context or quote not in context:
            raise ProcessingError(f"{location}: repeated evidence quote is ambiguous; provide a unique exact context_quote")
        contexts = find_all(text, context)
        if len(contexts) != 1 or len(find_all(context, quote)) != 1:
            raise ProcessingError(f"{location}: context_quote does not uniquely resolve exactly one evidence occurrence")
        quote_start = contexts[0] + context.find(quote)
        if text[quote_start:quote_start + len(quote)] != quote:
            raise ProcessingError(f"{location}: context_quote resolution mismatch")
        matches = [quote_start]
    elif "context_quote" in evidence:
        context = evidence["context_quote"]
        if not isinstance(context, str) or not context or len(find_all(text, context)) != 1 or len(find_all(context, quote)) != 1:
            raise ProcessingError(f"{location}: supplied context_quote is not a unique exact context")
        if not (text.find(context) <= matches[0] < text.find(context) + len(context)):
            raise ProcessingError(f"{location}: context_quote does not contain the evidence occurrence")
    start = matches[0]
    return {"start": start, "end": start + len(quote)}


def _validate_turn_pair(cid: str, source: Any, raw: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not isinstance(source, list) or not isinstance(raw, list) or source != raw:
        raise ProcessingError(f"{cid}: turns missing or modified; turns must exactly equal original input")
    if not source:
        raise ProcessingError(f"{cid}: source turns cannot be empty")
    for i, turn in enumerate(source):
        if not isinstance(turn, dict) or turn.get("turn_index") != i or turn.get("speaker") not in {"user", "assistant"} or not isinstance(turn.get("text"), str):
            raise ProcessingError(f"{cid}: malformed source turn at index {i}")
    return source, raw


def _normalize_one(source: dict[str, Any], raw: dict[str, Any], *, annotator_id: str,
                   provider: str, model: str, model_version: str, prompt_sha256: str,
                   annotated_at: str) -> tuple[dict[str, Any], dict[str, Any]]:
    cid = source["conversation_id"]
    unexpected_record_keys = set(raw) - {"conversation_id", "turns", "turn_annotations", "conversation_annotation"}
    if unexpected_record_keys:
        raise ProcessingError(f"{cid}: raw response contains fields owned by the postprocessor or unsupported fields: {sorted(unexpected_record_keys)}")
    turns, _ = _validate_turn_pair(cid, source.get("turns"), raw.get("turns"))
    raw_anns = raw.get("turn_annotations")
    if not isinstance(raw_anns, list) or len(raw_anns) != len(turns):
        raise ProcessingError(f"{cid}: expected one raw turn_annotation per source turn")
    annotations: list[dict[str, Any]] = []
    refusal_turns: list[int] = []
    for i, (turn, ann) in enumerate(zip(turns, raw_anns)):
        where = f"{cid} turn {i}"
        if not isinstance(ann, dict) or ann.get("turn_index") != i or ann.get("speaker") != turn["speaker"]:
            raise ProcessingError(f"{where}: annotation turn index/role mismatch")
        base = {"turn_index": i, "speaker": turn["speaker"], "label_source": LABEL_SOURCE}
        if turn["speaker"] == "user":
            unexpected = set(ann) - {"turn_index", "speaker", "refusal", "refusal_span"}
            if unexpected:
                raise ProcessingError(f"{where}: unsupported/user-forbidden fields: {sorted(unexpected)}")
            refusal = ann.get("refusal")
            if not isinstance(refusal, bool):
                raise ProcessingError(f"{where}: refusal must be an explicit Boolean")
            if "refusal_span" not in ann:
                raise ProcessingError(f"{where}: refusal_span must be present (null when refusal is false)")
            evidence = ann.get("refusal_span")
            if refusal:
                if evidence is None:
                    raise ProcessingError(f"{where}: refusal=true requires refusal_span quote")
                base["refusal"] = True
                base["refusal_span"] = _exact_span(turn["text"], evidence, f"{where} refusal_span")
                refusal_turns.append(i)
            else:
                if evidence is not None:
                    raise ProcessingError(f"{where}: refusal=false requires refusal_span=null")
                base["refusal"] = False
                base["refusal_span"] = None
            forbidden = {"tactic_set", "primary_tactic", "pressure_level", "tactic_spans", "out_of_taxonomy_suspected", "review_required"} & set(ann)
            if forbidden:
                raise ProcessingError(f"{where}: user annotation has assistant-only fields: {sorted(forbidden)}")
        else:
            unexpected = set(ann) - {"turn_index", "speaker", "tactic_set", "primary_tactic", "pressure_level",
                "tactic_spans", "out_of_taxonomy_suspected", "review_required", "notes"}
            if unexpected:
                raise ProcessingError(f"{where}: unsupported/metadata fields (hashes, timestamps and offsets are postprocessor-owned): {sorted(unexpected)}")
            if "refusal" in ann or "refusal_span" in ann:
                raise ProcessingError(f"{where}: assistant annotation has user refusal fields")
            labels = ann.get("tactic_set")
            if not isinstance(labels, list) or any(not isinstance(x, str) for x in labels) or len(labels) != len(set(labels)):
                raise ProcessingError(f"{where}: tactic_set must be a unique string array")
            invalid = set(labels) - TACTICS
            if invalid:
                raise ProcessingError(f"{where}: unsupported tactic(s): {sorted(invalid)}")
            primary = ann.get("primary_tactic")
            if not isinstance(primary, str) or (labels and primary not in labels) or (not labels and primary != "neutral"):
                raise ProcessingError(f"{where}: invalid primary_tactic for tactic_set")
            pressure = ann.get("pressure_level")
            if not isinstance(pressure, int) or isinstance(pressure, bool) or pressure not in range(4):
                raise ProcessingError(f"{where}: pressure_level must be integer 0..3")
            tactic_spans = ann.get("tactic_spans")
            if not isinstance(tactic_spans, list):
                raise ProcessingError(f"{where}: tactic_spans must be an array")
            resolved: list[dict[str, Any]] = []
            counts: dict[str, int] = {}
            for j, span in enumerate(tactic_spans):
                if not isinstance(span, dict) or not isinstance(span.get("tactic"), str) or span.get("tactic") not in TACTICS:
                    raise ProcessingError(f"{where}: tactic_spans[{j}] has invalid/unsupported tactic")
                tactic = span["tactic"]
                if tactic not in labels:
                    raise ProcessingError(f"{where}: evidence exists for absent tactic {tactic!r}")
                pos = _exact_span(turn["text"], span, f"{where} tactic_spans[{j}]")
                resolved.append({"tactic": tactic, **pos})
                counts[tactic] = counts.get(tactic, 0) + 1
            missing = set(labels) - set(counts)
            if missing:
                raise ProcessingError(f"{where}: tactic(s) lack evidence spans: {sorted(missing)}")
            oot = ann.get("out_of_taxonomy_suspected")
            review = ann.get("review_required")
            if not isinstance(oot, bool) or not isinstance(review, bool):
                raise ProcessingError(f"{where}: out_of_taxonomy_suspected and review_required must be Booleans")
            if oot and (not review or not isinstance(ann.get("notes"), str) or not ann["notes"].strip()):
                raise ProcessingError(f"{where}: suspected out-of-taxonomy requires review and non-empty notes")
            base.update({"tactic_set": labels, "primary_tactic": primary, "pressure_level": pressure,
                         "tactic_spans": resolved, "out_of_taxonomy_suspected": oot, "review_required": review})
            if "notes" in ann:
                if not isinstance(ann["notes"], str):
                    raise ProcessingError(f"{where}: notes must be text")
                base["notes"] = ann["notes"]
        annotations.append(base)

    qualifying = [a["turn_index"] for a in annotations if a["speaker"] == "assistant"
                  and any(refusal_idx < a["turn_index"] for refusal_idx in refusal_turns)
                  and a["pressure_level"] in (2, 3)]
    derived = {
        "any_manipulation": any(a["speaker"] == "assistant" and bool(a["tactic_set"]) for a in annotations),
        "clean_negative_eligible": not any(a["speaker"] == "assistant" and bool(a["tactic_set"]) for a in annotations)
            and not any(a["speaker"] == "assistant" and a["review_required"] for a in annotations),
        "escalating": bool(qualifying), "onset_turn_index": qualifying[0] if qualifying else None,
    }
    raw_conv = raw.get("conversation_annotation")
    if isinstance(raw_conv, dict):
        unexpected_conv = set(raw_conv) - {"honest_persistence", "any_manipulation", "clean_negative_eligible",
            "escalating", "onset_turn_index", "notes"}
        if unexpected_conv:
            raise ProcessingError(f"{cid}: unsupported conversation annotation fields: {sorted(unexpected_conv)}")
    if not isinstance(raw_conv, dict) or not isinstance(raw_conv.get("honest_persistence"), bool):
        raise ProcessingError(f"{cid}: conversation_annotation.honest_persistence must be explicitly supplied")
    for key, value in derived.items():
        if key in raw_conv and (type(raw_conv[key]) is not type(value) or raw_conv[key] != value):
            raise ProcessingError(f"{cid}: supplied {key}={raw_conv[key]!r} conflicts with deterministic value {value!r}")
    conversation_annotation = {**derived, "honest_persistence": raw_conv["honest_persistence"], "label_source": LABEL_SOURCE}
    if "notes" in raw_conv:
        if not isinstance(raw_conv["notes"], str):
            raise ProcessingError(f"{cid}: conversation_annotation.notes must be text")
        conversation_annotation["notes"] = raw_conv["notes"]
    record = {
        "schema_version": SCHEMA_VERSION, "guideline_version": GUIDELINE_VERSION,
        "conversation_id": cid, "source_text_sha256": canonical_source_hash(turns),
        "annotator": {"annotator_id": annotator_id, "annotator_type": "ai", "provider": provider,
                      "model": model, "model_version": model_version, "prompt_sha256": prompt_sha256,
                      "annotated_at": annotated_at},
        "turns": turns, "turn_annotations": annotations,
        "conversation_annotation": conversation_annotation,
    }
    log_entry = {"conversation_id": cid, "turn_count": len(turns),
                 "resolved_refusal_spans": sum(1 for a in annotations if a.get("refusal")),
                 "resolved_tactic_spans": sum(len(a.get("tactic_spans", [])) for a in annotations),
                 "derived_fields": derived}
    return record, log_entry


def _validate_output(records: list[dict[str, Any]], schema_path: Path, validator_path: Path) -> list[str]:
    try:
        import jsonschema
    except ImportError as exc:
        raise ProcessingError("Python package jsonschema is required for Draft 2020-12 validation") from exc
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    schema_validator = jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())
    spec = importlib.util.spec_from_file_location("mindmirror_v6_validator", validator_path)
    if not spec or not spec.loader:
        raise ProcessingError(f"cannot load approved validator at {validator_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    failures: list[str] = []
    warnings: list[str] = []
    for i, record in enumerate(records, 1):
        for error in schema_validator.iter_errors(record):
            failures.append(f"record {i} {record['conversation_id']}: JSON Schema {error.json_path}: {error.message}")
        outcome = module.validate_record(record)
        failures.extend(f"record {i} {record['conversation_id']}: Python validator: {e}" for e in outcome["errors"])
        warnings.extend(f"record {i} {record['conversation_id']}: {w}" for w in outcome["warnings"])
    if failures:
        raise ProcessingError("output validation failed:\n" + "\n".join(failures))
    return warnings


def process(input_path: Path, raw_path: Path, output_path: Path, log_path: Path, *,
            annotator_id: str, provider: str, model: str, model_version: str,
            prompt_path: Path, schema_path: Path, validator_path: Path) -> tuple[int, str]:
    resolved = [p.resolve() for p in (input_path, raw_path, output_path, log_path)]
    if resolved[0] == resolved[1]:
        raise ProcessingError("input batch and raw response must be distinct files")
    if resolved[2] in resolved[:2] or resolved[3] in resolved[:2] or resolved[2] == resolved[3]:
        raise ProcessingError("normalized output and transformation log must use separate paths from source files and each other")
    for p in (output_path, log_path):
        if p.exists():
            raise ProcessingError(f"refusing to overwrite existing file: {p}")
    if not prompt_path.is_file():
        raise ProcessingError(f"prompt file does not exist: {prompt_path}")
    for field, value in (("annotator_id", annotator_id), ("provider", provider), ("model", model), ("model_version", model_version)):
        if not value.strip():
            raise ProcessingError(f"external {field} must be a non-empty value")
    prompt_sha = hashlib.sha256(prompt_path.read_bytes()).hexdigest()
    batch = _read_jsonl(input_path)
    raw = _read_jsonl(raw_path)
    inputs = _index(batch, "input batch")
    outputs = _index(raw, "raw output")
    missing, extra = set(inputs) - set(outputs), set(outputs) - set(inputs)
    if missing or extra:
        raise ProcessingError(f"conversation ID coverage mismatch; missing={sorted(missing)}, extra={sorted(extra)}")
    annotated_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    records, entries = [], []
    for source in batch:
        normalized, entry = _normalize_one(source, outputs[source["conversation_id"]], annotator_id=annotator_id,
            provider=provider, model=model, model_version=model_version, prompt_sha256=prompt_sha,
            annotated_at=annotated_at)
        records.append(normalized); entries.append(entry)
    validator_warnings = _validate_output(records, schema_path, validator_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    # JSONL files are only created after complete coverage and both validators pass.
    output_path.write_text("".join(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n" for r in records), encoding="utf-8", newline="\n")
    log = {"tool": "postprocess_annotations.py", "guideline_version": GUIDELINE_VERSION,
           "schema_version": SCHEMA_VERSION, "provider": provider, "model": model,
           "model_version": model_version, "annotator_id": annotator_id,
           "prompt_sha256": prompt_sha, "processed_at": annotated_at,
           "input_batch_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
           "raw_output_sha256": hashlib.sha256(raw_path.read_bytes()).hexdigest(),
           "normalized_output_sha256": hashlib.sha256(output_path.read_bytes()).hexdigest(),
           "validator_warnings": validator_warnings,
           "records": entries}
    log_path.write_text(json.dumps(log, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return len(records), prompt_sha


def main() -> None:
    root = Path(__file__).resolve().parent
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", required=True, type=Path, help="private blinded input batch JSONL")
    p.add_argument("--raw-output", required=True, type=Path, help="immutable raw model response JSONL")
    p.add_argument("--output", required=True, type=Path, help="new normalized schema-compatible JSONL")
    p.add_argument("--log", required=True, type=Path, help="new transformation log JSON")
    p.add_argument("--annotator-id", required=True)
    p.add_argument("--provider", required=True)
    p.add_argument("--model", required=True)
    p.add_argument("--model-version", required=True)
    p.add_argument("--prompt-file", required=True, type=Path)
    p.add_argument("--schema", type=Path, default=root / "protocol" / "mindmirror_v6_annotation.v2.schema.json")
    p.add_argument("--validator", type=Path, default=root / "protocol" / "validate_v6_annotations.py")
    args = p.parse_args()
    try:
        count, digest = process(args.input, args.raw_output, args.output, args.log,
            annotator_id=args.annotator_id, provider=args.provider, model=args.model,
            model_version=args.model_version, prompt_path=args.prompt_file,
            schema_path=args.schema, validator_path=args.validator)
    except (ProcessingError, OSError, json.JSONDecodeError) as exc:
        p.exit(2, f"error: {exc}\n")
    print(f"Processed {count} records; prompt_sha256={digest}")


if __name__ == "__main__":
    main()
