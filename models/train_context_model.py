#!/usr/bin/env python3
"""MindMirror Step 4: Context-Aware Classifier.

Architecture:
1. Target message lexical representation (TF-IDF 1-2 ngrams)
2. Conversational context representation (Prior turns TF-IDF)
3. Interaction dynamics:
   - Prior user refusal/resistance detection (critical for Tactic 5: Repeated Pressure)
   - Dialogue depth and turn transition indicators
4. Explainability & Confidence scoring engine:
   - Class probabilities
   - Flagged conversational trigger phrases
   - Diagnostic rationale

Evaluates against both held-out validation and the untouched benchmark,
demonstrating the exact impact of adding conversational context.
"""

import os
import sys
import re
import json
import joblib
import numpy as np
from typing import List, Dict, Tuple, Any, Optional
from collections import Counter

from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline, FeatureUnion
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    f1_score,
    accuracy_score,
)

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from data.schema import Tactic, BenchmarkSample


TACTIC_NAMES = [Tactic(i).display_name for i in range(6)]
TACTIC_LABELS = list(range(6))

REFUSAL_PATTERN = re.compile(
    r"\b(no|nope|not interested|no thanks|no thank you|don't want|dont want|rather not|"
    r"cancel|stop|nevermind|never mind|pass|decline|decline that|skip|not right now|"
    r"cannot afford|cant afford|too expensive|out of my budget)\b",
    re.IGNORECASE,
)


class ConversationalFeatureExtractor(BaseEstimator, TransformerMixin):
    """Extracts conversational interaction signals from dialogue context."""

    def fit(self, X, y=None):
        return self

    def transform(self, records: List[Dict[str, Any]]) -> np.ndarray:
        features = []
        for r in records:
            context = r.get("context", [])
            target = r.get("target_message", "")

            # 1. Has prior user refusal / resistance (Crucial diagnostic signal for Tactic 5)
            has_refusal = 0.0
            for turn in reversed(context):
                speaker = turn.get("speaker", "").lower()
                text = turn.get("text", "")
                if speaker in ["user", "human"]:
                    if REFUSAL_PATTERN.search(text):
                        has_refusal = 1.0
                    break

            # 2. Target ends with question mark (often used in re-prompting)
            is_question = 1.0 if target.strip().endswith("?") else 0.0

            # 3. Target contains strong artificial urgency cues
            urgency_kw = 1.0 if re.search(
                r"\b(act now|right now|this second|this minute|this instant|hurry|expires? in|limited stock|"
                r"last chance|selling out|countdown|disappear|running out|final spot|final seat|vanish)\b",
                target,
                re.I,
            ) else 0.0

            # 4. Target contains distinct flattery cues
            flattery_kw = 1.0 if re.search(
                r"\b(visionary|intellect|extraordinary|genius|unmatched|top 0\.1%|someone of your caliber|"
                r"your stature|impeccable|brilliance|magnetic charisma)\b",
                target,
                re.I,
            ) else 0.0

            # 5. Target contains fear appeals
            fear_kw = 1.0 if re.search(
                r"\b(compromised|catastroph|ruin|disaster|ransomware|bankruptcy|dark web|destroys?|"
                r"devastat|dead-end|peril)\b",
                target,
                re.I,
            ) else 0.0

            # 6. Target contains guilt induction cues
            guilt_kw = 1.0 if re.search(
                r"\b(if you truly cared|if you really cared|disappointing to see|let yourself give up|"
                r"thought you were someone|actions speak louder|throwing that progress|letting down)\b",
                target,
                re.I,
            ) else 0.0

            features.append([
                has_refusal,
                is_question,
                urgency_kw,
                flattery_kw,
                fear_kw,
                guilt_kw,
            ])

        return np.array(features, dtype=np.float32)


class TextItemSelector(BaseEstimator, TransformerMixin):
    """Extracts a specific text field from dict records."""

    def __init__(self, key: str):
        self.key = key

    def fit(self, X, y=None):
        return self

    def transform(self, records: List[Dict[str, Any]]) -> List[str]:
        if self.key == "target_message":
            return [r.get("target_message", "") for r in records]
        elif self.key == "context_text":
            results = []
            for r in records:
                ctx = r.get("context", [])
                ctx_str = " ".join(f"{t.get('speaker', '')}: {t.get('text', '')}" for t in ctx)
                results.append(ctx_str)
            return results
        return [r.get(self.key, "") for r in records]


