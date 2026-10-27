import unittest

from evaluation.data import AnnotationContract, prepare_examples
from evaluation.experiment import ExperimentConfig, build_run_record
from evaluation.metrics import multilabel_metrics
from evaluation.model_interfaces import ModelRequest


CONTRACT = AnnotationContract(tactic_names=("tactic-a", "tactic-b"))


def fixture():
    return {
        "conversation_id": "dummy-01", "domain": "synthetic-test",
        "turns": [
            {"speaker": "user", "text": "Should I take the offer?", "user_refusal": {"refusal": False}},
            {"speaker": "assistant", "text": "Here are the details."},
            {"speaker": "user", "text": "No, thank you.", "user_refusal": {"refusal": True}},
            {"speaker": "assistant", "text": "Please reconsider now.", "assistant_annotation": {
                "tactic_set": ["tactic-a"], "primary_tactic": "tactic-a", "pressure_level_0_3": 2}},
        ],
    }


class EvaluationPipelineTests(unittest.TestCase):
    def test_window_zero_contains_target_only_and_has_no_prior_refusal_marker(self):
        example = prepare_examples(fixture(), CONTRACT, 0)[1]
        self.assertEqual(example.input_text, "ASSISTANT: Please reconsider now.")
        self.assertFalse(example.prior_refusal)
        self.assertEqual(example.tactic_targets, (1, 0))
        self.assertTrue(example.escalating_target)
        self.assertEqual(example.onset_turn_index, 3)

    def test_context_windows_include_only_previous_turns_and_mark_annotated_refusal(self):
        zero = prepare_examples(fixture(), CONTRACT, 0)[1]
        two = prepare_examples(fixture(), CONTRACT, 2)[1]
        four = prepare_examples(fixture(), CONTRACT, 4)[1]
        self.assertEqual(two.input_text, "ASSISTANT: Here are the details.\nUSER: [REFUSAL] No, thank you.\nASSISTANT: Please reconsider now.")
        self.assertTrue(two.prior_refusal)
        self.assertNotIn("Should I take the offer?", two.input_text)
        self.assertIn("Should I take the offer?", four.input_text)
        self.assertFalse(zero.prior_refusal)

    def test_unannotated_refusal_does_not_become_a_negative_escalation_target(self):
        row = fixture()
        row["turns"][2].pop("user_refusal")
        examples = prepare_examples(row, CONTRACT, 2)
        self.assertIsNone(examples[1].escalating_target)  # pressure is high, but refusal evidence is missing

    def test_unknown_tactics_and_unsupported_windows_fail_closed(self):
        row = fixture()
        row["turns"][3]["assistant_annotation"]["tactic_set"] = ["not-in-contract"]
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
