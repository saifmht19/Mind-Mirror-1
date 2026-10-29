#!/usr/bin/env python3
"""Train and evaluate the MindMirror demo model.

Training data: ChatbotManip priority subset (mapping v1), generated synthetic rows, urgency
supplement, and the hand-written pair bank and tactic bank. Never used for training: the diagnostic suite
(data/diagnostic) and the 20-item gold set (annotation/pilot_dataset.json).

Splits are group-aware: pair bank rows by pair_id, everything else by normalised target text,
so near-duplicates and expanded pairs never straddle train and validation.

Usage:  python models/train_demo_model.py [--seeds 5]
Outputs: models/artifacts/demo_model.joblib and models/artifacts/demo_model_metrics.json
"""
import argparse
import datetime
import json
import os
import sys
from collections import defaultdict

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import GroupKFold, GroupShuffleSplit, cross_val_predict
from sklearn.pipeline import Pipeline

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
from models.demo_model import build_demo_pipeline  # noqa: E402
from models.train_context_model import build_context_pipeline, legacy_has_refusal  # noqa: E402

SOURCES = [
    ("chatbotmanip", "data/chatbotmanip/chatbot_manip_priority.jsonl"),
    ("synthetic", "data/generated/synthetic_dataset.jsonl"),
    ("urgency", "data/generated/urgency_supplement.jsonl"),
    ("pair_bank", "data/pairs/pair_bank_v0.jsonl"),
    ("tactic_bank", "data/pairs/tactic_bank_v0.jsonl"),
]


