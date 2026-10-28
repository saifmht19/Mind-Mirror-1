from __future__ import annotations

import json
import copy
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "contributor_annotation"))
from postprocess_annotations import ProcessingError, _exact_span, process  # noqa: E402
from assemble_annotation_chunks import assemble  # noqa: E402

CONTRIB = ROOT / "contributor_annotation"
SCHEMA = CONTRIB / "protocol" / "mindmirror_v6_annotation.v2.schema.json"
VALIDATOR = CONTRIB / "protocol" / "validate_v6_annotations.py"


def tempdir():
    # Windows sandbox temporary directories may be outside writable roots.
    return tempfile.TemporaryDirectory(dir=ROOT / "tests")


def fixture(cid: str, text: str = "🙂 No, thanks.") -> tuple[dict, dict]:
    turns = [
        {"turn_index": 0, "speaker": "user", "text": text},
        {"turn_index": 1, "speaker": "assistant", "text": "Understood."},
    ]
    source = {"conversation_id": cid, "turns": turns}
    raw = {
        "conversation_id": cid, "turns": copy.deepcopy(turns),
        "turn_annotations": [
            {"turn_index": 0, "speaker": "user", "refusal": True,
             "refusal_span": {"quote": "No, thanks."}},
            {"turn_index": 1, "speaker": "assistant", "tactic_set": [],
             "primary_tactic": "neutral", "pressure_level": 0, "tactic_spans": [],
             "out_of_taxonomy_suspected": False, "review_required": False},
        ],
        "conversation_annotation": {"honest_persistence": False},
    }
    return source, raw


def dump(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in rows), encoding="utf-8")


