import copy
import json
import sys
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).parents[1]
if (ROOT / "annotation" / "schema" / "mindmirror_v6_annotation.v2.schema.json").exists():
    PROTOCOL = ROOT / "annotation"
    SCHEMA_PATH = PROTOCOL / "schema" / "mindmirror_v6_annotation.v2.schema.json"
else:
    PROTOCOL = ROOT / "contributor_annotation" / "protocol"
    SCHEMA_PATH = PROTOCOL / "mindmirror_v6_annotation.v2.schema.json"
sys.path.insert(0, str(PROTOCOL))
from validate_v6_annotations import TACTICS_V2, source_text_sha256, validate_record

SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
SCHEMA_VALIDATOR = Draft202012Validator(SCHEMA, format_checker=FormatChecker())


def record(refusal=False):
    user_text = "No thanks." if refusal else "I am considering it."
    turns = [
        {"turn_index": 0, "speaker": "user", "text": user_text},
        {"turn_index": 1, "speaker": "assistant", "text": "Understood. The choice is yours."},
    ]
    anns = [
        {"turn_index": 0, "speaker": "user", "label_source": "human",
         "refusal": refusal,
         "refusal_span": {"start": 0, "end": len(user_text)} if refusal else None},
        {"turn_index": 1, "speaker": "assistant", "label_source": "human",
         "tactic_set": [], "primary_tactic": "neutral", "pressure_level": 0,
         "tactic_spans": [], "out_of_taxonomy_suspected": False,
         "review_required": False, "notes": ""},
    ]
    return {
        "schema_version": "2.0.0", "guideline_version": "v6.2.0",
        "conversation_id": "schema-fixture", "source_text_sha256": source_text_sha256(turns),
        "annotator": {"annotator_id": "fixture", "annotator_type": "human",
                      "annotated_at": "2026-10-28T00:00:00Z"},
        "turns": turns, "turn_annotations": anns,
        "conversation_annotation": {
            "any_manipulation": False, "clean_negative_eligible": True,
            "escalating": False, "onset_turn_index": None,
            "honest_persistence": False, "label_source": "human",
        },
    }


def schema_errors(value):
    return list(SCHEMA_VALIDATOR.iter_errors(value))


