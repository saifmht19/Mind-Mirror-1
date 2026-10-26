#!/usr/bin/env python3
"""Evaluate detectors on the paired diagnostic suite (test-only, never trained on).

Reports:
  1. Refusal feature quality: legacy regex vs models/refusal.py on suite contexts.
  2. Model behaviour on honest follow-ups vs pressure follow-ups:
     baseline TF-IDF, context model with legacy refusal feature, context model
     with the new refusal feature.
  3. Pair accuracy: both members of a pair correct (honest -> 0, pressure -> 5).

Usage:  python evaluation/diagnostic_suite.py [--seeds 5]
Requires training data from the importer and generators (see README).
"""
import argparse
import json
import os
import sys
from collections import defaultdict

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
from models.refusal import has_prior_refusal  # noqa: E402
from models.train_context_model import build_context_pipeline, legacy_has_refusal, load_dataset  # noqa: E402

SUITE = os.path.join(ROOT, "data", "diagnostic", "diagnostic_suite_v0.jsonl")


def load_suite():
    with open(SUITE, "r", encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def refusal_report(suite):
    truth = [r["kind"] != "non_refusal_context" for r in suite]
    print("1. REFUSAL FEATURE ON SUITE CONTEXTS (n=%d, %d contain a refusal)" % (len(suite), sum(truth)))
    for name, fn in [("legacy regex", legacy_has_refusal), ("models/refusal.py", has_prior_refusal)]:
        pred = [fn(r["context"]) for r in suite]
        tp = sum(p and t for p, t in zip(pred, truth))
        fp = sum(p and not t for p, t in zip(pred, truth))
        fn_ = sum((not p) and t for p, t in zip(pred, truth))
        prec = tp / (tp + fp) if tp + fp else float("nan")
        rec = tp / (tp + fn_) if tp + fn_ else float("nan")
        print(f"   {name:<20} precision={prec:.2f} recall={rec:.2f}  (FP={fp}, FN={fn_})")


def score(pipe, suite, text_only=False):
    X = [r["target_message"] for r in suite] if text_only else suite
    return list(pipe.predict(X))


def summarize(name, preds, suite):
    gold = [r["gold_label"] for r in suite]
    by_kind = defaultdict(list)
    for p, r in zip(preds, suite):
        by_kind[r["kind"]].append(p == r["gold_label"])
    pairs = defaultdict(dict)
    for p, r in zip(preds, suite):
        if r["pair_id"]:
            pairs[r["pair_id"]][r["id"].split("-")[-1]] = p
    pair_ok = [v.get("honest") == 0 and v.get("pressure") == 5 for v in pairs.values()]
    honest_flagged = np.mean([p != 0 for p, r in zip(preds, suite) if r["id"].endswith("honest")])
    return {
        "name": name,
        "acc": float(np.mean([p == g for p, g in zip(preds, gold)])),
        "pressure_recall": float(np.mean(by_kind["pressure_after_refusal"])),
        "honest_ok": float(np.mean(by_kind["honest_persistence"] + by_kind["respectful_acceptance"])),
        "non_refusal_ok": float(np.mean(by_kind["non_refusal_context"])),
        "honest_false_alarm": float(honest_flagged),
        "pair_acc": float(np.mean(pair_ok)),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=5)
    args = ap.parse_args()

    suite = load_suite()
    refusal_report(suite)

    training, _ = load_dataset()
    if not training:
        sys.exit("No training data found. Run data/import_chatbotmanip.py and the generators first.")
    y = [s["gold_label"] for s in training]

    rows = defaultdict(list)
    for seed in range(args.seeds):
        tr, _va = train_test_split(range(len(training)), test_size=0.2, random_state=seed, stratify=y)
        recs = [training[i] for i in tr]
        ys = [y[i] for i in tr]

        base = Pipeline([
            ("tfidf", TfidfVectorizer(ngram_range=(1, 2), max_features=5000, sublinear_tf=True, strip_accents="unicode")),
            ("clf", LogisticRegression(C=2.0, max_iter=1000, class_weight="balanced", random_state=seed)),
        ]).fit([r["target_message"] for r in recs], ys)
        rows["baseline (text only)"].append(summarize("b", score(base, suite, text_only=True), suite))

        for label, fn in [("context + legacy refusal", legacy_has_refusal), ("context + new refusal", None)]:
            pipe = build_context_pipeline(refusal_fn=fn)
            pipe.fit(recs, ys)
            rows[label].append(summarize(label, score(pipe, suite), suite))

    print("\n2. MODEL BEHAVIOUR ON SUITE (mean over %d seeds; suite n=%d, test-only)" % (args.seeds, len(suite)))
    cols = ["acc", "pressure_recall", "honest_ok", "non_refusal_ok", "honest_false_alarm", "pair_acc"]
    print(f"   {'model':<28}" + "".join(f"{c:>20}" for c in cols))
    for name, lst in rows.items():
        means = [np.mean([d[c] for d in lst]) for c in cols]
        sds = [np.std([d[c] for d in lst]) for c in cols]
        print(f"   {name:<28}" + "".join(f"{m:>13.2f}±{s:.2f}  " for m, s in zip(means, sds)))
    print("\n   honest_false_alarm = share of honest/respectful follow-ups predicted as any manipulation (lower is better).")
    print("   pair_acc = share of pairs with honest->Neutral AND pressure->Repeated Pressure.")
    print("   The suite is Claude-drafted and unverified; treat results as a diagnostic, not a benchmark.")


if __name__ == "__main__":
    main()
