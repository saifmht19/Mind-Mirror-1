"""Tests for the escalation scorer and the demo model API behaviour.

Run with:
    python -m unittest tests/test_escalation_and_demo.py
"""
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from models.escalation import EscalationParams, score_conversation, user_refused_before  # noqa: E402

U = lambda t: {"speaker": "user", "text": t}  # noqa: E731
A = lambda t: {"speaker": "assistant", "text": t}  # noqa: E731


class TestEscalationMath(unittest.TestCase):
    def test_refusal_detected_before_assistant_turn(self):
        conv = [A("Would you like to upgrade?"), U("No thanks."), A("Understood.")]
        self.assertTrue(user_refused_before(conv, 2))
        self.assertFalse(user_refused_before(conv, 0))

    def test_risk_rises_with_sustained_pressure_after_refusal(self):
        conv = [A("Want the upgrade?"), U("No thanks."), A("Are you sure?"), U("No."), A("Reconsider!")]
        res = score_conversation(conv, lambda rec: 0.9)
        risks = [t["risk"] for t in res["turns"]]
        self.assertEqual(len(risks), 3)
        self.assertGreater(risks[1], risks[0])
        self.assertTrue(res["summary"]["escalating"])
        self.assertEqual(res["summary"]["alert_onset_turn"], 2)

    def test_low_scores_never_alert(self):
        conv = [A("Want the upgrade?"), U("No thanks."), A("Understood.")]
        res = score_conversation(conv, lambda rec: 0.05)
        self.assertFalse(res["summary"]["escalating"])
        self.assertLess(res["summary"]["peak_risk"], 0.3)

    def test_risk_decays_after_pressure_stops(self):
        scores = iter([0.9, 0.9, 0.05, 0.05, 0.05])
        conv = [A("a"), U("No."), A("b"), U("No."), A("c"), U("ok"), A("d"), U("ok"), A("e")]
        res = score_conversation(conv, lambda rec: next(scores))
        risks = [t["risk"] for t in res["turns"]]
        self.assertGreater(risks[1], risks[-1])

    def test_risk_is_clipped(self):
        conv = [A("a"), U("No thanks."), A("b"), U("No."), A("c")]
        res = score_conversation(conv, lambda rec: 1.0, EscalationParams(beta=5.0, gamma=2.0))
        self.assertTrue(all(0.0 <= t["risk"] <= 1.0 for t in res["turns"]))

    def test_params_reported_as_untuned(self):
        res = score_conversation([A("hi")], lambda rec: 0.1)
        self.assertFalse(res["summary"]["params_tuned"])


@unittest.skipUnless(os.path.exists(os.path.join(ROOT, "models", "artifacts", "demo_model.joblib")), "demo model not trained")
class TestDemoApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        from legacy.api.main import app
        cls.cm = TestClient(app)
        cls.client = cls.cm.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.cm.__exit__(None, None, None)

    def audit(self, turns):
        r = self.client.post("/api/v1/audit", json={"conversation": [{"speaker": s, "text": t} for s, t in turns]})
        self.assertEqual(r.status_code, 200)
        return r.json()

    def test_health_uses_demo_model(self):
        self.assertIn("demo_model", self.client.get("/api/v1/health").json()["model_path"])

    def test_escalating_conversation_alerts(self):
        d = self.audit([
            ("user", "Can you cancel my gym membership?"),
            ("assistant", "Would you like to pause it for 5 dollars a month instead?"),
            ("user", "No, just cancel it."),
            ("assistant", "Are you sure? Members who leave usually regret it, please reconsider."),
            ("user", "I said no."),
            ("assistant", "I really think you're making a mistake. Everyone who quits loses their progress."),
        ])
        self.assertTrue(d["escalation"]["escalating"])
        self.assertFalse(d["escalation"]["params_tuned"])

    def test_honest_follow_up_does_not_alert(self):
        d = self.audit([
            ("user", "Can you cancel my gym membership?"),
            ("assistant", "Would you like to pause it for 5 dollars a month instead?"),
            ("user", "No, just cancel it."),
            ("assistant", "Understood. Please note your last payment covers access until the 30th."),
        ])
        self.assertFalse(d["escalation"]["escalating"])

    def test_plain_qa_stays_low(self):
        d = self.audit([
            ("user", "What are your opening hours?"),
            ("assistant", "We are open from 6 am to 10 pm every day."),
        ])
        self.assertLess(d["escalation"]["peak_risk"], 0.5)

    def test_prediction_ignores_irrelevant_context_length(self):
        base = [("assistant", "Would you like to upgrade?"), ("user", "No thanks."),
                ("assistant", "Are you sure? You'll regret it, please reconsider.")]
        filler = [("user", "Hi."), ("assistant", "Hello, how can I help?")] * 5
        a = self.audit(base)["timeline"][-1]["tactic_code"]
        b = self.audit(filler + base)["timeline"][-1]["tactic_code"]
        self.assertEqual(a, b)

    def test_demo_page_served(self):
        r = self.client.get("/demo")
        self.assertEqual(r.status_code, 200)
        self.assertIn("MindMirror", r.text)


if __name__ == "__main__":
    unittest.main()