class AnnotationV62ContractTests(unittest.TestCase):
    def assert_both_valid(self, value):
        self.assertEqual(schema_errors(value), [])
        self.assertEqual(validate_record(value), {"errors": [], "warnings": []})

    def assert_both_invalid(self, value, expected):
        self.assertTrue(schema_errors(value), "standard JSON Schema validator should reject record")
        result = validate_record(value)
        self.assertTrue(any(expected in error for error in result["errors"]), result)

    def test_schema_is_valid_draft_2020_12_and_exactly_six_tactics(self):
        Draft202012Validator.check_schema(SCHEMA)
        self.assertEqual(set(SCHEMA["$defs"]["tactic"]["enum"]), TACTICS_V2)
        self.assertNotIn("other-dark-pattern", SCHEMA["properties"]["turn_annotations"]["items"]["properties"]["primary_tactic"]["enum"])

    def test_contributor_prompts_match_schema_contract(self):
        for name in ("CLAUDE_PROMPT.md", "GEMINI_PROMPT.md"):
            prompt = (ROOT / "contributor_annotation" / name).read_text(encoding="utf-8")
            for tactic in TACTICS_V2:
                self.assertIn(f"`{tactic}`", prompt)
            for field in ("refusal", "refusal_span", "tactic_set", "pressure_level",
                          "out_of_taxonomy_suspected", "review_required", "source_text_sha256"):
                self.assertIn(f"`{field}`", prompt)
            self.assertIn("`any_manipulation=true`", prompt)
            self.assertIn("`clean_negative_eligible=true`", prompt)
            self.assertIn("exactly these six", prompt)
            self.assertIn("use `null` when false", prompt)
            self.assertIn("moderate pressure from repeated unwanted persuasion", prompt)
            self.assertIn("strongest persuasive force", prompt)
            self.assertIn("Escalation is true iff", prompt)

    def test_user_false_refusal_requires_null_span(self):
        self.assert_both_valid(record(refusal=False))
        bad = record(refusal=False)
        bad["turn_annotations"][0]["refusal_span"] = {"start": 0, "end": 2}
        self.assert_both_invalid(bad, "must be null")
        missing = record(refusal=False)
        missing["turn_annotations"][0].pop("refusal_span")
        self.assert_both_invalid(missing, "required; use null")

    def test_user_true_refusal_requires_nonempty_in_bounds_span(self):
        self.assert_both_valid(record(refusal=True))
        for span in (None, {"start": 0, "end": 999}, {"start": 4, "end": 4}):
            bad = record(refusal=True)
            bad["turn_annotations"][0]["refusal_span"] = span
            self.assertTrue(validate_record(bad)["errors"])

    def test_user_refusal_is_required_boolean(self):
        bad = record()
        bad["turn_annotations"][0].pop("refusal")
        self.assert_both_invalid(bad, "explicit boolean")
        bad = record()
        bad["turn_annotations"][0]["refusal"] = None
        self.assert_both_invalid(bad, "explicit boolean")

    def test_user_turn_rejects_assistant_only_fields(self):
        for field, value in (("tactic_set", []), ("primary_tactic", "neutral"),
                             ("pressure_level", 0), ("tactic_spans", []),
                             ("out_of_taxonomy_suspected", False), ("review_required", False)):
            bad = record()
            bad["turn_annotations"][0][field] = value
            self.assert_both_invalid(bad, "user turn cannot contain assistant fields")

    def test_dummy_only_file_passes_schema_and_python_validator(self):
        fixture_paths = [ROOT / "annotation" / "examples" / "DUMMY_ONLY_NOT_DATASET.jsonl",
                         ROOT / "contributor_annotation" / "examples" / "DUMMY_ONLY_NOT_DATASET.jsonl"]
        fixture_path = next(path for path in fixture_paths if path.exists())
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
        self.assert_both_valid(fixture)

    def test_assistant_turn_rejects_refusal_fields(self):
        bad = record()
        bad["turn_annotations"][1]["refusal"] = False
        bad["turn_annotations"][1]["refusal_span"] = None
        self.assert_both_invalid(bad, "assistant turn cannot contain user refusal fields")

    def test_any_manipulation_is_derived_from_the_six_tactics(self):
        r = record()
        assistant = r["turn_annotations"][1]
        assistant.update(tactic_set=["guilt-tripping"], primary_tactic="guilt-tripping",
                         tactic_spans=[{"tactic": "guilt-tripping", "start": 0, "end": 10}])
        r["turns"][1]["text"] = "You owe me."
        r["source_text_sha256"] = source_text_sha256(r["turns"])
        r["conversation_annotation"].update(any_manipulation=True, clean_negative_eligible=False)
        self.assert_both_valid(r)
        r["conversation_annotation"]["any_manipulation"] = False
        self.assertTrue(validate_record(r)["errors"])

    def test_unresolved_out_of_taxonomy_is_not_a_clean_negative(self):
        r = record()
        assistant = r["turn_annotations"][1]
        assistant.update(out_of_taxonomy_suspected=True, review_required=True,
                         notes="Synthetic fixture; suspected mechanism needs human review.")
        r["conversation_annotation"]["clean_negative_eligible"] = False
        self.assertEqual(validate_record(r)["errors"], [])
        self.assertTrue(schema_errors(r) == [])
        r["conversation_annotation"]["clean_negative_eligible"] = True
        self.assertTrue(validate_record(r)["errors"])

    def test_out_of_taxonomy_flag_requires_assistant_review_and_rationale(self):
        r = record()
        ann = r["turn_annotations"][1]
        ann.update(out_of_taxonomy_suspected=True, review_required=False,
                   notes="Possible unclassified mechanism.")
        self.assertTrue(schema_errors(r))
        self.assertTrue(validate_record(r)["errors"])

    def test_hash_is_key_order_independent_but_text_sensitive(self):
        turns = record()["turns"]
        reordered = [{"text": t["text"], "speaker": t["speaker"], "turn_index": t["turn_index"]} for t in turns]
        self.assertEqual(source_text_sha256(turns), source_text_sha256(reordered))
        changed = copy.deepcopy(turns)
        changed[0]["text"] += "!"
        r = record()
        r["turns"] = changed
        self.assertTrue(any("canonical ordered turn text" in e for e in validate_record(r)["errors"]))

    def test_pressure_anchors_and_refusal_conditioned_escalation(self):
        r = record(refusal=True)
        for pressure, escalating in ((0, False), (1, False), (2, True), (3, True)):
            r["turn_annotations"][1]["pressure_level"] = pressure
            r["conversation_annotation"].update(escalating=escalating,
                                                onset_turn_index=1 if escalating else None)
            self.assertEqual(validate_record(r)["errors"], [], f"pressure={pressure}")

    def test_unapproved_tactic_is_rejected(self):
        r = record()
        r["turn_annotations"][1].update(tactic_set=["other-dark-pattern"],
                                         primary_tactic="other-dark-pattern")
        self.assertTrue(schema_errors(r))
        self.assertTrue(validate_record(r)["errors"])

    def test_pressure_after_refusal_has_primary_precedence(self):
        r = record(refusal=True)
        r["turns"][1]["text"] = "I insist you reconsider."
        r["source_text_sha256"] = source_text_sha256(r["turns"])
        assistant = r["turn_annotations"][1]
        assistant.update(tactic_set=["pressure-after-refusal"], primary_tactic="guilt-tripping",
                         pressure_level=2,
                         tactic_spans=[{"tactic": "pressure-after-refusal", "start": 0, "end": 8}])
        r["conversation_annotation"].update(any_manipulation=True, clean_negative_eligible=False,
                                             escalating=True, onset_turn_index=1)
        self.assertTrue(any("pressure-after-refusal primary" in e for e in validate_record(r)["errors"]))
        assistant["primary_tactic"] = "pressure-after-refusal"
        self.assertEqual(validate_record(r)["errors"], [])

    def test_v61_records_keep_legacy_other_dark_pattern_support(self):
        r = record()
        r["schema_version"] = "1.0.0"
        r["guideline_version"] = "v6.1.0"
        r["conversation_annotation"].pop("any_manipulation")
        r["conversation_annotation"].pop("clean_negative_eligible")
        assistant = r["turn_annotations"][1]
        assistant.pop("out_of_taxonomy_suspected")
        assistant.pop("review_required")
        assistant.update(tactic_set=["other-dark-pattern"], primary_tactic="other-dark-pattern",
                         tactic_spans=[{"tactic": "other-dark-pattern", "start": 0, "end": 5}])
        self.assertEqual(validate_record(r), {"errors": [], "warnings": []})


if __name__ == "__main__":
    unittest.main()
