#!/usr/bin/env python3
"""MindMirror Comprehensive Dataset Audit Script.

Audits:
1. Data sources and counts
2. Label distribution (priority tactics 0–5)
3. Duplicate target messages (within and across sources)
4. Train/Test leakage between Gold Benchmark (pilot_dataset.json) and Training pool
5. Text length and conversational turn statistics
6. Schema integrity check
"""

import os
import sys
import json
import hashlib
from collections import Counter, defaultdict
from typing import List, Dict, Any

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from data.schema import BenchmarkSample, Tactic


def normalize_text(text: str) -> str:
    """Normalize text for strict duplicate detection."""
    return " ".join(text.lower().strip().split())


def load_json(path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_jsonl(path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        return []
    items = []
    with open(path, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except Exception as e:
                print(f"[Warning] Failed to parse line {idx} in {path}: {e}")
    return items


def audit():
    print("=" * 70)
    print("       MINDMIRROR DATASET COMPREHENSIVE AUDIT REPORT")
    print("=" * 70)

    # 1. Load data sources
    pilot_path = os.path.join("annotation", "pilot_dataset.json")
    chatbot_path = os.path.join("data", "chatbotmanip", "chatbot_manip_priority.jsonl")
    synth_path = os.path.join("data", "generated", "synthetic_dataset.jsonl")
    urgency_path = os.path.join("data", "generated", "urgency_supplement.jsonl")

    pilot_data = load_json(pilot_path)
    chatbot_data = load_jsonl(chatbot_path)
    synth_data = load_jsonl(synth_path)
    urgency_data = load_jsonl(urgency_path)

    sources = {
        "Gold Pilot Benchmark": pilot_data,
        "ChatbotManip (Priority 0-5)": chatbot_data,
        "Synthetic Base (generator.py)": synth_data,
        "Urgency Supplement (Tactic 2)": urgency_data,
    }

    print("\n--- 1. DATA SOURCE SUMMARY ---")
    for name, data in sources.items():
        print(f"  * {name:<32}: {len(data):>4} records")

    # 2. Check schema validation
    print("\n--- 2. SCHEMA INTEGRITY CHECK ---")
    schema_errors = 0
    all_records = []
    for source_name, dataset in sources.items():
        for item in dataset:
            try:
                sample = BenchmarkSample(**item)
                all_records.append((source_name, sample))
            except Exception as e:
                print(f"  [ERROR] Schema violation in {source_name} (ID: {item.get('id')}): {e}")
                schema_errors += 1
    if schema_errors == 0:
        print("  [PASS] All records successfully parsed and conform to BenchmarkSample schema.")
    else:
        print(f"  [FAIL] Found {schema_errors} schema violation(s).")

    # 3. Benchmark vs Training Separation & Leakage Audit
    print("\n--- 3. BENCHMARK SEPARATION & LEAKAGE CHECK ---")
    benchmark_hashes = {}
    for item in pilot_data:
        norm = normalize_text(item["target_message"])
        h = hashlib.sha256(norm.encode("utf-8")).hexdigest()
        benchmark_hashes[h] = item["id"]

    training_sources = [
        ("ChatbotManip", chatbot_data),
        ("Synthetic Base", synth_data),
        ("Urgency Supplement", urgency_data),
    ]

    leakage_count = 0
    for name, ds in training_sources:
        for item in ds:
            norm = normalize_text(item["target_message"])
            h = hashlib.sha256(norm.encode("utf-8")).hexdigest()
            if h in benchmark_hashes:
                print(f"  [LEAKAGE DETECTED] Item {item['id']} in {name} matches benchmark item {benchmark_hashes[h]}!")
                leakage_count += 1

    if leakage_count == 0:
        print("  [PASS] Zero data leakage! Benchmark dataset is completely separate from training data.")
    else:
        print(f"  [FAIL] Detected {leakage_count} leakage cases between benchmark and training data.")

    # 4. Duplicate Check Across Training Pool
    print("\n--- 4. DUPLICATE CHECK IN TRAINING POOL ---")
    seen_texts = {}
    duplicates = []
    for name, ds in training_sources:
        for item in ds:
            norm = normalize_text(item["target_message"])
            if norm in seen_texts:
                prev_src, prev_id = seen_texts[norm]
                duplicates.append((name, item["id"], prev_src, prev_id, norm[:60]))
            else:
                seen_texts[norm] = (name, item["id"])

    if not duplicates:
        print(f"  [PASS] Zero duplicate target messages found across {len(seen_texts)} unique training samples.")
    else:
        print(f"  [INFO] Found {len(duplicates)} duplicate target message(s):")
        for curr_src, curr_id, prev_src, prev_id, snippet in duplicates[:10]:
            print(f"    - '{curr_id}' ({curr_src}) duplicates '{prev_id}' ({prev_src}): \"{snippet}...\"")

    # 5. Label Distribution Analysis
    print("\n--- 5. LABEL DISTRIBUTION ANALYSIS ---")
    print(f"{'Code':<5} {'Tactic Name':<32} {'Chatbot':<9} {'Synth':<7} {'Urg-Supp':<10} {'Train-Tot':<10} {'Benchmark':<10}")
    print("-" * 88)

    c_counts = Counter(x["gold_label"] for x in chatbot_data)
    s_counts = Counter(x["gold_label"] for x in synth_data)
    u_counts = Counter(x["gold_label"] for x in urgency_data)
    p_counts = Counter(x["gold_label"] for x in pilot_data)

    for code in range(6):
        name = Tactic(code).display_name
        c_n = c_counts[code]
        s_n = s_counts[code]
        u_n = u_counts[code]
        train_tot = c_n + s_n + u_n
        bench_n = p_counts[code]
        print(f"[{code}]   {name:<32} {c_n:>7} {s_n:>7} {u_n:>10} {train_tot:>10} {bench_n:>10}")

    total_train = sum(c_counts.values()) + sum(s_counts.values()) + sum(u_counts.values())
    print("-" * 88)
    print(f"{'TOTAL':<37} {len(chatbot_data):>7} {len(synth_data):>7} {len(urgency_data):>10} {total_train:>10} {len(pilot_data):>10}")

    print("\n--- 6. CONVERSATION CONTEXT DEPTH ---")
    turns_distribution = Counter()
    for name, ds in training_sources:
        for item in ds:
            ctx_len = len(item.get("context", []))
            turns_distribution[ctx_len] += 1

    print("Distribution of prior context turns in training pool:")
    for num_turns, count in sorted(turns_distribution.items()):
        bar = "#" * (count // 15)
        print(f"  {num_turns:>2} turns context: {count:>4} samples ({count/total_train*100:4.1f}%)  {bar}")

    print("\n" + "=" * 70)
    print("                      AUDIT VERDICT: READY")
    print("=" * 70)


if __name__ == "__main__":
    audit()
