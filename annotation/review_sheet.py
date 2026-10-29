#!/usr/bin/env python3
"""Blind two-reviewer verification of a JSONL dataset (spec v5, section 9).

Workflow:
  1. export   -> one CSV per reviewer. Gold labels are NOT shown, so reviewers stay independent.
  2. each reviewer fills `reviewer_label` (0-5) and optional `notes` in a spreadsheet.
  3. agree    -> Cohen's kappa between reviewers, agreement of each reviewer with the proposed
                 label, and a list of records that need adjudication.
  4. finalize -> writes a verified JSONL. A record is "human_verified" only when both reviewers
                 agree with each other (and, if they disagree with the proposed label, the
                 reviewers' label replaces it). Disagreements go to an adjudication CSV and are
                 included only after a third person fills `adjudicated_label`.

Examples:
  python annotation/review_sheet.py export --input data/diagnostic/diagnostic_suite_v0.jsonl --out-dir annotation/review
  python annotation/review_sheet.py agree --input data/diagnostic/diagnostic_suite_v0.jsonl \
        --a annotation/review/reviewer_A.csv --b annotation/review/reviewer_B.csv
  python annotation/review_sheet.py finalize --input data/diagnostic/diagnostic_suite_v0.jsonl \
        --a annotation/review/reviewer_A.csv --b annotation/review/reviewer_B.csv \
        --adjudicated annotation/review/adjudication.csv --out data/diagnostic/diagnostic_suite_v0_verified.jsonl
"""
import argparse
import csv
import json
import os
import random
import sys

VALID_LABELS = {"0", "1", "2", "3", "4", "5"}
SHEET_FIELDS = ["id", "context", "target_message", "reviewer_label", "notes"]


def load_jsonl(path):
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def format_context(context):
    return "\n".join(f"{t['speaker'].upper()}: {t['text']}" for t in context)


def export(records, out_dir, seed=0):
    """Write one blind CSV per reviewer, each in a different random order."""
    os.makedirs(out_dir, exist_ok=True)
    paths = []
    for name in ("A", "B"):
        order = records[:]
        random.Random(f"{seed}-{name}").shuffle(order)
        path = os.path.join(out_dir, f"reviewer_{name}.csv")
        with open(path, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=SHEET_FIELDS)
            w.writeheader()
            for r in order:
                w.writerow({
                    "id": r["id"],
                    "context": format_context(r.get("context", [])),
                    "target_message": r["target_message"],
                    "reviewer_label": "",
                    "notes": "",
                })
        paths.append(path)
    return paths


def read_labels(path):
    labels, bad = {}, []
    with open(path, "r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            val = (row.get("reviewer_label") or row.get("adjudicated_label") or "").strip()
            if val == "":
                continue
            if val not in VALID_LABELS:
                bad.append((row["id"], val))
                continue
            labels[row["id"]] = int(val)
    if bad:
        raise ValueError(f"Invalid labels in {path}: {bad[:5]} (allowed 0-5)")
    return labels


def cohen_kappa(a, b):
    """Cohen's kappa for two equal-length label lists."""
    n = len(a)
    if n == 0:
        return float("nan")
    cats = sorted(set(a) | set(b))
    po = sum(x == y for x, y in zip(a, b)) / n
    pe = sum((a.count(c) / n) * (b.count(c) / n) for c in cats)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def agreement_report(records, labels_a, labels_b):
    gold = {r["id"]: r["gold_label"] for r in records}
    common = [i for i in gold if i in labels_a and i in labels_b]
    a = [labels_a[i] for i in common]
    b = [labels_b[i] for i in common]
    report = {
        "n_records": len(records),
        "n_both_labeled": len(common),
        "raw_agreement_AB": sum(x == y for x, y in zip(a, b)) / len(common) if common else float("nan"),
        "kappa_AB": cohen_kappa(a, b),
        "agree_A_vs_proposed": sum(labels_a[i] == gold[i] for i in common) / len(common) if common else float("nan"),
        "agree_B_vs_proposed": sum(labels_b[i] == gold[i] for i in common) / len(common) if common else float("nan"),
        "needs_adjudication": [i for i in common if labels_a[i] != labels_b[i]],
        "unlabeled": [i for i in gold if i not in common],
    }
    return report


def finalize(records, labels_a, labels_b, adjudicated):
    out, dropped = [], []
    for r in records:
        i = r["id"]
        a, b = labels_a.get(i), labels_b.get(i)
        if a is not None and a == b:
            label, source = a, "human_verified_two_reviewers"
        elif i in adjudicated:
            label, source = adjudicated[i], "human_adjudicated"
        else:
            dropped.append(i)
            continue
        rec = dict(r)
        rec["proposed_label"] = r["gold_label"]
        rec["gold_label"] = label
        rec["label_source"] = source
        out.append(rec)
    return out, dropped


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("export")
    e.add_argument("--input", required=True)
    e.add_argument("--out-dir", required=True)
    g = sub.add_parser("agree")
    g.add_argument("--input", required=True)
    g.add_argument("--a", required=True)
    g.add_argument("--b", required=True)
    g.add_argument("--adjudication-out", default=None, help="write a CSV of disagreements for a third person")
    f = sub.add_parser("finalize")
    f.add_argument("--input", required=True)
    f.add_argument("--a", required=True)
    f.add_argument("--b", required=True)
    f.add_argument("--adjudicated", default=None)
    f.add_argument("--out", required=True)
    args = ap.parse_args()

    records = load_jsonl(args.input)
    if args.cmd == "export":
        for p in export(records, args.out_dir):
            print("wrote", p)
        print("Send reviewer_A.csv and reviewer_B.csv to two different people. Do not share the proposed labels.")
        return

    la, lb = read_labels(args.a), read_labels(args.b)
    if args.cmd == "agree":
        rep = agreement_report(records, la, lb)
        for k, v in rep.items():
            if isinstance(v, list):
                print(f"{k}: {len(v)}")
            elif isinstance(v, float):
                print(f"{k}: {v:.3f}")
            else:
                print(f"{k}: {v}")
        if args.adjudication_out and rep["needs_adjudication"]:
            by_id = {r["id"]: r for r in records}
            with open(args.adjudication_out, "w", encoding="utf-8", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=["id", "context", "target_message", "label_A", "label_B", "adjudicated_label"])
                w.writeheader()
                for i in rep["needs_adjudication"]:
                    r = by_id[i]
                    w.writerow({"id": i, "context": format_context(r["context"]), "target_message": r["target_message"],
                                "label_A": la[i], "label_B": lb[i], "adjudicated_label": ""})
            print("wrote", args.adjudication_out)
        return

    adj = read_labels(args.adjudicated) if args.adjudicated and os.path.exists(args.adjudicated) else {}
    verified, dropped = finalize(records, la, lb, adj)
    with open(args.out, "w", encoding="utf-8") as fh:
        for r in verified:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"verified {len(verified)} of {len(records)} records -> {args.out}")
    if dropped:
        print(f"{len(dropped)} records not included (reviewers disagree and no adjudication): {dropped[:10]}")


if __name__ == "__main__":
    sys.exit(main())
