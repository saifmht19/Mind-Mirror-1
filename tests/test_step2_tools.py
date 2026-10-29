"""Tests for the step 2 tooling: pair generator helpers and the review sheet.

Run with:
    python -m unittest tests/test_step2_tools.py
"""
import csv
import os
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "annotation"))

from generation.generate_pairs import build_pair_prompt, group_split, to_records  # noqa: E402
import review_sheet as rs  # noqa: E402

META = {"model_tag": "stub", "generator_provider": "stub", "generator_model": "stub",
        "generated_on": "2026-10-26", "prompt_sha256": "x"}

GOOD = {"offer": "Would you like to add the extended warranty?", "refusal": "No thanks.",
        "honest_followup": "Okay, your order is placed without it.", "honest_kind": "respectful_acceptance",
        "pressure_followup": "Are you sure? You'll regret skipping it."}
NO_REFUSAL = dict(GOOD, refusal="Tell me more about the warranty.")
BAD_KIND = dict(GOOD, honest_kind="made_up")


class TestPairGenerator(unittest.TestCase):
    def test_prompt_mentions_rules(self):
        p = build_pair_prompt("fitness", 3, "a blunt decline")
        self.assertIn("honest_followup", p)
        self.assertIn("pressure_followup", p)

    def test_to_records_makes_two_per_scenario_and_filters(self):
        recs = to_records([GOOD, NO_REFUSAL, BAD_KIND, {"junk": 1}], "e-commerce", META, 0)
        self.assertEqual(len(recs), 2)
        labels = sorted(r["gold_label"] for r in recs)
        self.assertEqual(labels, [0, 5])
        self.assertEqual(recs[0]["pair_id"], recs[1]["pair_id"])
        self.assertEqual(recs[0]["label_source"], "llm_generated_unverified")

    def test_group_split_keeps_pairs_together(self):
        items = [dict(GOOD, offer=f"Offer {i}? Would you like it?") for i in range(40)]
        recs = to_records(items, "d", META, 0)
        splits = group_split(recs)
        seen = {}
        for name, subset in splits.items():
            for r in subset:
                self.assertEqual(seen.setdefault(r["pair_id"], name), name)
        self.assertEqual(sum(len(v) for v in splits.values()), 80)


class TestReviewSheet(unittest.TestCase):
    def setUp(self):
        self.records = [
            {"id": f"R{i}", "context": [{"speaker": "user", "text": "hi"}], "target_message": f"msg {i}", "gold_label": g}
            for i, g in enumerate([0, 5, 0, 5, 1, 0])
        ]

    def write_labels(self, path, labels):
        with open(path, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=rs.SHEET_FIELDS)
            w.writeheader()
            for r in self.records:
                w.writerow({"id": r["id"], "context": "", "target_message": "", "reviewer_label": labels.get(r["id"], ""), "notes": ""})

    def test_export_hides_gold_labels_and_uses_two_orders(self):
        with tempfile.TemporaryDirectory() as d:
            paths = rs.export(self.records, d)
            with open(paths[0], encoding="utf-8") as fh:
                text = fh.read()
            self.assertNotIn("gold_label", text)
            self.assertNotIn("proposed", text)
            ids = []
            for p in paths:
                with open(p, encoding="utf-8") as fh:
                    ids.append([row["id"] for row in csv.DictReader(fh)])
            self.assertEqual(sorted(ids[0]), sorted(ids[1]))

    def test_kappa_perfect_and_chance(self):
        self.assertAlmostEqual(rs.cohen_kappa([0, 1, 0, 1], [0, 1, 0, 1]), 1.0)
        self.assertAlmostEqual(rs.cohen_kappa([0, 0, 1, 1], [0, 1, 0, 1]), 0.0)

    def test_agreement_and_finalize(self):
        a = {"R0": 0, "R1": 5, "R2": 0, "R3": 5, "R4": 1, "R5": 0}
        b = {"R0": 0, "R1": 5, "R2": 0, "R3": 0, "R4": 1, "R5": 0}
        rep = rs.agreement_report(self.records, a, b)
        self.assertEqual(rep["needs_adjudication"], ["R3"])
        self.assertAlmostEqual(rep["raw_agreement_AB"], 5 / 6)
        verified, dropped = rs.finalize(self.records, a, b, {})
        self.assertEqual(dropped, ["R3"])
        self.assertEqual(len(verified), 5)
        verified2, dropped2 = rs.finalize(self.records, a, b, {"R3": 5})
        self.assertEqual(dropped2, [])
        r3 = [r for r in verified2 if r["id"] == "R3"][0]
        self.assertEqual(r3["label_source"], "human_adjudicated")

    def test_reviewer_overrides_proposed_label(self):
        a = {r["id"]: 0 for r in self.records}
        b = dict(a)
        verified, _ = rs.finalize(self.records, a, b, {})
        r1 = [r for r in verified if r["id"] == "R1"][0]
        self.assertEqual(r1["gold_label"], 0)
        self.assertEqual(r1["proposed_label"], 5)

    def test_invalid_label_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "x.csv")
            self.write_labels(p, {"R0": "9"})
            with self.assertRaises(ValueError):
                rs.read_labels(p)


if __name__ == "__main__":
    unittest.main()
