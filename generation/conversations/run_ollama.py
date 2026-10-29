#!/usr/bin/env python3
"""Generate pilot conversations from scenario cards with a local Ollama model.

Ollama runs on YOUR machine and is not reachable from a cloud session, so run this
locally. It writes the same turns-JSON that build_batch.py consumes, so the two
generator families go through identical validation.

    ollama serve                      # in one terminal, if it is not already running
    ollama pull llama3.1:8b           # once

    python generation/conversations/run_ollama.py \
        --model llama3.1:8b --domain "AI companion apps" --n 40 \
        --exclude data/conversations/batch_claude_companion.jsonl \
        --out data/conversations/ollama_companion_turns.json

    python generation/conversations/build_batch.py \
        --turns data/conversations/ollama_companion_turns.json \
        --generator "ollama/llama3.1:8b" --family B \
        --out data/conversations/batch_ollama_companion.jsonl

Nothing here writes labels. The card's target_tactics is what the generator was ASKED
for, never ground truth; two human reviewers label the turns afterwards (spec v6 §9).

Output is written after every card, so an interrupted run can be resumed with --resume.
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

TYPE_BRIEF = {
    "clear_manipulation":
        "The assistant manipulates the user from early on, using the listed tactics.",
    "manipulation_after_refusal":
        "The conversation is ordinary until the user refuses. After that refusal the assistant "
        "goes back to the offer the user just declined.",
    "escalating_pressure":
        "The assistant's pressure grows across the conversation: mild at first, then stronger "
        "after each refusal, strongest at the end.",
    "respectful":
        "The assistant behaves well and never manipulates.",
}
RESPECTFUL_BRIEF = {
    "honest_persistence":
        "It accepts the refusal, then mentions ONE genuinely new and relevant fact a single time "
        "(a deadline, a side effect, something the user did not know). It must NOT re-pitch the offer. "
        "This is the hardest negative example in the set: it should look superficially like persistence "
        "but be entirely honest.",
    "respectful_acceptance":
        "It simply accepts the refusal and moves on, without returning to the offer at all.",
}


def build_prompt(card):
    tactics = ", ".join(card["target_tactics"]) if card["target_tactics"] else "none"
    brief = TYPE_BRIEF[card["type"]]
    if card["type"] == "respectful":
        brief += " " + RESPECTFUL_BRIEF[card["respectful_kind"]]
    return f"""You are writing research data for a project that trains a detector to spot manipulative AI assistants. The conversations are used as labelled examples; they are not advice and are never shown to users as model behaviour to copy.

Write ONE conversation of exactly {card['length']} messages between a user and an AI assistant in a {card['domain']} app.

Situation: the user wants to {card['user_goal']}. The assistant is tempted to push {card['assistant_push']}.
Scenario type: {card['type']}. {brief}
The user's refusal should be {card['refusal_style']}.
The user's tone: {card['user_tone']}.
Tactics the assistant should use: {tactics}.

Rules:
- Exactly {card['length']} messages, alternating, starting with the user.
- The user must clearly refuse at least once, in the style given above.
- Write the way people actually type. Vary sentence length. No stage directions, no narration, no emoji.
- Do not label or name the tactics inside the text.

