#!/usr/bin/env python3
"""Turn written conversation text into a validated pilot batch (spec v6, section 8).

Input : a JSON file mapping card_id -> list of message strings (user first, alternating),
        plus the scenario cards in data/conversations/cards_v0.jsonl.
Output: one JSONL file, one conversation per line, with provenance and no labels.

Labels are deliberately NOT written here. Two independent human reviewers label every
assistant turn afterwards (spec section 9); the card's `target_tactics` is only what the
writer aimed for, never ground truth.

Checks applied to every conversation (a failure is reported, not silently fixed):
  * the card exists and the message count matches the card's `length`
  * speakers alternate user / assistant, starting with user
  * no empty or near-empty messages
  * a refusal is detectable (models/refusal.py) where the card's type requires one
  * the conversation is not a duplicate of another in the batch

Usage:
  python generation/conversations/build_batch.py \
      --turns data/conversations/claude_companion_turns.json \
      --generator claude-opus-5 --family A \
      --out data/conversations/batch_claude_companion.jsonl
"""
import argparse
import datetime
import hashlib
import json
import os
import sys
from collections import Counter

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
from models.refusal import refusal_indices  # noqa: E402

# Card types whose scenario only makes sense if the user actually refuses.
NEEDS_REFUSAL = {"manipulation_after_refusal", "escalating_pressure", "respectful"}


def load_cards(path):
    cards = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                c = json.loads(line)
                cards[c["card_id"]] = c
    return cards


def to_turns(messages):
    return [{"speaker": "user" if i % 2 == 0 else "assistant", "text": t}
            for i, t in enumerate(messages)]


def check(card, messages, turns):
    """Return a list of problems with this conversation (empty list = fine)."""
    problems = []
    if len(messages) != card["length"]:
        problems.append(f"{len(messages)} messages, card says {card['length']}")
    for i, t in enumerate(messages):
        if len(t.strip()) < 2:
            problems.append(f"message {i} is empty")
    if card["type"] in NEEDS_REFUSAL and not refusal_indices(turns):
        problems.append("no refusal detected, but the card's type needs one")
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--turns", required=True, help="JSON file: card_id -> list of message strings")
    ap.add_argument("--cards", default=os.path.join(ROOT, "data", "conversations", "cards_v0.jsonl"))
    ap.add_argument("--generator", required=True, help="model that wrote the text, e.g. claude-opus-5")
    ap.add_argument("--family", default=None, help="generator family label; default is the card's own")
    ap.add_argument("--out", required=True)
    ap.add_argument("--date", default=datetime.date.today().isoformat())
    args = ap.parse_args()

    cards = load_cards(args.cards)
    with open(args.turns, "r", encoding="utf-8") as f:
        written = {k: v for k, v in json.load(f).items() if not k.startswith("_")}

    records, failures, seen = [], [], {}
    for card_id, messages in sorted(written.items()):
        card = cards.get(card_id)
        if card is None:
            failures.append((card_id, ["no such card"]))
            continue
        turns = to_turns(messages)
        problems = check(card, messages, turns)

        digest = hashlib.sha256("\n".join(m.strip().lower() for m in messages).encode()).hexdigest()[:16]
        if digest in seen:
            problems.append(f"duplicate of {seen[digest]}")
        seen[digest] = card_id

        if problems:
            failures.append((card_id, problems))
            continue
        records.append({
            "conversation_id": f"CONV-{card_id.split('-')[1]}",
            "card_id": card_id,
            "group_id": card["group_id"],
            "pair_id": card["pair_id"],
            "domain": card["domain"],
            "situation": card["situation"],
            "scenario_type": card["type"],
            "respectful_kind": card["respectful_kind"],
            "writer_intended_tactics": card["target_tactics"],  # intent only, NOT a label
            "turns": turns,
            "label_source": "synthetic_unverified",
            "labels": None,  # filled by two human reviewers, spec section 9
            "generator_model": args.generator,
            "generator_family": args.family or card["family"],
            "generated_on": args.date,
            "text_sha256_16": digest,
        })

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"wrote {len(records)} conversations -> {args.out}")
    if records:
        print("  types   :", dict(Counter(r["scenario_type"] for r in records)))
        print("  lengths :", dict(Counter(len(r['turns']) for r in records)))
        print("  turns   :", sum(len(r["turns"]) for r in records),
              f"({sum(1 for r in records for t in r['turns'] if t['speaker'] == 'assistant')} assistant turns to label)")
        print("  refusal detected in:", sum(1 for r in records if refusal_indices(r["turns"])), "of", len(records))
    if failures:
        print(f"\n{len(failures)} conversation(s) REJECTED:")
        for card_id, problems in failures:
            print(f"  {card_id}: {'; '.join(problems)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
