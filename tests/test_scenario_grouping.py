import unittest
from data.conversations.scenario_grouping import assign_group_splits, build_proposals, find_split_leakage


def rec(cid, **kw):
    r={"conversation_id":cid,"domain":"shop","group_id":None,"pair_id":None,"situation":None,
       "card_id":"same-card-ignored","writer_intended_tactics":["guilt-tripping"],
       "turns":[{"speaker":"user","text":"No"},{"speaker":"assistant","text":"Okay"}]}
    r.update(kw);return r


class GroupingTests(unittest.TestCase):
    def test_tf_idf_only_is_reviewed_never_merged_into_proposal_group(self):
        rows=[rec("a"),rec("b")]
        edges,groups,coverage=build_proposals(rows,[{"conversation_1":"a","conversation_2":"b","similarity":"0.99"}])
        self.assertEqual(len(edges),1);self.assertEqual(edges[0]["decision"],"pending_human_review")
        self.assertEqual(groups,[]);self.assertNotIn("card_id",str(edges[0]));self.assertEqual(len(coverage),2)

    def test_corroborated_metadata_proposes_unconfirmed_group(self):
        rows=[rec("a",group_id="g",pair_id="p",situation="cancel"),
              rec("b",group_id="g",pair_id="p",situation="cancel")]
        edges,groups,_=build_proposals(rows,[])
        self.assertEqual(len(edges),1);self.assertEqual(len(groups),2)
        self.assertEqual({x["status"] for x in groups},{"unconfirmed_human_review_required"})

    def test_pair_id_situation_conflict_is_flagged_and_not_grouped(self):
        rows=[rec("a",pair_id="p",situation="cancel"),rec("b",pair_id="p",situation="upgrade")]
        edges,groups,_=build_proposals(rows,[])
        self.assertIn("shared_id_different_situation",edges[0]["conflicts"])
        self.assertEqual(groups,[])

    def test_deterministic_verified_group_split_keeps_group_together(self):
        rows=[{"conversation_id":"a","verified_scenario_id":"scenario-1"},
              {"conversation_id":"b","verified_scenario_id":"scenario-1"},
              {"conversation_id":"c","verified_scenario_id":"scenario-2"},
              {"conversation_id":"d"}]
        first=assign_group_splits(rows,seed="fixed");second=assign_group_splits(rows,seed="fixed")
        self.assertEqual(first,second);self.assertEqual(first["a"],first["b"])
        self.assertEqual(first["d"],"unassigned")

    def test_leakage_checker_detects_split_crossing(self):
        rows=[{"conversation_id":"a","verified_scenario_id":"same"},
              {"conversation_id":"b","verified_scenario_id":"same"}]
        self.assertEqual(find_split_leakage(rows,{"a":"train","b":"test"}),{"same":["test","train"]})
    def test_invalid_ratios_rejected(self):
        with self.assertRaises(ValueError): assign_group_splits([],ratios=(.7,.2,.2))


if __name__=="__main__": unittest.main()