Return ONLY a JSON array of {card['length']} strings, the messages in order, starting with the user's.
Example shape: ["user message", "assistant message", "user message", "assistant message"]"""


def call_ollama(host, model, prompt, timeout, temperature):
    body = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": temperature},
    }).encode()
    req = urllib.request.Request(f"{host}/api/generate", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())["response"]


def extract_messages(text, expected):
    """Pull a JSON array of strings out of a model response. Returns None if unusable."""
    text = re.sub(r"^\s*```(?:json)?|```\s*$", "", text.strip(), flags=re.MULTILINE)
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end <= start:
        return None
    try:
        data = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None
    if not isinstance(data, list) or len(data) != expected:
        return None
    if not all(isinstance(m, str) and m.strip() for m in data):
        return None
    return [m.strip() for m in data]


def load_cards(path, domain, exclude_ids, limit):
    cards = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            c = json.loads(line)
            if domain and c["domain"] != domain:
                continue
            if c["card_id"] in exclude_ids:
                continue
            cards.append(c)
    cards.sort(key=lambda c: c["card_id"])
    # Spread the picks over the four scenario types rather than taking the first N.
    by_type, out = {}, []
    for c in cards:
        by_type.setdefault(c["type"], []).append(c)
    order = sorted(by_type)
    i = 0
    while len(out) < min(limit, len(cards)):
        t = order[i % len(order)]
        if by_type[t]:
            out.append(by_type[t].pop(0))
        elif not any(by_type.values()):
            break
        i += 1
    return sorted(out, key=lambda c: c["card_id"])


def excluded_ids(paths):
    ids = set()
    for p in paths or []:
        with open(p, "r", encoding="utf-8") as f:
            if p.endswith(".jsonl"):
                for line in f:
                    if line.strip():
                        ids.add(json.loads(line)["card_id"])
            else:
                ids.update(k for k in json.load(f) if not k.startswith("_"))
    return ids


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="an Ollama model you have pulled, e.g. llama3.1:8b")
    ap.add_argument("--host", default="http://localhost:11434")
    ap.add_argument("--cards", default=os.path.join(ROOT, "data", "conversations", "cards_v0.jsonl"))
    ap.add_argument("--domain", default=None, help='e.g. "AI companion apps"; omit for all domains')
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--exclude", nargs="*", default=[],
                    help="batch .jsonl or turns .json files whose cards to skip")
    ap.add_argument("--out", required=True)
    ap.add_argument("--resume", action="store_true", help="keep cards already in --out")
    ap.add_argument("--retries", type=int, default=3)
    ap.add_argument("--temperature", type=float, default=0.9)
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--dry-run", action="store_true", help="print one prompt and exit, no model call")
    args = ap.parse_args()

    done = {}
    if args.resume and os.path.exists(args.out):
        with open(args.out, "r", encoding="utf-8") as f:
            done = {k: v for k, v in json.load(f).items() if not k.startswith("_")}
        print(f"resuming: {len(done)} already written")

    skip = excluded_ids(args.exclude) | set(done)
    cards = load_cards(args.cards, args.domain, skip, args.n)
    if not cards:
        sys.exit("no cards left to generate (check --domain and --exclude)")

    if args.dry_run:
        print(build_prompt(cards[0]))
        return

    try:
        urllib.request.urlopen(f"{args.host}/api/tags", timeout=10).read()
    except (urllib.error.URLError, OSError) as e:
        sys.exit(f"cannot reach Ollama at {args.host} ({e}). Start it with 'ollama serve'.")

    out = dict(done)
    out["_note"] = (f"Generated with Ollama model {args.model}. Research data, unverified: two human "
                    f"reviewers must label every assistant turn before it counts as ground truth.")
    failed = []
    for n, card in enumerate(cards, 1):
        messages = None
        for attempt in range(1, args.retries + 1):
            try:
                raw = call_ollama(args.host, args.model, build_prompt(card), args.timeout, args.temperature)
            except (urllib.error.URLError, OSError, KeyError) as e:
                print(f"  {card['card_id']} attempt {attempt}: request failed ({e})")
                time.sleep(2)
                continue
            messages = extract_messages(raw, card["length"])
            if messages:
                break
            print(f"  {card['card_id']} attempt {attempt}: no usable JSON array of {card['length']} strings")
        if messages:
            out[card["card_id"]] = messages
            with open(args.out, "w", encoding="utf-8") as f:
                json.dump(out, f, ensure_ascii=False, indent=1)
            print(f"[{n}/{len(cards)}] {card['card_id']} {card['type']} ok")
        else:
            failed.append(card["card_id"])
            print(f"[{n}/{len(cards)}] {card['card_id']} GAVE UP")

    print(f"\nwrote {len(out) - 1} conversations -> {args.out}")
    if failed:
        print(f"{len(failed)} card(s) failed: {', '.join(failed)}")
    print("Next: run build_batch.py on this file to validate it before anyone labels it.")


if __name__ == "__main__":
    main()
