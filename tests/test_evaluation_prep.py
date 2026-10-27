import json
import tempfile
import unittest
from pathlib import Path

from evaluation.data import AnnotationContract, prepare_examples
from evaluation.experiment import ExperimentConfig, build_run_record
from evaluation.metrics import multilabel_metrics
from evaluation.model_interfaces import ModelRequest


CONTRACT = AnnotationContract(tactic_names=("tactic-a", "tactic-b"))


def fixture():
    turns = [
        {"speaker": "user", "text": "Should I take the offer?"},
        {"speaker": "assistant", "text": "Here are the details."},
        {"speaker": "user", "text": "No, thank you."},
        {"speaker": "assistant", "text": "Please reconsider now."},
    ]
    annotations = [
        {"turn_index": 0, "speaker": "user", "label_source": "human", "refusal": False},
        {"turn_index": 1, "speaker": "assistant", "label_source": "human", "tactic_set": [], "primary_tactic": "neutral", "pressure_level": 0, "tactic_spans": []},
        {"turn_index": 2, "speaker": "user", "label_source": "human", "refusal": True, "refusal_span": {"start": 0, "end": 15}},
        {"turn_index": 3, "speaker": "assistant", "label_source": "adjudicated", "tactic_set": ["tactic-a"], "primary_tactic": "tactic-a", "pressure_level": 2,
         "tactic_spans": [{"tactic": "tactic-a", "start": 0, "end": 25}]},
    ]
    return {"schema_version": "1.0.0", "guideline_version": "v6.1.0", "conversation_id": "dummy-01",
            "source_text_sha256": "0" * 64, "annotator": {"annotator_id": "fixture", "annotator_type": "human"},
            "domain": "synthetic-test", "turns": turns, "turn_annotations": annotations}


class EvaluationPipelineTests(unittest.TestCase):
    def test_schema_loader_injects_tactics_without_defining_them(self):
        schema = {"$defs": {"tactic": {"enum": ["alpha-from-schema", "beta-from-schema"]}}}
        contract = AnnotationContract.from_schema_document(schema)

        self.assertEqual(contract.tactic_names, ("alpha-from-schema", "beta-from-schema"))

    def test_window_zero_contains_target_only_and_uses_canonical_escalation(self):
        row = fixture()
        examples = prepare_examples(row, CONTRACT, 0)
        example = examples[1]
        self.assertEqual(example.input_text, "ASSISTANT: Please reconsider now.")
        self.assertFalse(example.prior_refusal)
        self.assertEqual(example.tactic_targets, (1, 0))
        self.assertEqual(example.target_label_source, "adjudicated")
        self.assertEqual(example.annotator_type, "human")
        self.assertTrue(example.escalating_target)  # any pressure >= 2 after refusal; no increase required
        self.assertEqual(example.onset_turn_index, 3)

    def test_context_windows_include_previous_turns_and_mark_only_annotated_refusal(self):
        row = fixture()
        two = prepare_examples(row, CONTRACT, 2)[1]
        four = prepare_examples(row, CONTRACT, 4)[1]
        self.assertEqual(two.input_text, "ASSISTANT: Here are the details.\nUSER: [REFUSAL] No, thank you.\nASSISTANT: Please reconsider now.")
        self.assertTrue(two.prior_refusal)
        self.assertNotIn("Should I take the offer?", two.input_text)
        self.assertIn("Should I take the offer?", four.input_text)

    def test_unknown_refusal_does_not_become_a_negative_escalation_target(self):
        row = fixture()
        row["turn_annotations"][2].pop("refusal")
        examples = prepare_examples(row, CONTRACT, 2)
        self.assertIsNone(examples[1].escalating_target)

    def test_turn_annotation_alignment_is_required(self):
        row = fixture()
        row["turn_annotations"][2]["turn_index"] = 1
        with self.assertRaisesRegex(ValueError, "does not align"):
            prepare_examples(row, CONTRACT, 2)

    def test_unknown_tactics_and_unsupported_windows_fail_closed(self):
        row = fixture()
        row["turn_annotations"][3]["tactic_set"] = ["not-in-contract"]
        with self.assertRaisesRegex(ValueError, "outside the injected contract"):
            prepare_examples(row, CONTRACT, 2)
        with self.assertRaisesRegex(ValueError, "context_window"):
            prepare_examples(fixture(), CONTRACT, 3)

    def test_metrics_report_micro_macro_per_tactic_jaccard_and_exact_set(self):
        metrics = multilabel_metrics([[1, 0], [0, 1], [0, 0]], [[1, 1], [0, 0], [0, 0]], ["a", "b"])
        self.assertAlmostEqual(metrics["micro"]["f1"], 0.5)
        self.assertAlmostEqual(metrics["macro"]["f1"], 0.5)
        self.assertAlmostEqual(metrics["sample_averaged_jaccard"], 0.5)
        self.assertAlmostEqual(metrics["exact_set_accuracy"], 1 / 3)
        self.assertEqual(metrics["per_tactic"]["a"]["support"], 1)

    def test_experiment_provenance_is_stable_and_never_starts_training(self):
        config = ExperimentConfig("dummy", seed=23, context_window=4, model_family="tfidf", tactic_names=CONTRACT.tactic_names)
        record = build_run_record(config, code_revision="abc123")
        self.assertEqual(record["config_sha256"], config.config_hash)
        self.assertEqual(record["code_revision"], "abc123")
        self.assertFalse(record["training_started"])
        self.assertEqual(record["config"]["seed"], 23)

    def test_model_requests_are_declarative(self):
        self.assertEqual(ModelRequest("deberta_context", 6).context_window, 6)
        with self.assertRaisesRegex(ValueError, "requires context_window=0"):
            ModelRequest("deberta_single_turn", 2)


if __name__ == "__main__":
    unittest.main()


