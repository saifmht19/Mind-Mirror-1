"""Dependency-free multi-label classification metrics."""
from __future__ import annotations
from typing import Sequence


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def multilabel_metrics(y_true: Sequence[Sequence[int]], y_pred: Sequence[Sequence[int]], labels: Sequence[str]) -> dict:
    if len(y_true) != len(y_pred):
        raise ValueError("y_true and y_pred sample counts must match")
    if not labels or len(set(labels)) != len(labels):
        raise ValueError("labels must be non-empty and unique")
    width = len(labels)
    for name, matrix in (("y_true", y_true), ("y_pred", y_pred)):
        for i, row in enumerate(matrix):
            if len(row) != width or any(value not in (0, 1, False, True) for value in row):
                raise ValueError(f"{name}[{i}] must contain {width} binary values")
    per_label = {}
    total_tp = total_fp = total_fn = 0
    macro_p = macro_r = macro_f = 0.0
    supported = 0
    for j, label in enumerate(labels):
        tp = sum(bool(t[j]) and bool(p[j]) for t, p in zip(y_true, y_pred))
        fp = sum(not bool(t[j]) and bool(p[j]) for t, p in zip(y_true, y_pred))
        fn = sum(bool(t[j]) and not bool(p[j]) for t, p in zip(y_true, y_pred))
        support = sum(bool(t[j]) for t in y_true)
        precision, recall = _ratio(tp, tp + fp), _ratio(tp, tp + fn)
        f1 = _ratio(2 * precision * recall, precision + recall)
        per_label[label] = {"precision": precision, "recall": recall, "f1": f1,
                            "support": support, "true_positive": tp, "false_positive": fp, "false_negative": fn}
        total_tp += tp; total_fp += fp; total_fn += fn
        if support:
            macro_p += precision; macro_r += recall; macro_f += f1; supported += 1
    micro_p = _ratio(total_tp, total_tp + total_fp)
    micro_r = _ratio(total_tp, total_tp + total_fn)
    micro_f = _ratio(2 * micro_p * micro_r, micro_p + micro_r)
    exact = sum(tuple(map(bool, t)) == tuple(map(bool, p)) for t, p in zip(y_true, y_pred))
    jaccards = []
    for truth, prediction in zip(y_true, y_pred):
        ts, ps = {i for i, v in enumerate(truth) if v}, {i for i, v in enumerate(prediction) if v}
        jaccards.append(1.0 if not ts and not ps else len(ts & ps) / len(ts | ps))
    n = len(y_true)
    return {
        "n_samples": n,
        "labels": list(labels),
        "macro": {"precision": macro_p / supported if supported else 0.0,
                  "recall": macro_r / supported if supported else 0.0,
                  "f1": macro_f / supported if supported else 0.0,
                  "classes_in_average": supported, "averaging_note": "classes with zero gold support are excluded"},
        "micro": {"precision": micro_p, "recall": micro_r, "f1": micro_f,
                  "true_positive": total_tp, "false_positive": total_fp, "false_negative": total_fn},
        "sample_averaged_jaccard": sum(jaccards) / n if n else 0.0,
        "exact_set_accuracy": exact / n if n else 0.0,
        "per_tactic": per_label,
    }

