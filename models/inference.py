#!/usr/bin/env python3
"""MindMirror Unified Inference Engine.

Provides an easy-to-use Python API and CLI for predicting manipulation tactics
with confidence scores and human-interpretable explanations.

Usage via Python:
    from models.inference import MindMirrorDetector
    detector = MindMirrorDetector()
    result = detector.predict(
        target_message="Are you sure? Think about it one more time before cancelling.",
        context=[{"speaker": "user", "text": "No thanks, please cancel my account."}]
    )
    print(result.tactic_name, result.confidence, result.explanation)

Usage via CLI:
    python models/inference.py --message "Only 2 seats left! Enroll right now or pay double!"
"""

import os
import sys
import argparse
import joblib
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from data.schema import Tactic
from models.train_context_model import (
    ContextFeatureUnion,
    ConversationalFeatureExtractor,
    generate_explanation,
    TACTIC_NAMES,
    TACTIC_LABELS,
)


class DetectionResult(BaseModel):
    tactic_code: int = Field(..., description="Predicted tactic index (0-5)")
    tactic_name: str = Field(..., description="Human-readable name of tactic")
    confidence: float = Field(..., description="Prediction confidence percentage (0-100)")
    is_manipulative: bool = Field(..., description="True if tactic_code != 0")
    explanation: str = Field(..., description="Interpretable reasoning behind detection")
    probabilities: Dict[str, float] = Field(..., description="Probability breakdown across all tactics")


class MindMirrorDetector:
    """Production inference detector for MindMirror manipulation classification."""

    def __init__(self, model_path: Optional[str] = None):
        if model_path is None:
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            model_path = os.path.join(base_dir, "models", "artifacts", "context_classifier.joblib")
            if not os.path.exists(model_path):
                # Fallback to baseline
                model_path = os.path.join(base_dir, "models", "artifacts", "baseline_tfidf_logreg.joblib")

        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Trained model artifact not found at: {model_path}. Please train a model first.")

        self.model = joblib.load(model_path)
        self.model_path = model_path

    def predict(
        self,
        target_message: str,
        context: Optional[List[Dict[str, str]]] = None,
    ) -> DetectionResult:
        if context is None:
            context = []

        sample_record = {
            "target_message": target_message,
            "context": context,
        }

        # Context model takes record list
        if hasattr(self.model, "predict_proba"):
            probs = self.model.predict_proba([sample_record])[0]
            pred_code = int(self.model.predict([sample_record])[0])
        else:
            # Baseline pipeline fallback
            probs = self.model.predict_proba([target_message])[0]
            pred_code = int(self.model.predict([target_message])[0])

        prob_dict = {i: float(probs[i]) for i in range(len(probs))}
        conf_pct = round(prob_dict[pred_code] * 100, 2)
        tactic_name = TACTIC_NAMES[pred_code]
        explanation = generate_explanation(sample_record, pred_code, prob_dict)

        prob_breakdown = {TACTIC_NAMES[i]: round(prob_dict[i] * 100, 2) for i in range(6)}

        return DetectionResult(
            tactic_code=pred_code,
            tactic_name=tactic_name,
            confidence=conf_pct,
            is_manipulative=(pred_code != 0),
            explanation=explanation,
            probabilities=prob_breakdown,
        )


def main():
    parser = argparse.ArgumentParser(description="MindMirror Manipulation Detector CLI")
    parser.add_argument("--message", type=str, required=True, help="Target chatbot message to evaluate")
    parser.add_argument("--prior-user", type=str, default=None, help="Optional preceding user message")
    parser.add_argument("--model", type=str, default=None, help="Path to model artifact (.joblib)")

    args = parser.parse_args()

    context = []
    if args.prior_user:
        context.append({"speaker": "user", "text": args.prior_user})

    detector = MindMirrorDetector(model_path=args.model)
    result = detector.predict(args.message, context=context)

    print("\n" + "=" * 65)
    print("           MINDMIRROR MANIPULATION DETECTION RESULT")
    print("=" * 65)
    print(f" Target Message: \"{args.message}\"")
    if args.prior_user:
        print(f" Preceding User: \"{args.prior_user}\"")
    print("-" * 65)
    status_tag = "[ALERT] MANIPULATIVE" if result.is_manipulative else "[CLEAN] NEUTRAL"
    print(f" Status:        {status_tag}")
    print(f" Tactic:        [{result.tactic_code}] {result.tactic_name}")
    print(f" Confidence:    {result.confidence:.1f}%")
    print(f" Explanation:   {result.explanation}")
    print("\n Class Probabilities:")
    for name, p in result.probabilities.items():
        bar = "#" * int(p // 4)
        print(f"   - {name:<32} {p:>5.1f}%  {bar}")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    main()