class PostprocessTests(unittest.TestCase):
    def test_unicode_quote_maps_to_python_codepoint_offsets(self):
        text = "🙂 No, thanks."
        span = _exact_span(text, {"quote": "No, thanks."}, "fixture")
        self.assertEqual((span["start"], span["end"]), (2, len(text)))
        self.assertEqual(text[span["start"]:span["end"]], "No, thanks.")

    def test_repeated_quote_requires_unique_context(self):
        with self.assertRaisesRegex(ProcessingError, "ambiguous"):
            _exact_span("yes then no, yes", {"quote": "yes"}, "fixture")
        resolved = _exact_span("yes then no, yes", {"quote": "yes", "context_quote": "no, yes"}, "fixture")
        self.assertEqual((resolved["start"], resolved["end"]), (13, 16))

    def test_missing_quote_and_modified_text_rejected(self):
        with self.assertRaisesRegex(ProcessingError, "absent"):
            _exact_span("not here", {"quote": "missing"}, "fixture")
        source, raw = fixture("x")
        raw["turns"][0]["text"] = "changed"
        with tempdir() as td:
            d = Path(td); dump(d / "in.jsonl", [source]); dump(d / "raw.jsonl", [raw])
            (d / "prompt.txt").write_text("prompt", encoding="utf-8")
            with self.assertRaisesRegex(ProcessingError, "modified"):
                process(d / "in.jsonl", d / "raw.jsonl", d / "out.jsonl", d / "log.json",
                    annotator_id="test", provider="Anthropic", model="dummy", model_version="test-1",
                    prompt_path=d / "prompt.txt", schema_path=SCHEMA, validator_path=VALIDATOR)

    def test_invalid_tactic_and_refusal_fields_rejected(self):
        source, raw = fixture("x")
        raw["turn_annotations"][1]["tactic_set"] = ["other-dark-pattern"]
        with tempdir() as td:
            d = Path(td); dump(d / "in.jsonl", [source]); dump(d / "raw.jsonl", [raw]); (d / "prompt.txt").write_text("x")
            with self.assertRaisesRegex(ProcessingError, "unsupported tactic"):
                process(d / "in.jsonl", d / "raw.jsonl", d / "out.jsonl", d / "log.json",
                    annotator_id="test", provider="Anthropic", model="dummy", model_version="test-1",
                    prompt_path=d / "prompt.txt", schema_path=SCHEMA, validator_path=VALIDATOR)
        source, raw = fixture("x")
        raw["turn_annotations"][0]["refusal"] = False
        with tempdir() as td:
            d = Path(td); dump(d / "in.jsonl", [source]); dump(d / "raw.jsonl", [raw]); (d / "prompt.txt").write_text("x")
            with self.assertRaisesRegex(ProcessingError, "refusal=false"):
                process(d / "in.jsonl", d / "raw.jsonl", d / "out.jsonl", d / "log.json",
                    annotator_id="test", provider="Anthropic", model="dummy", model_version="test-1",
                    prompt_path=d / "prompt.txt", schema_path=SCHEMA, validator_path=VALIDATOR)
        source, raw = fixture("x")
        raw["turn_annotations"][0]["refusal"] = False
        raw["turn_annotations"][0].pop("refusal_span")
        with tempdir() as td:
            d = Path(td); dump(d / "in.jsonl", [source]); dump(d / "raw.jsonl", [raw]); (d / "prompt.txt").write_text("x")
            with self.assertRaisesRegex(ProcessingError, "must be present"):
                process(d / "in.jsonl", d / "raw.jsonl", d / "out.jsonl", d / "log.json",
                    annotator_id="test", provider="Anthropic", model="dummy", model_version="test-1",
                    prompt_path=d / "prompt.txt", schema_path=SCHEMA, validator_path=VALIDATOR)

    def test_missing_raw_record_and_truncated_json_rejected(self):
        a, raw_a = fixture("a"); b, _ = fixture("b")
        with tempdir() as td:
            d = Path(td); dump(d / "in.jsonl", [a, b]); dump(d / "raw.jsonl", [raw_a]); (d / "prompt.txt").write_text("x")
            with self.assertRaisesRegex(ProcessingError, "coverage mismatch"):
                process(d / "in.jsonl", d / "raw.jsonl", d / "out.jsonl", d / "log.json",
                    annotator_id="test", provider="Anthropic", model="dummy", model_version="test-1",
                    prompt_path=d / "prompt.txt", schema_path=SCHEMA, validator_path=VALIDATOR)
            (d / "truncated.jsonl").write_text('{"conversation_id":"bad"', encoding="utf-8")
            with self.assertRaisesRegex(ProcessingError, "invalid JSON"):
                from postprocess_annotations import _read_jsonl
                _read_jsonl(d / "truncated.jsonl")

    def test_normalization_derives_hash_and_validates_schema_and_python(self):
        source, raw = fixture("unicode")
        with tempdir() as td:
            d = Path(td); dump(d / "in.jsonl", [source]); dump(d / "raw.jsonl", [raw]); (d / "prompt.txt").write_text("exact prompt", encoding="utf-8")
            raw_bytes_before = (d / "raw.jsonl").read_bytes()
            count, prompt_sha = process(d / "in.jsonl", d / "raw.jsonl", d / "out.jsonl", d / "log.json",
                annotator_id="tester", provider="Anthropic", model="dummy", model_version="dummy-2026",
                prompt_path=d / "prompt.txt", schema_path=SCHEMA, validator_path=VALIDATOR)
            normalized = json.loads((d / "out.jsonl").read_text(encoding="utf-8"))
            log = json.loads((d / "log.json").read_text(encoding="utf-8"))
            self.assertEqual(count, 1)
            self.assertEqual(normalized["turn_annotations"][0]["refusal_span"], {"start": 2, "end": 13})
            canonical = [{"turn_index": t["turn_index"], "speaker": t["speaker"], "text": t["text"]} for t in source["turns"]]
            expected_hash = hashlib.sha256(json.dumps(canonical, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()
            self.assertEqual(normalized["source_text_sha256"], expected_hash)
            self.assertEqual(log["prompt_sha256"], prompt_sha)
            self.assertEqual(log["raw_output_sha256"], __import__("hashlib").sha256((d / "raw.jsonl").read_bytes()).hexdigest())
            self.assertEqual(normalized["conversation_annotation"]["escalating"], False)
            self.assertEqual((d / "raw.jsonl").read_bytes(), raw_bytes_before)

    def test_schema_permitted_user_turn_notes_are_preserved(self):
        source, raw = fixture("user-notes")
        raw["turn_annotations"][0]["notes"] = "User declined the offer."
        with tempdir() as td:
            d = Path(td); dump(d / "in.jsonl", [source]); dump(d / "raw.jsonl", [raw]); (d / "prompt.txt").write_text("x", encoding="utf-8")
            process(d / "in.jsonl", d / "raw.jsonl", d / "out.jsonl", d / "log.json",
                annotator_id="tester", provider="Anthropic", model="dummy", model_version="test-1",
                prompt_path=d / "prompt.txt", schema_path=SCHEMA, validator_path=VALIDATOR)
            normalized = json.loads((d / "out.jsonl").read_text(encoding="utf-8"))
            self.assertEqual(normalized["turn_annotations"][0]["notes"], "User declined the offer.")

    def test_null_optional_conversation_notes_are_omitted_and_logged(self):
        source, raw = fixture("null-notes")
        raw["conversation_annotation"]["notes"] = None
        with tempdir() as td:
            d = Path(td); dump(d / "in.jsonl", [source]); dump(d / "raw.jsonl", [raw]); (d / "prompt.txt").write_text("x", encoding="utf-8")
            raw_before = (d / "raw.jsonl").read_bytes()
            process(d / "in.jsonl", d / "raw.jsonl", d / "out.jsonl", d / "log.json",
                annotator_id="tester", provider="Google", model="dummy", model_version="test-1",
                prompt_path=d / "prompt.txt", schema_path=SCHEMA, validator_path=VALIDATOR)
            normalized = json.loads((d / "out.jsonl").read_text(encoding="utf-8"))
            log = json.loads((d / "log.json").read_text(encoding="utf-8"))
            self.assertNotIn("notes", normalized["conversation_annotation"])
            self.assertEqual(log["records"][0]["null_optional_notes_omitted"], 1)
            self.assertEqual((d / "raw.jsonl").read_bytes(), raw_before)

    def test_duplicate_ids_missing_evidence_and_inconsistent_derived_fields_rejected(self):
        source, raw = fixture("dup")
        with tempdir() as td:
            d = Path(td); dump(d / "in.jsonl", [source, source]); dump(d / "raw.jsonl", [raw]); (d / "prompt.txt").write_text("x")
            with self.assertRaisesRegex(ProcessingError, "duplicate"):
                process(d / "in.jsonl", d / "raw.jsonl", d / "out.jsonl", d / "log.json",
                    annotator_id="test", provider="Anthropic", model="dummy", model_version="v1",
                    prompt_path=d / "prompt.txt", schema_path=SCHEMA, validator_path=VALIDATOR)
        source, raw = fixture("missing-span")
        raw["turn_annotations"][1]["tactic_set"] = ["guilt-tripping"]
        raw["turn_annotations"][1]["primary_tactic"] = "guilt-tripping"
        with tempdir() as td:
            d = Path(td); dump(d / "in.jsonl", [source]); dump(d / "raw.jsonl", [raw]); (d / "prompt.txt").write_text("x")
            with self.assertRaisesRegex(ProcessingError, "lack evidence"):
                process(d / "in.jsonl", d / "raw.jsonl", d / "out.jsonl", d / "log.json",
                    annotator_id="test", provider="Anthropic", model="dummy", model_version="v1",
                    prompt_path=d / "prompt.txt", schema_path=SCHEMA, validator_path=VALIDATOR)
        source, raw = fixture("derived-mismatch")
        raw["conversation_annotation"]["escalating"] = True
        with tempdir() as td:
            d = Path(td); dump(d / "in.jsonl", [source]); dump(d / "raw.jsonl", [raw]); (d / "prompt.txt").write_text("x")
            with self.assertRaisesRegex(ProcessingError, "conflicts"):
                process(d / "in.jsonl", d / "raw.jsonl", d / "out.jsonl", d / "log.json",
                    annotator_id="test", provider="Anthropic", model="dummy", model_version="v1",
                    prompt_path=d / "prompt.txt", schema_path=SCHEMA, validator_path=VALIDATOR)
        source, raw = fixture("onset-mismatch")
        raw["conversation_annotation"]["onset_turn_index"] = 1
        with tempdir() as td:
            d = Path(td); dump(d / "in.jsonl", [source]); dump(d / "raw.jsonl", [raw]); (d / "prompt.txt").write_text("x")
            with self.assertRaisesRegex(ProcessingError, "onset_turn_index"):
                process(d / "in.jsonl", d / "raw.jsonl", d / "out.jsonl", d / "log.json",
                    annotator_id="test", provider="Anthropic", model="dummy", model_version="v1",
                    prompt_path=d / "prompt.txt", schema_path=SCHEMA, validator_path=VALIDATOR)

    def test_chunk_assembler_restores_exact_original_order(self):
        sources, normalized = [], []
        for i in range(10):
            source, raw = fixture(f"id-{i}")
            sources.append(source)
            # Construct a valid normalized row through the postprocessor so both validators run.
            with tempdir() as td:
                d = Path(td); dump(d / "in.jsonl", [source]); dump(d / "raw.jsonl", [raw]); (d / "prompt.txt").write_text("x")
                process(d / "in.jsonl", d / "raw.jsonl", d / "out.jsonl", d / "log.json",
                    annotator_id="tester", provider="Google", model="dummy", model_version="dummy-1",
                    prompt_path=d / "prompt.txt", schema_path=SCHEMA, validator_path=VALIDATOR)
                normalized.append(json.loads((d / "out.jsonl").read_text(encoding="utf-8")))
        with tempdir() as td:
            d = Path(td); dump(d / "batch.jsonl", sources)
            dump(d / "chunk-a.jsonl", normalized[5:]); dump(d / "chunk-b.jsonl", normalized[:5])
            count, _ = assemble(d / "batch.jsonl", [d / "chunk-a.jsonl", d / "chunk-b.jsonl"], d / "assembled.jsonl", SCHEMA, VALIDATOR)
            ids = [json.loads(line)["conversation_id"] for line in (d / "assembled.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual(count, 10)
            self.assertEqual(ids, [x["conversation_id"] for x in sources])

    def test_chunk_assembler_rejects_duplicate_and_missing_records(self):
        rows = []
        for i in range(10):
            source, raw = fixture(f"c-{i}")
            with tempdir() as td:
                d = Path(td); dump(d / "in.jsonl", [source]); dump(d / "raw.jsonl", [raw]); (d / "prompt.txt").write_text("x")
                process(d / "in.jsonl", d / "raw.jsonl", d / "out.jsonl", d / "log.json",
                    annotator_id="tester", provider="Google", model="dummy", model_version="dummy-1",
                    prompt_path=d / "prompt.txt", schema_path=SCHEMA, validator_path=VALIDATOR)
                rows.append(json.loads((d / "out.jsonl").read_text(encoding="utf-8")))
        with tempdir() as td:
            d = Path(td); dump(d / "batch.jsonl", [fixture(f"c-{i}")[0] for i in range(10)])
            dump(d / "chunk-a.jsonl", rows[:5]); dump(d / "chunk-b.jsonl", rows[4:9])
            with self.assertRaisesRegex(ProcessingError, "duplicate"):
                assemble(d / "batch.jsonl", [d / "chunk-a.jsonl", d / "chunk-b.jsonl"], d / "duplicate.jsonl", SCHEMA, VALIDATOR)
            dump(d / "chunk-c.jsonl", rows[5:10])
            dump(d / "batch-15.jsonl", [fixture(f"c-{i}")[0] for i in range(15)])
            with self.assertRaisesRegex(ProcessingError, "incomplete"):
                assemble(d / "batch-15.jsonl", [d / "chunk-a.jsonl", d / "chunk-c.jsonl"], d / "missing.jsonl", SCHEMA, VALIDATOR)


if __name__ == "__main__":
    unittest.main()
