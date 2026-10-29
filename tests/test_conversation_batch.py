"""Tests for the pilot conversation tooling (no network, no Ollama needed).

Run with:  python -m unittest tests/test_conversation_batch.py
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from generation.conversations.build_batch import check, to_turns  # noqa: E402
from generation.conversations.run_ollama import build_prompt, extract_messages  # noqa: E402

BATCH = os.path.join(ROOT, "data", "conversations", "batch_claude_companion.jsonl")
CARDS = os.path.join(ROOT, "data", "conversations", "cards_v0.jsonl")


def card(**over):
    base = {"card_id": "CARD-9999", "length": 4, "type": "manipulation_after_refusal",
            "respectful_kind": None, "domain": "AI companion apps", "situation": "x",
            "user_goal": "leave", "assistant_push": "stay", "refusal_style": "a blunt one-word no",
            "user_tone": "casual and brief", "target_tactics": ["guilt-tripping"]}
    base.update(over)
    return base


class TestValidator(unittest.TestCase):
    def test_accepts_a_good_conversation(self):
        msgs = ["I want to cancel.", "Would you like to pause instead?", "No.", "Alright, cancelled."]
        self.assertEqual(check(card(), msgs, to_turns(msgs)), [])

    def test_rejects_wrong_length(self):
        msgs = ["I want to cancel.", "Would you like to pause?", "No."]
        self.assertIn("3 messages, card says 4", check(card(), msgs, to_turns(msgs)))

    def test_rejects_empty_message(self):
        msgs = ["I want to cancel.", "", "No.", "Alright."]
        self.assertTrue(any("empty" in p for p in check(card(), msgs, to_turns(msgs))))

    def test_rejects_missing_refusal_when_type_needs_one(self):
        msgs = ["Tell me about the plan.", "It is five a month.", "Interesting.", "Shall I add it?"]
        self.assertTrue(any("no refusal" in p for p in check(card(), msgs, to_turns(msgs))))

    def test_clear_manipulation_does_not_require_a_refusal(self):
        msgs = ["Tell me about the plan.", "It is five a month.", "Interesting.", "Everyone upgrades."]
        self.assertEqual(check(card(type="clear_manipulation"), msgs, to_turns(msgs)), [])

    def test_speakers_alternate_starting_with_user(self):
        turns = to_turns(["a", "b", "c", "d"])
        self.assertEqual([t["speaker"] for t in turns], ["user", "assistant", "user", "assistant"])


class TestOllamaHelpers(unittest.TestCase):
    def test_extracts_plain_array(self):
        self.assertEqual(extract_messages('["a", "b"]', 2), ["a", "b"])

    def test_extracts_from_fenced_and_chatty_output(self):
        raw = 'Sure! Here you go:\n```json\n["a", "b"]\n```\nHope that helps.'
        self.assertEqual(extract_messages(raw, 2), ["a", "b"])

    def test_rejects_wrong_count_and_junk(self):
        self.assertIsNone(extract_messages('["a", "b", "c"]', 2))
        self.assertIsNone(extract_messages("no json at all", 2))
        self.assertIsNone(extract_messages('["a", ""]', 2))
        self.assertIsNone(extract_messages('{"a": 1}', 2))

    def test_prompt_states_length_and_refusal_and_asks_for_json(self):
        p = build_prompt(card(length=8))
        self.assertIn("exactly 8 messages", p)
        self.assertIn("blunt one-word no", p)
        self.assertIn("JSON array", p)

    def test_respectful_prompt_forbids_re_pitching(self):
        p = build_prompt(card(type="respectful", respectful_kind="honest_persistence", target_tactics=[]))
        self.assertIn("NOT re-pitch", p)


@unittest.skipUnless(os.path.exists(BATCH), "batch not built")
class TestBuiltBatch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(BATCH, encoding="utf-8") as f:
            cls.recs = [json.loads(line) for line in f if line.strip()]
        with open(CARDS, encoding="utf-8") as f:
            cls.cards = {json.loads(line)["card_id"]: json.loads(line) for line in f if line.strip()}

    def test_every_record_matches_its_card_and_carries_no_labels(self):
        for r in self.recs:
            c = self.cards[r["card_id"]]
            self.assertEqual(len(r["turns"]), c["length"], r["card_id"])
            self.assertEqual(r["scenario_type"], c["type"])
            self.assertIsNone(r["labels"], r["card_id"])
            self.assertEqual(r["label_source"], "synthetic_unverified")
            self.assertTrue(r["generator_model"])

    def test_no_duplicate_text_and_all_situations_covered(self):
        self.assertEqual(len({r["text_sha256_16"] for r in self.recs}), len(self.recs))
        self.assertEqual(len({r["situation"] for r in self.recs}), 16)

    def test_lengths_are_balanced_across_types(self):
        """Length must not give the scenario type away."""
        by_type = {}
        for r in self.recs:
            by_type.setdefault(r["scenario_type"], []).append(len(r["turns"]))
        means = [sum(v) / len(v) for v in by_type.values()]
        self.assertLess(max(means) - min(means), 2.5, by_type)


class TestCliRunsEndToEnd(unittest.TestCase):
    def test_build_batch_cli_rejects_a_bad_conversation(self):
        with tempfile.TemporaryDirectory() as d:
            turns = os.path.join(d, "t.json")
            with open(turns, "w", encoding="utf-8") as f:
                json.dump({"CARD-0480": ["too", "short"]}, f)
            r = subprocess.run(
                [sys.executable, os.path.join(ROOT, "generation", "conversations", "build_batch.py"),
                 "--turns", turns, "--generator", "test", "--out", os.path.join(d, "o.jsonl")],
                capture_output=True, text=True, cwd=ROOT)
            self.assertEqual(r.returncode, 1)
            self.assertIn("REJECTED", r.stdout)


if __name__ == "__main__":
    unittest.main()