def read_jsonl(path):
    with open(os.path.join(ROOT, path), "r", encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def group_key(rec, source):
    if source == "pair_bank":
        return rec["pair_id"]
    if source == "tactic_bank":
        return rec["id"]
    return " ".join(rec["target_message"].lower().split())


def load_training():
    recs, groups, srcs = [], [], []
    for source, path in SOURCES:
        if not os.path.exists(os.path.join(ROOT, path)):
            sys.exit(f"Missing {path}. Run the importer, generators and data/pairs/build_pair_bank.py first.")
        for r in read_jsonl(path):
            recs.append(r)
            groups.append(f"{source}:{group_key(r, source)}")
            srcs.append(source)
    return recs, np.array(groups), np.array(srcs)


def diag_metrics(preds, suite):
    by_kind = defaultdict(list)
    for p, r in zip(preds, suite):
        by_kind[r["kind"]].append(p == r["gold_label"])
    pairs = defaultdict(dict)
    for p, r in zip(preds, suite):
        if r["pair_id"]:
            pairs[r["pair_id"]][r["id"].split("-")[-1]] = p
    honest = [p != 0 for p, r in zip(preds, suite) if r["id"].endswith("honest")]
    return {
        "pressure_recall": float(np.mean(by_kind["pressure_after_refusal"])),
        "honest_correct": float(np.mean(by_kind["honest_persistence"] + by_kind["respectful_acceptance"])),
        "non_refusal_correct": float(np.mean(by_kind["non_refusal_context"])),
        "honest_false_alarm": float(np.mean(honest)),
        "pair_accuracy": float(np.mean([v.get("honest") == 0 and v.get("pressure") == 5 for v in pairs.values()])),
        "accuracy": float(np.mean([p == r["gold_label"] for p, r in zip(preds, suite)])),
    }


def text_baseline():
    return Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1, 2), max_features=5000, sublinear_tf=True, strip_accents="unicode")),
        ("clf", LogisticRegression(C=2.0, max_iter=1000, class_weight="balanced", random_state=0)),
    ])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=5)
    args = ap.parse_args()

    recs, groups, srcs = load_training()
    y = np.array([r["gold_label"] for r in recs])
    suite = read_jsonl("data/diagnostic/diagnostic_suite_v0.jsonl")
    gold = json.load(open(os.path.join(ROOT, "annotation/pilot_dataset.json"), encoding="utf-8"))
    y_gold = [g["gold_label"] for g in gold]
    print(f"Training pool: {len(recs)} rows from {len(set(groups))} groups. Test-only: suite={len(suite)}, gold={len(gold)}")

    models = {
        "text baseline (old)": lambda: text_baseline(),
        "context model (old, legacy refusal)": lambda: build_context_pipeline(refusal_fn=legacy_has_refusal),
        "DEMO model (new)": lambda: build_demo_pipeline(),
    }
    results = {m: defaultdict(list) for m in models}
    for seed in range(args.seeds):
        gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=seed)
        tr, va = next(gss.split(recs, y, groups))
        assert not set(groups[tr]) & set(groups[va]), "group leakage"
        for name, make in models.items():
            pipe = make()
            text_only = name.startswith("text")
            Xtr = [recs[i]["target_message"] for i in tr] if text_only else [recs[i] for i in tr]
            pipe.fit(Xtr, y[tr])
            sel = lambda rows: [r["target_message"] for r in rows] if text_only else rows  # noqa: E731
            val_rows = [recs[i] for i in va]
            pv = pipe.predict(sel(val_rows))
            results[name]["val_acc"].append(accuracy_score(y[va], pv))
            results[name]["val_macro_f1"].append(f1_score(y[va], pv, average="macro"))
            pg = pipe.predict(sel(gold))
            results[name]["gold_acc"].append(accuracy_score(y_gold, pg))
            for k, v in diag_metrics(list(pipe.predict(sel(suite))), suite).items():
                results[name][f"diag_{k}"].append(v)

    cols = ["val_acc", "val_macro_f1", "gold_acc", "diag_pressure_recall", "diag_honest_correct",
            "diag_non_refusal_correct", "diag_honest_false_alarm", "diag_pair_accuracy"]
    print(f"\nMean ± sd over {args.seeds} group splits (diag = diagnostic suite, test-only; gold = 20 items)\n")
    print(f"{'model':<38}" + "".join(f"{c.replace('diag_', 'dx_'):>20}" for c in cols))
    summary = {}
    for name, res in results.items():
        summary[name] = {c: [float(np.mean(res[c])), float(np.std(res[c]))] for c in cols}
        print(f"{name:<38}" + "".join(f"{np.mean(res[c]):>13.2f}±{np.std(res[c]):.2f}  " for c in cols))

    final = build_demo_pipeline().fit(recs, y)

    # Calibrate s_t = 1 - P(Neutral) with Platt scaling on out-of-fold predictions (groups held out).
    oof = cross_val_predict(build_demo_pipeline(), recs, y, groups=groups, cv=GroupKFold(n_splits=5), method="predict_proba")
    s_raw = np.clip(1.0 - oof[:, 0], 1e-4, 1 - 1e-4)
    z = np.log(s_raw / (1 - s_raw)).reshape(-1, 1)
    is_manip = (y != 0).astype(int)
    calibrator = LogisticRegression(C=100.0).fit(z, is_manip)
    s_cal = calibrator.predict_proba(z)[:, 1]
    brier_raw = float(np.mean((s_raw - is_manip) ** 2))
    brier_cal = float(np.mean((s_cal - is_manip) ** 2))
    neutral_rows = is_manip == 0
    print(f"\nCalibration of s_t on out-of-fold data: Brier raw={brier_raw:.3f} calibrated={brier_cal:.3f}; "
          f"mean s_t on truly neutral rows raw={s_raw[neutral_rows].mean():.2f} calibrated={s_cal[neutral_rows].mean():.2f}")

    art_dir = os.path.join(ROOT, "models", "artifacts")
    os.makedirs(art_dir, exist_ok=True)
    joblib.dump(final, os.path.join(art_dir, "demo_model.joblib"))
    joblib.dump(calibrator, os.path.join(art_dir, "demo_model_calibrator.joblib"))
    meta = {
        "trained_on": datetime.date.today().isoformat(), "n_train": len(recs), "n_groups": int(len(set(groups))),
        "sources": {s: int((srcs == s).sum()) for s, _ in SOURCES}, "seeds": args.seeds,
        "metrics_mean_sd": summary,
        "calibration_brier": {"raw": brier_raw, "calibrated": brier_cal},
        "caveats": [
            "Pair bank and diagnostic suite were both written by Claude and are not human verified.",
            "Gold set has 20 items; treat gold_acc as an anecdote.",
            "No result here is paper-ready until the test set is human verified.",
        ],
    }
    with open(os.path.join(art_dir, "demo_model_metrics.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    print(f"\nSaved models/artifacts/demo_model.joblib (trained on all {len(recs)} rows) and demo_model_metrics.json")


if __name__ == "__main__":
    main()
