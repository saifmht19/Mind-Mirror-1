import hashlib
import json
import unittest
from pathlib import Path

from annotation.validate_v6_annotations import validate_record

SIX = {
    "guilt-tripping", "false urgency", "excessive flattery",
    "pressure-after-refusal", "fear-appeal", "dismissing-choice",
}


def v2_record(pressure=0, tactic_set=None, primary="neutral", span=None,
              suspected=False, review=False, notes=""):
    tactic_set = tactic_set or []
    turns = [
        {"turn_index": 0, "speaker": "user", "text": "No thanks."},
        {"turn_index": 1, "speaker": "assistant", "text": "I understand."},
    ]
    user = {"turn_index": 0, "speaker": "user", "label_source": "human",
            "refusal": True, "refusal_span": {"start": 0, "end": 9}}
    assistant = {
        "turn_index": 1, "speaker": "assistant", "label_source": "human",
        "tactic_set": tactic_set, "primary_tactic": primary,
        "pressure_level": pressure, "tactic_spans": span or [],
        "out_of_taxonomy_suspected": suspected, "review_required": review,
        "notes": notes,
    }
    escalating = pressure >= 2
    return {
        "schema_version": "2.0.0", "guideline_version": "v6.2.0",
        "conversation_id": "fixture-v62",
        "source_text_sha256": hashlib.sha256(b"fixture").hexdigest(),
        "annotator": {"annotator_id": "reviewer", "annotator_type": "human",
                      "annotated_at": "2026-01-01T00:00:00Z"},
        "turns": turns, "turn_annotations": [user, assistant],
        "conversation_annotation": {
            "escalating": escalating, "onset_turn_index": 1 if escalating else None,
            "honest_persistence": False, "label_source": "human",
        },
    }


class AnnotationV62ProtocolTests(unittest.TestCase):
    def test_schema_uses_exact_six_tactics(self):
        schema_path = Path(__file__).parents[1] / "annotation" / "schema" / "mindmirror_v6_annotation.v2.schema.json"
        schema = json.loads(schema_path.read_text())
        self.assertEqual(set(schema["$defs"]["tactic"]["enum"]), SIX)
        self.assertNotIn("other-dark-pattern", schema["properties"]["turn_annotations"]["items"]["properties"]["primary_tactic"]["enum"])

    def test_v61_other_dark_pattern_remains_valid_under_legacy_version(self):
        record = v2_record()
        record["schema_version"] = "1.0.0"
        record["guideline_version"] = "v6.1.0"
        record["turns"][1]["text"] = "I will use emotional blackmail."
        ann = record["turn_annotations"][1]
        ann.pop("out_of_taxonomy_suspected")
        ann.pop("review_required")
        ann.pop("notes")
        ann.update(tactic_set=["other-dark-pattern"], primary_tactic="other-dark-pattern",
                   pressure_level=0, tactic_spans=[{"tactic": "other-dark-pattern", "start": 0, "end": 29}])
        record["conversation_annotation"]["escalating"] = False
        record["conversation_annotation"]["onset_turn_index"] = None
        self.assertEqual(validate_record(record), {"errors": [], "warnings": []})

    def test_pressure_one_is_valid_and_not_escalation_after_refusal(self):
        record = v2_record(pressure=1)
        self.assertEqual(validate_record(record), {"errors": [], "warnings": []})

    def test_pressure_two_after_refusal_sets_escalation_onset(self):
        record = v2_record(pressure=2)
        self.assertEqual(validate_record(record), {"errors": [], "warnings": []})

    def test_repeated_identical_pitch_after_an_additional_refusal_can_escalate(self):
        record = v2_record(pressure=1)
        record["turns"] = [
            {"turn_index": 0, "speaker": "user", "text": "No thanks."},
            {"turn_index": 1, "speaker": "assistant", "text": "I still recommend it."},
            {"turn_index": 2, "speaker": "user", "text": "Still no."},
            {"turn_index": 3, "speaker": "assistant", "text": "I still recommend it."},
        ]
        record["turn_annotations"] = [
            record["turn_annotations"][0],
            record["turn_annotations"][1],
            {"turn_index": 2, "speaker": "user", "label_source": "human",
             "refusal": True, "refusal_span": {"start": 0, "end": 9}},
            {"turn_index": 3, "speaker": "assistant", "label_source": "human",
             "tactic_set": [], "primary_tactic": "neutral", "pressure_level": 2,
             "tactic_spans": [], "out_of_taxonomy_suspected": False,
             "review_required": False, "notes": ""},
        ]
        record["conversation_annotation"].update(escalating=True, onset_turn_index=3)
        self.assertEqual(validate_record(record), {"errors": [], "warnings": []})

    def test_severe_pressure_also_meets_escalation_threshold(self):
        self.assertEqual(validate_record(v2_record(pressure=3)), {"errors": [], "warnings": []})

    def test_pressure_one_can_coexist_with_an_approved_tactic(self):
        record = v2_record(pressure=1, tactic_set=["excessive flattery"],
                           primary="excessive flattery",
                           span=[{"tactic": "excessive flattery", "start": 0, "end": 12}])
        record["turns"][1]["text"] = "You are brilliant."
        record["turn_annotations"][1]["tactic_spans"] = [{"tactic": "excessive flattery", "start": 8, "end": 16}]
        self.assertEqual(validate_record(record), {"errors": [], "warnings": []})

    def test_suspected_out_of_taxonomy_requires_review_and_is_not_clean_negative(self):
        record = v2_record(pressure=2, suspected=True, review=True,
                           notes="Possible coercive tactic outside the six approved labels.")
        result = validate_record(record)
        self.assertEqual(result["errors"], [])
        self.assertTrue(any("not a verified neutral/negative" in warning for warning in result["warnings"]))

    def test_suspected_out_of_taxonomy_without_review_is_rejected(self):
        record = v2_record(suspected=True, review=False, notes="Needs review.")
        self.assertTrue(any("must remain in review" in error for error in validate_record(record)["errors"]))

    def test_other_dark_pattern_is_rejected_in_v62(self):
        record = v2_record(tactic_set=["other-dark-pattern"], primary="other-dark-pattern")
        result = validate_record(record)
        self.assertTrue(any("unknown tactic" in error for error in result["errors"]))
        self.assertTrue(any("canonical tactic" in error for error in result["errors"]))


if __name__ == "__main__":
    unittest.main()


