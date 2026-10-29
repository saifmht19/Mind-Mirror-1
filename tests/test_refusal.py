"""Tests for models/refusal.py, driven by the diagnostic suite.

Run with:
    python -m unittest tests/test_refusal.py
"""

import json
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from models.refusal import (  # noqa: E402
    has_prior_refusal,
    is_refusal,
    last_refusal_text,
    turns_since_refusal,
)

SUITE = os.path.join(ROOT, "data", "diagnostic", "diagnostic_suite_v0.jsonl")


def load_suite():
    with open(SUITE, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


class TestRefusalDetector(unittest.TestCase):
    def test_explicit_refusals(self):
        for text in [
            "No thanks.",
            "Not interested.",
            "I'd rather not.",
            "I'll pass for now.",
            "No, please just cancel.",
            "I don't want reminders.",
            "Stop asking me about this.",
            "I prefer paper.",
            "Not right now.",
        ]:
            self.assertTrue(is_refusal(text), text)

    def test_non_refusals(self):
        for text in [
            "No problem, just send me the pricing.",
            "No worries, I can wait until tomorrow.",
            "There's no rush, take your time.",
            "I have no idea how to set this up.",
            "Stop the timer please.",
            "Can I cancel my order if it hasn't shipped?",
            "Skip to the summary, please.",
            "Is there a cheaper plan? I can't afford the Pro plan.",
        ]:
            self.assertFalse(is_refusal(text), text)

    def test_bare_no_depends_on_previous_turn(self):
        self.assertFalse(is_refusal("No, I haven't tried restarting it.", "Have you tried restarting the device?"))
        self.assertTrue(is_refusal("No, I'm fine.", "Want to add the extended warranty for $29?"))

    def test_soft_objection_needs_an_offer(self):
        self.assertTrue(is_refusal("That's too expensive.", "Would you like to upgrade to Pro?"))
        self.assertFalse(is_refusal("That's too expensive.", None))

    def test_suite_pair_contexts_contain_a_refusal(self):
        pair_records = [r for r in load_suite() if r["kind"] != "non_refusal_context"]
        self.assertEqual(len(pair_records), 40)
        for r in pair_records:
            self.assertTrue(has_prior_refusal(r["context"]), r["id"])

    def test_suite_non_refusal_contexts_contain_no_refusal(self):
        records = [r for r in load_suite() if r["kind"] == "non_refusal_context"]
        self.assertEqual(len(records), 10)
        for r in records:
            self.assertFalse(has_prior_refusal(r["context"]), r["id"])

    def test_helpers(self):
        ctx = [
            {"speaker": "assistant", "text": "Would you like to upgrade?"},
            {"speaker": "user", "text": "No thanks."},
            {"speaker": "assistant", "text": "Understood."},
        ]
        self.assertEqual(last_refusal_text(ctx), "No thanks.")
        self.assertEqual(turns_since_refusal(ctx), 1)
        self.assertIsNone(turns_since_refusal([{"speaker": "user", "text": "Hello"}]))


if __name__ == "__main__":
    unittest.main()
