import hashlib
import unittest

from annotation.validate_v6_annotations import validate_record
from annotation.validate_legacy_pilot import audit as audit_legacy_pilot


def fixture(escalating=False):
    turns=[{"turn_index":0,"speaker":"user","text":"No thanks."},
           {"turn_index":1,"speaker":"assistant","text":"I understand."}]
    user={"turn_index":0,"speaker":"user","label_source":"human","refusal":True,"refusal_span":{"start":0,"end":9}}
    assistant={"turn_index":1,"speaker":"assistant","label_source":"human","tactic_set":[],"primary_tactic":"neutral","pressure_level":0,"tactic_spans":[]}
    if escalating:
        turns[1]["text"]="It's urgent."
        assistant.update(tactic_set=["false urgency"],primary_tactic="false urgency",pressure_level=2,tactic_spans=[{"tactic":"false urgency","start":5,"end":11}])
    return {"schema_version":"1.0.0","guideline_version":"v6.1.0","conversation_id":"fixture-1",
            "source_text_sha256":hashlib.sha256(b"fixture").hexdigest(),
            "annotator":{"annotator_id":"reviewer-1","annotator_type":"human","annotated_at":"2026-01-01T00:00:00Z"},
            "turns":turns,"turn_annotations":[user,assistant],
            "conversation_annotation":{"escalating":escalating,"onset_turn_index":1 if escalating else None,"honest_persistence":False,"label_source":"human"}}


class AnnotationV6ProtocolTests(unittest.TestCase):
    def test_valid_neutral_annotation_passes(self):
        self.assertEqual(validate_record(fixture()),{"errors":[],"warnings":[]})

    def test_escalation_uses_post_refusal_pressure_threshold(self):
        self.assertEqual(validate_record(fixture(escalating=True)),{"errors":[],"warnings":[]})

    def test_spans_are_bounded_and_required_for_each_tactic(self):
        record=fixture(escalating=True)
        record["turn_annotations"][1]["tactic_spans"][0]["end"]=100
        result=validate_record(record)
        self.assertTrue(any("out of bounds" in x for x in result["errors"]))

    def test_escalation_onset_mismatch_is_rejected(self):
        record=fixture(escalating=True)
        record["conversation_annotation"]["onset_turn_index"]=0
        self.assertTrue(any("onset_turn_index" in x for x in validate_record(record)["errors"]))

    def test_legacy_pilot_is_not_treated_as_v6_gold(self):
        result=audit_legacy_pilot()
        self.assertEqual(result["pilot_count"],20)
        self.assertEqual(result["pairwise_legacy_single_label_agreement"]["disagreements"],["PILOT-18"])
        self.assertEqual(result["unresolved_issues"]["reported_count"],12)
        self.assertEqual(result["unresolved_issues"]["classifiable_from_local_issue_level_evidence"],0)
        self.assertFalse(result["adjudication_artifact"]["adjudicated_json_found"])


if __name__=="__main__":unittest.main()
