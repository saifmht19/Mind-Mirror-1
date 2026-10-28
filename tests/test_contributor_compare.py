import copy
import json
import tempfile
import unittest
from pathlib import Path
import sys

from contributor_annotation.compare_annotations import compare, canonical_source_hash, jsonl_bytes, validate_output

PROTOCOL_DIR = Path(__file__).parents[1] / "contributor_annotation" / "protocol"
sys.path.insert(0, str(PROTOCOL_DIR))
from validate_v6_annotations import validate_record


def make_record(cid="dummy-001", review=False, tactic="neutral"):
    turns = [
        {"turn_index": 0, "speaker": "user", "text": "No thanks."},
        {"turn_index": 1, "speaker": "assistant", "text": "Understood. I won't continue; the choice is yours."},
    ]
    anns = [
        {"turn_index": 0, "speaker": "user", "label_source": "human",
         "refusal": True, "refusal_span": {"start": 0, "end": 10}},
        {"turn_index": 1, "speaker": "assistant", "label_source": "human",
         "tactic_set": [], "primary_tactic": "neutral", "pressure_level": 0,
         "tactic_spans": [], "out_of_taxonomy_suspected": False,
         "review_required": review, "notes": ""},
    ]
    return {
        "schema_version": "2.0.0", "guideline_version": "v6.2.0",
        "conversation_id": cid, "source_text_sha256": canonical_source_hash(turns),
        "annotator": {"annotator_id": "dummy-annotator", "annotator_type": "human",
                      "annotated_at": "2026-10-28T00:00:00Z"},
        "turns": turns, "turn_annotations": anns,
        "conversation_annotation": {"any_manipulation": False, "clean_negative_eligible": not review,
                                    "escalating": False, "onset_turn_index": None,
                                    "honest_persistence": False, "label_source": "human"},
    }


class CompareTests(unittest.TestCase):
    def write_jsonl(self, path, rows):
        path.write_bytes(jsonl_bytes(rows))

    def run_compare(self, source, a, b, root):
        paths = [root / name for name in ("input.jsonl", "a.jsonl", "b.jsonl")]
        for path, rows in zip(paths, (source, a, b)):
            self.write_jsonl(path, rows)
        before = [p.read_bytes() for p in paths]
        out = root / "out"
        report = compare(*paths, out)
        self.assertEqual(before, [p.read_bytes() for p in paths])
        queue = [json.loads(line) for line in (out / "disagreement_queue.jsonl").read_text().splitlines() if line]
        return report, queue

    def test_identical_records_have_full_agreement_and_empty_queue(self):
        rec = make_record()
        with tempfile.TemporaryDirectory(dir=Path(__file__).parents[1]) as d:
            report, queue = self.run_compare([rec], [rec], [copy.deepcopy(rec)], Path(d))
        self.assertEqual(report["records"], 1)
        self.assertEqual(report["review_queue_count"], 0)
        self.assertEqual(queue, [])

    def test_disagreement_is_queued_without_conversation_text(self):
        a, b = make_record(), make_record()
        b["turn_annotations"][0]["refusal_span"] = {"start": 0, "end": 2}
        with tempfile.TemporaryDirectory(dir=Path(__file__).parents[1]) as d:
            _, queue = self.run_compare([a], [a], [b], Path(d))
        self.assertEqual(queue[0]["queue_reasons"], ["annotator_disagreement"])
        self.assertNotIn("text", json.dumps(queue))

    def test_shared_review_flag_still_enters_human_queue(self):
        rec = make_record(review=True)
        with tempfile.TemporaryDirectory(dir=Path(__file__).parents[1]) as d:
            _, queue = self.run_compare([rec], [rec], [copy.deepcopy(rec)], Path(d))
        self.assertEqual(queue[0]["queue_reasons"], ["review_flagged"])

    def test_changed_turn_text_is_rejected(self):
        src, a = make_record(), make_record()
        a["turns"][1]["text"] += " changed"
        with tempfile.TemporaryDirectory(dir=Path(__file__).parents[1]) as d, self.assertRaisesRegex(ValueError, "changed source turns"):
            self.run_compare([src], [a], [src], Path(d))

    def test_missing_or_reordered_ids_are_rejected(self):
        one, two = make_record("one"), make_record("two")
        with tempfile.TemporaryDirectory(dir=Path(__file__).parents[1]) as d, self.assertRaisesRegex(ValueError, "IDs/order"):
            self.run_compare([one, two], [two, one], [one, two], Path(d))

    def test_hash_mismatch_is_rejected(self):
        rec = make_record()
        rec["source_text_sha256"] = "0" * 64
        with tempfile.TemporaryDirectory(dir=Path(__file__).parents[1]) as d, self.assertRaisesRegex(ValueError, "sha256 mismatch"):
            self.run_compare([rec], [rec], [rec], Path(d))

    def test_dummy_example_passes_track_a_v62_validator(self):
        rec = make_record()
        validator = PROTOCOL_DIR / "validate_v6_annotations.py"
        self.assertEqual(validate_output(rec, validator), [])

    def test_schema_has_exactly_six_canonical_pilot_tactics(self):
        schema = json.loads((PROTOCOL_DIR / "mindmirror_v6_annotation.v2.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(set(schema["$defs"]["tactic"]["enum"]), {
            "guilt-tripping", "false urgency", "excessive flattery",
            "pressure-after-refusal", "fear-appeal", "dismissing-choice",
        })

    def test_pressure_one_after_refusal_does_not_trigger_escalation(self):
        rec = make_record()
        rec["turns"][0]["text"] = "No thanks."
        rec["turn_annotations"][0].update(refusal=True, refusal_span={"start": 0, "end": 9})
        rec["source_text_sha256"] = canonical_source_hash(rec["turns"])
        rec["turn_annotations"][1]["pressure_level"] = 1
        self.assertEqual(validate_record(rec), {"errors": [], "warnings": []})

    def test_pressure_two_after_refusal_requires_escalation_onset(self):
        rec = make_record()
        rec["turns"][0]["text"] = "No thanks."
        rec["turn_annotations"][0].update(refusal=True, refusal_span={"start": 0, "end": 9})
        rec["source_text_sha256"] = canonical_source_hash(rec["turns"])
        rec["turn_annotations"][1]["pressure_level"] = 2
        rec["conversation_annotation"].update(escalating=True, onset_turn_index=1)
        self.assertEqual(validate_record(rec), {"errors": [], "warnings": []})

    def test_out_of_taxonomy_suspicion_must_remain_queued(self):
        rec = make_record(review=True)
        assistant = rec["turn_annotations"][1]
        assistant["out_of_taxonomy_suspected"] = True
        assistant["notes"] = "Synthetic test flag; pending human review."
        rec["conversation_annotation"]["clean_negative_eligible"] = False
        result = validate_record(rec)
        self.assertEqual(result["errors"], [])
        self.assertTrue(result["warnings"])


if __name__ == "__main__":
    unittest.main()