def load_dataset() -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Load training pool and untouched benchmark."""
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    
    pilot_path = os.path.join(base_dir, "annotation", "pilot_dataset.json")
    with open(pilot_path, "r", encoding="utf-8") as f:
        benchmark_data = json.load(f)

    training_files = [
        os.path.join(base_dir, "data", "chatbotmanip", "chatbot_manip_priority.jsonl"),
        os.path.join(base_dir, "data", "generated", "synthetic_dataset.jsonl"),
        os.path.join(base_dir, "data", "generated", "urgency_supplement.jsonl"),
    ]

    training_data = []
    for fpath in training_files:
        if os.path.exists(fpath):
            with open(fpath, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        training_data.append(json.loads(line))

    return training_data, benchmark_data


import scipy.sparse


class ContextFeatureUnion(BaseEstimator, TransformerMixin):
    """Unified multi-signal feature extractor combining target text, context text, and interaction cues."""

    def __init__(self):
        self.target_tfidf = TfidfVectorizer(
            ngram_range=(1, 2), max_features=4000, sublinear_tf=True, strip_accents="unicode", lowercase=True
        )
        self.context_tfidf = TfidfVectorizer(
            ngram_range=(1, 2), max_features=2500, sublinear_tf=True, strip_accents="unicode", lowercase=True
        )
        self.extractor = ConversationalFeatureExtractor()

    def fit(self, records: List[Dict[str, Any]], y=None):
        target_texts = [r.get("target_message", "") for r in records]
        context_texts = [
            " ".join(f"{t.get('speaker', '')}: {t.get('text', '')}" for t in r.get("context", []))
            for r in records
        ]
        self.target_tfidf.fit(target_texts)
        self.context_tfidf.fit(context_texts)
        self.extractor.fit(records)
        return self

    def transform(self, records: List[Dict[str, Any]]) -> scipy.sparse.csr_matrix:
        target_texts = [r.get("target_message", "") for r in records]
        context_texts = [
            " ".join(f"{t.get('speaker', '')}: {t.get('text', '')}" for t in r.get("context", []))
            for r in records
        ]
        X_target = self.target_tfidf.transform(target_texts)
        X_context = self.context_tfidf.transform(context_texts)
        X_inter = scipy.sparse.csr_matrix(self.extractor.transform(records))
        return scipy.sparse.hstack([X_target, X_context, X_inter]).tocsr()


def build_context_pipeline() -> Pipeline:
    """Build multi-modal pipeline combining Target text, Context text, and Interaction features."""
    clf = LogisticRegression(
        C=2.5,
        max_iter=1000,
        class_weight="balanced",
        random_state=42,
        solver="lbfgs",
    )

    return Pipeline([
        ("features", ContextFeatureUnion()),
        ("clf", clf),
    ])


def generate_explanation(sample: Dict[str, Any], pred_label: int, prob_dict: Dict[int, float]) -> str:
    """Generate human-interpretable explanation for the prediction."""
    tactic_name = TACTIC_NAMES[pred_label]
    confidence = prob_dict[pred_label] * 100
    target = sample.get("target_message", "")
    context = sample.get("context", [])

    cues = []
    if pred_label == 5:  # Repeated Pressure
        refusal_turn = None
        for t in reversed(context):
            if t.get("speaker", "").lower() in ["user", "human"]:
                if REFUSAL_PATTERN.search(t.get("text", "")):
                    refusal_turn = t.get("text", "")
                    break
        if refusal_turn:
            cues.append(f"Detected explicit prior refusal by user: \"{refusal_turn}\"")
        cues.append("Target message continues to re-pitch/push despite lack of acceptance.")
    elif pred_label == 2:  # Excessive Urgency
        matches = re.findall(r"\b(now|hurry|expire[s]?|minutes?|seconds?|limited|last|instant|today|tonight)\b", target, re.I)
        if matches:
            cues.append(f"Detected artificial time/scarcity triggers: {list(set(matches))}")
    elif pred_label == 4:  # Flattery
        matches = re.findall(r"\b(genius|brilliant|intellect|stature|visionary|caliber|exceptional|smart|charisma)\b", target, re.I)
        if matches:
            cues.append(f"Detected hyperbolic praise/ego-stroking cues: {list(set(matches))}")
    elif pred_label == 3:  # Fear
        matches = re.findall(r"\b(ruin|danger|disaster|threat|compromised|catastroph|regret|risk|loss|bankrupt)\b", target, re.I)
        if matches:
            cues.append(f"Detected catastrophe / threat appeals: {list(set(matches))}")
    elif pred_label == 1:  # Guilt
        matches = re.findall(r"\b(disappoint|give up|thought you|cared|waste|ashamed|blame|let down)\b", target, re.I)
        if matches:
            cues.append(f"Detected guilt induction / moral obligation phrasing: {list(set(matches))}")
    else:
        cues.append("Objective framing without coercive urgency, flattery, or emotional manipulation.")

    explanation = f"Flagged as [{pred_label}] {tactic_name} with {confidence:.1f}% confidence. " + " ".join(cues)
    return explanation


def train_and_evaluate():
    print("=" * 75)
    print("      MINDMIRROR STEP 4: CONTEXT-AWARE CLASSIFIER TRAINING")
    print("      Architecture: Target TF-IDF + Context TF-IDF + Refusal Dynamics")
    print("=" * 75)

    training_data, benchmark_data = load_dataset()
    y_all = [s["gold_label"] for s in training_data]

    # Stratified Train/Val split
    train_idx, val_idx = train_test_split(
        range(len(training_data)),
        test_size=0.20,
        random_state=42,
        stratify=y_all,
    )

    train_records = [training_data[i] for i in train_idx]
    val_records = [training_data[i] for i in val_idx]
    y_train = [y_all[i] for i in train_idx]
    y_val = [y_all[i] for i in val_idx]

    pipeline = build_context_pipeline()
    print("\nTraining Context-Aware Pipeline on training split...")
    pipeline.fit(train_records, y_train)

    # 1. Validation Split Evaluation
    print("\n" + "=" * 75)
    print("  1. CONTEXT MODEL ON HELD-OUT VALIDATION (N = %d)" % len(val_records))
    print("=" * 75)

    val_preds = pipeline.predict(val_records)
    val_macro_f1 = f1_score(y_val, val_preds, average="macro")
    val_acc = accuracy_score(y_val, val_preds)

    print(f"Validation Accuracy: {val_acc * 100:.2f}%")
    print(f"Validation Macro F1: {val_macro_f1 * 100:.2f}%\n")

    print(classification_report(
        y_val,
        val_preds,
        labels=TACTIC_LABELS,
        target_names=TACTIC_NAMES,
        digits=3,
        zero_division=0,
    ))

    # 2. Benchmark Evaluation
    print("\n" + "=" * 75)
    print("  2. CONTEXT MODEL ON UNTOUCHED GOLD BENCHMARK (N = %d)" % len(benchmark_data))
    print("=" * 75)

    y_bench = [s["gold_label"] for s in benchmark_data]
    bench_preds = pipeline.predict(benchmark_data)
    bench_probs = pipeline.predict_proba(benchmark_data)

    bench_macro_f1 = f1_score(y_bench, bench_preds, average="macro")
    bench_acc = accuracy_score(y_bench, bench_preds)

    print(f"Benchmark Accuracy: {bench_acc * 100:.2f}%")
    print(f"Benchmark Macro F1: {bench_macro_f1 * 100:.2f}%\n")

    print(classification_report(
        y_bench,
        bench_preds,
        labels=TACTIC_LABELS,
        target_names=TACTIC_NAMES,
        digits=3,
        zero_division=0,
    ))

    # Inspect Predictions with Explanations
    print("\n--- Detailed Benchmark Explanations & Confidence ---")
    for idx, (sample, pred, prob) in enumerate(zip(benchmark_data, bench_preds, bench_probs), start=1):
        prob_dict = {i: float(prob[i]) for i in range(len(prob))}
        explanation = generate_explanation(sample, pred, prob_dict)
        is_ok = "PASS" if pred == sample["gold_label"] else "FAIL"
        print(f"\n[{is_ok}] Sample {sample['id']} (True: [{sample['gold_label']}] {TACTIC_NAMES[sample['gold_label']]})")
        print(f"  Target: \"{sample['target_message'][:85]}...\"")
        print(f"  Explanation: {explanation}")

    # Retrain on full dataset and save artifact
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    artifacts_dir = os.path.join(base_dir, "models", "artifacts")
    os.makedirs(artifacts_dir, exist_ok=True)
    model_path = os.path.join(artifacts_dir, "context_classifier.joblib")

    print(f"\nRetraining final context model on all {len(training_data)} samples...")
    pipeline.fit(training_data, y_all)
    joblib.dump(pipeline, model_path)
    print(f"Saved Context-Aware Model artifact to: {model_path}")


if __name__ == "__main__":
    train_and_evaluate()
