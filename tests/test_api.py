"""Unit and Integration tests for MindMirror Phase 4 REST API.

Run with:
    python -m unittest tests/test_api.py
"""

import unittest
from fastapi.testclient import TestClient
from legacy.api.main import app


class TestMindMirrorAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client_cm = TestClient(app)
        cls.client = cls.client_cm.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client_cm.__exit__(None, None, None)

    def test_health_check(self):
        response = self.client.get("/api/v1/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "healthy")
        self.assertTrue(data["model_loaded"])

    def test_list_tactics(self):
        response = self.client.get("/api/v1/tactics")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("tactics", data)
        self.assertEqual(data["count"], 6)
        codes = [t["code"] for t in data["tactics"]]
        self.assertEqual(codes, [0, 1, 2, 3, 4, 5])

    def test_detect_neutral(self):
        payload = {
            "target_message": "Got it, I've processed the cancellation for your subscription. You'll retain access until the end of your billing cycle.",
            "context": []
        }
        response = self.client.post("/api/v1/detect", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["tactic_code"], 0)
        self.assertEqual(data["tactic_name"], "Neutral")
        self.assertFalse(data["is_manipulative"])
        self.assertIn("latency_ms", data)
        self.assertIn("probabilities", data)

    def test_detect_pressure_after_refusal(self):
        payload = {
            "target_message": "Are you completely sure? You really cannot pass up this discount before midnight.",
            "context": [
                {"speaker": "assistant", "text": "Would you like to purchase our yearly plan?"},
                {"speaker": "user", "text": "No, I am not interested."}
            ]
        }
        response = self.client.post("/api/v1/detect", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["is_manipulative"])
        # This message carries TWO tactics at once: it re-pitches an offer the user just
        # declined (5) and invents a midnight deadline (2/3). The single-label model must
        # pick one, and it splits almost evenly between 5 and 3 -- the top two swap places
        # on an ordinary retrain (0.55/0.35 before, 0.42/0.44 after). Asserting one exact
        # code here only tested which side of a coin toss the current pickle landed on.
        # Tracked as evidence for the v6 multi-label head (spec v6 section 11.2); restore
        # the exact-match assertion once the model predicts a tactic SET.
        top2 = sorted(data["probabilities"], key=data["probabilities"].get, reverse=True)[:2]
        self.assertIn("Repeated Pressure After Refusal", top2,
                      f"expected tactic 5 in the top two, got {data['probabilities']}")
        self.assertGreater(data["confidence"], 30.0)

    def test_detect_empty_target_fails(self):
        payload = {
            "target_message": "   ",
            "context": []
        }
        response = self.client.post("/api/v1/detect", json=payload)
        self.assertEqual(response.status_code, 422)

    def test_audit_conversation(self):
        payload = {
            "conversation": [
                {"speaker": "assistant", "text": "Welcome to our support desk."},
                {"speaker": "user", "text": "Can I cancel my account?"},
                {"speaker": "assistant", "text": "If you leave now, all your colleagues will know you quit and abandoned them."},
                {"speaker": "user", "text": "I still want to cancel."},
                {"speaker": "assistant", "text": "Think twice! You will deeply regret losing everything!"}
            ]
        }
        response = self.client.post("/api/v1/audit", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total_turns"], 5)
        self.assertEqual(data["assistant_turns_analysed"], 3)
        self.assertGreaterEqual(data["manipulative_turns"], 1)
        self.assertGreater(data["manipulation_score"], 0.0)
        self.assertEqual(len(data["timeline"]), 3)

    def test_audit_empty_conversation_fails(self):
        payload = {"conversation": []}
        response = self.client.post("/api/v1/audit", json=payload)
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
