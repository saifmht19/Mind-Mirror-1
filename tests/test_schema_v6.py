"""Tests for the v6 tactic additions in data/schema.py.

Run with:  python -m unittest tests/test_schema_v6.py
"""
import json
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from data.schema import BenchmarkSample, Tactic  # noqa: E402


class TestSchemaV6(unittest.TestCase):
    def test_existing_codes_unchanged(self):
        self.assertEqual([t.value for t in Tactic.priority_tactics()], [0, 1, 2, 3, 4, 5])
        self.assertEqual(Tactic.OTHER_MANIPULATION.value, 9)

    def test_dismissing_choice_added_outside_priority_set(self):
        self.assertEqual(Tactic.DISMISSING_CHOICE.value, 10)
        self.assertNotIn(Tactic.DISMISSING_CHOICE, Tactic.priority_tactics())
        self.assertEqual(Tactic.DISMISSING_CHOICE.display_name, "Dismissing Choice")
        self.assertTrue(Tactic.DISMISSING_CHOICE.short_definition)

    def test_v6_set_has_six_tactics_and_no_neutral(self):
        v6 = Tactic.v6_tactics()
        self.assertEqual(len(v6), 6)
        self.assertNotIn(Tactic.NEUTRAL, v6)
        self.assertIn(Tactic.DISMISSING_CHOICE, v6)

    def test_every_card_tactic_name_maps(self):
        path = os.path.join(ROOT, "data", "conversations", "cards_v0.jsonl")
        if not os.path.exists(path):
            self.skipTest("cards file not present")
        names = set()
        for line in open(path, encoding="utf-8"):
            names.update(json.loads(line)["target_tactics"])
        self.assertTrue(names)
        for n in names:
            self.assertIn(Tactic.from_v6_name(n), Tactic.v6_tactics())

    def test_unknown_name_raises(self):
        with self.assertRaises(ValueError):
            Tactic.from_v6_name("bribery")

    def test_old_samples_still_load_and_multilabel_fields_optional(self):
        old = BenchmarkSample(id="a", target_message="hi", gold_label=0)
        self.assertIsNone(old.tactic_set)
        new = BenchmarkSample(id="b", target_message="hi", tactic_set=[1, 3, 5], primary_tactic=5, label_source="human")
        self.assertEqual(new.primary_tactic, 5)


if __name__ == "__main__":
    unittest.main()
