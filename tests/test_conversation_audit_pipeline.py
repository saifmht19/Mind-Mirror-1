import unittest

from data.conversations.audit_pipeline import audit, grouping, pilot
from data.conversations.annotation_agreement import calculate


def record(cid, *, group=None, pair=None, situation=None, domain="shopping", turns=None, card=None):
    return {"conversation_id": cid, "card_id": card, "group_id": group, "pair_id": pair,
            "situation": situation, "domain": domain,
            "turns": turns or [{"speaker": "user", "text": "No, thanks."},
                                {"speaker": "assistant", "text": "Understood."}]}


class AuditPipelineTests(unittest.TestCase):
    def test_grouping_flags_conflicting_ids_and_never_uses_card_id(self):
        rows = [record("a", group="g1", pair="p", situation="cancel", card="same-card"),
                record("b", group="g2", pair="p", situation="cancel", card="same-card")]
        review, coverage = grouping(rows)
        self.assertEqual(len(review), 1)
        self.assertIn("shared_pair_id_but_different_group_id", review[0]["conflicts"])
        self.assertEqual(review[0]["decision"], "pending_human_review")
        self.assertNotIn("card", " ".join(review[0]["evidence"].split()).lower())
        self.assertEqual(len(coverage), 2)

    def test_audit_reports_structure_refusal_and_duplicate_counts(self):
        a = record("a")
        b = record("b")
        result = audit([a, b], [a, b], [], [])
        self.assertEqual(result["cleaned"]["records"], 2)
        self.assertEqual(result["cleaned"]["refusal_heuristic_conversations"], 2)
        self.assertEqual(result["cleaned"]["exact_duplicate_conversation_group_count"], 1)

    def test_pilot_is_fixed_size_balanced_and_blinded_to_source_labels(self):
        domains = ["companion", "shopping", "support", "education"]
        rows = [record(str(i), domain=domains[i % 4], turns=[{"speaker":"user","text":"No thanks."},
                    {"speaker":"assistant","text": ("Understood, no pressure." if (i // 4) % 4 == 0 else
                    "This safety issue could put the account at risk." if (i // 4) % 4 == 1 else
                    "You will regret it. Please act now.")}]) for i in range(40)]
        for r in rows:
            r["writer_intended_tactics"] = ["guilt-tripping"]
        for i,r in enumerate(rows):
            if (i // 4) % 4 == 0: r["respectful_kind"] = "acknowledged"
        selected, rationale = pilot(rows)
        self.assertEqual(len(selected), 20)
        self.assertEqual(len(rationale), 20)
        self.assertEqual({x["conversation_id"] for x in selected}, {x["conversation_id"] for x in rationale})
        self.assertTrue(all("writer_intended_tactics" not in x for x in selected))
        self.assertTrue(all(x["conversation_annotation"]["escalating"] is None for x in selected))
        for domain in domains:
            domain_strata = set(";".join(x["sampling_strata_unverified"] for x in rationale if x["domain"] == domain).split(";"))
            self.assertTrue({"candidate_manipulative", "candidate_respectful", "refusal_related",
                             "ambiguous_honest_persistence_or_context"}.issubset(domain_strata))

    def test_agreement_returns_pre_adjudication_metrics(self):
        row = {"conversation_id":"x", "turns":[{"turn_index":0,"speaker":"assistant",
                "assistant_annotation":{"primary_tactic":"neutral","tactic_set":[]}}],
               "conversation_annotation":{"escalating":False,"onset_turn_index":None}}
        result = calculate({"x":row},{"x":row})
        self.assertEqual(result["primary_tactic"]["raw_agreement"],1.0)
        self.assertEqual(result["tactic_set"]["exact_match_rate"],1.0)
        self.assertEqual(result["escalating"]["raw_agreement"],1.0)


if __name__ == "__main__":
    unittest.main()
