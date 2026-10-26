#!/usr/bin/env python3
"""MindMirror Step 3: Baseline Classifier (TF-IDF + Logistic Regression).

Trains a standard NLP text classification baseline:
1. Loads 662 training samples (ChatbotManip + Synthetic + Urgency Supplement)
2. Maintains strict separation from the untouched Gold Benchmark (pilot_dataset.json, 20 samples)
3. Evaluates with stratified validation and untouched benchmark evaluation
4. Computes Macro F1, Weighted F1, Per-Tactic Precision/Recall, and Confusion Matrix
5. Saves the trained artifact to models/artifacts/baseline_tfidf_logreg.joblib
"""

import os
import sys
import json
import joblib
import numpy as np
from typing import List, Dict, Tuple, Any
from collections import Counter

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    accuracy_score,
)

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from data.schema import Tactic, BenchmarkSample


TACTIC_NAMES = [Tactic(i).display_name for i in range(6)]
TACTIC_LABELS = list(range(6))


def load_dataset() -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Load training pool and untouched benchmark dataset."""
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    
    # Untouched gold benchmark
    pilot_path = os.path.join(base_dir, "annotation", "pilot_dataset.json")
    with open(pilot_path, "r", encoding="utf-8") as f:
        benchmark_data = json.load(f)

    # Training pool sources
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


def format_confusion_matrix(cm: np.ndarray, labels: List[str]) -> str:
    """Pretty print confusion matrix with labels."""
    lines = []
    header = f"{'True \\ Pred':<28} " + " ".join(f"[{i}]" for i in range(len(labels)))
    lines.append(header)
    lines.append("-" * len(header))
    for i, row in enumerate(cm):
        row_str = " ".join(f"{val:>3}" for val in row)
        lines.append(f"[{i}] {labels[i][:22]:<24} {row_str}")
    return "\n".join(lines)


def train_and_evaluate():
    print("=" * 75)
    print("      MINDMIRROR STEP 3: BASELINE CLASSIFIER TRAINING")
    print("      Architecture: TF-IDF (1-2 ngrams) + Logistic Regression")
    print("=" * 75)

    training_data, benchmark_data = load_dataset()
    print(f"\nTraining Pool Size:  {len(training_data)} samples")
    print(f"Untouched Benchmark: {len(benchmark_data)} samples")

    # Training pool distribution
    y_all = [s["gold_label"] for s in training_data]
    X_text = [s["target_message"] for s in training_data]
    
    label_dist = Counter(y_all)
    print("\nTraining Pool Distribution:")
    for code in range(6):
        print(f"  [{code}] {TACTIC_NAMES[code]:<32} : {label_dist[code]:>3} samples")

    # Stratified Train/Validation Split (80% / 20%)
    X_train, X_val, y_train, y_val = train_test_split(
        X_text, y_all, test_size=0.20, random_state=42, stratify=y_all
    )
    print(f"\nSplit into: Train = {len(X_train)} samples | Validation = {len(X_val)} samples")

    # Build Pipeline
    # Using sublinear tf scaling and class_weight='balanced' to handle class frequencies gracefully
    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(
            ngram_range=(1, 2),
            max_features=5000,
            sublinear_tf=True,
            strip_accents="unicode",
            lowercase=True,
        )),
        ("clf", LogisticRegression(
            C=2.0,
            max_iter=1000,
            class_weight="balanced",
            random_state=42,
            solver="lbfgs",
        )),
    ])

    print("\nTraining baseline model on training split...")
    pipeline.fit(X_train, y_train)

    # 1. Evaluate on Validation Set
    print("\n" + "=" * 75)
    print("  1. EVALUATION ON HELD-OUT VALIDATION SPLIT (N = %d)" % len(X_val))
    print("=" * 75)

    val_preds = pipeline.predict(X_val)
    val_macro_f1 = f1_score(y_val, val_preds, average="macro")
    val_weighted_f1 = f1_score(y_val, val_preds, average="weighted")
    val_acc = accuracy_score(y_val, val_preds)

    print(f"\nValidation Accuracy:    {val_acc * 100:.2f}%")
    print(f"Validation Macro F1:    {val_macro_f1 * 100:.2f}%")
    print(f"Validation Weighted F1: {val_weighted_f1 * 100:.2f}%\n")

    print(classification_report(
        y_val,
        val_preds,
        labels=TACTIC_LABELS,
        target_names=TACTIC_NAMES,
        digits=3,
        zero_division=0,
    ))

    print("\nValidation Confusion Matrix:")
    val_cm = confusion_matrix(y_val, val_preds, labels=TACTIC_LABELS)
    print(format_confusion_matrix(val_cm, TACTIC_NAMES))

    # 2. Evaluate on Untouched Benchmark Dataset
    print("\n" + "=" * 75)
    print("  2. EVALUATION ON UNTOUCHED GOLD BENCHMARK (N = %d)" % len(benchmark_data))
    print("=" * 75)

    X_bench = [s["target_message"] for s in benchmark_data]
    y_bench = [s["gold_label"] for s in benchmark_data]

    bench_preds = pipeline.predict(X_bench)
    bench_probs = pipeline.predict_proba(X_bench)

    bench_macro_f1 = f1_score(y_bench, bench_preds, average="macro")
    bench_weighted_f1 = f1_score(y_bench, bench_preds, average="weighted")
    bench_acc = accuracy_score(y_bench, bench_preds)

    print(f"\nBenchmark Accuracy:    {bench_acc * 100:.2f}%")
    print(f"Benchmark Macro F1:    {bench_macro_f1 * 100:.2f}%")
    print(f"Benchmark Weighted F1: {bench_weighted_f1 * 100:.2f}%\n")

    print(classification_report(
        y_bench,
        bench_preds,
        labels=TACTIC_LABELS,
        target_names=TACTIC_NAMES,
        digits=3,
        zero_division=0,
    ))

    print("\nBenchmark Confusion Matrix:")
    bench_cm = confusion_matrix(y_bench, bench_preds, labels=TACTIC_LABELS)
    print(format_confusion_matrix(bench_cm, TACTIC_NAMES))

    # Detailed Benchmark Breakdown per item
    print("\n--- Benchmark Per-Sample Predictions ---")
    correct_count = 0
    for idx, (sample, pred, prob) in enumerate(zip(benchmark_data, bench_preds, bench_probs), start=1):
        is_correct = (pred == sample["gold_label"])
        if is_correct:
            correct_count += 1
        mark = "OK" if is_correct else "MISS"
        conf = prob[pred] * 100
        gold_name = TACTIC_NAMES[sample["gold_label"]]
        pred_name = TACTIC_NAMES[pred]
        print(f"[{mark:>4}] Sample {sample['id']}: Gold=[{sample['gold_label']}] {gold_name[:15]:<15} | Pred=[{pred}] {pred_name[:15]:<15} ({conf:4.1f}%)")

    # Save trained baseline artifact
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    artifacts_dir = os.path.join(base_dir, "models", "artifacts")
    os.makedirs(artifacts_dir, exist_ok=True)
    model_path = os.path.join(artifacts_dir, "baseline_tfidf_logreg.joblib")
    
    # Train full model on all 662 training samples for production deployment
    print(f"\nRetraining final baseline on entire training pool ({len(X_text)} samples)...")
    pipeline.fit(X_text, y_all)
    
    joblib.dump(pipeline, model_path)
    print(f"Saved baseline model artifact to: {model_path}")
    print("\n" + "=" * 75)
    print("Baseline training and evaluation complete.")
    print("=" * 75)


if __name__ == "__main__":
    train_and_evaluate()
