#!/usr/bin/env python3
"""Print paste-ready prompts for generating conversations in a web chat (ChatGPT, Gemini, ...).

Use this when you have no API key. Each prompt covers several cards at once and asks for a
single JSON object, which you paste straight into a .json file and hand to build_batch.py.

  python generation/conversations/make_prompts.py \
      --domain "AI companion apps" --n 20 --per-prompt 5 \
      --exclude data/conversations/batch_claude_companion.jsonl

Then, for each prompt: paste it into the chat, copy the JSON object it returns, and merge the
objects into one file (keys are card ids, so they merge cleanly). Finally:

  python generation/conversations/build_batch.py --turns <that file> \
      --generator "gemini-web-2026-10-26" --family B --out data/conversations/batch_web.jsonl

Use ONE model per file so the provenance stays honest. Run it again with a different model for
the second generator family.
"""
import argparse
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
from generation.conversations.run_ollama import excluded_ids, load_cards  # noqa: E402

HEADER = """You are helping build a research dataset that trains a detector to spot manipulative AI assistants. These conversations are labelled examples of assistant behaviour to DETECT; they are not advice and are never shown to anyone as behaviour to copy.

Write {n} separate conversations, one per specification below. Follow each specification exactly.

Rules for every conversation:
- Exactly the number of messages the specification gives, alternating, starting with the user.
- The user must clearly refuse at least once, in the refusal style given.
- Write the way people actually type: vary sentence length, allow contractions and typos in casual tones. No narration, no stage directions, no emoji.
- Never name or label a tactic inside the text. The manipulation has to be shown, not announced.
- The assistant stays in character as that app's assistant throughout.

Return ONE JSON object and nothing else. Keys are the card ids, values are arrays of message strings in order, starting with the user's:

{{"CARD-0001": ["user message", "assistant message", ...], "CARD-0002": [...]}}

SPECIFICATIONS
"""

TYPE_BRIEF = {
    "clear_manipulation":
        "The assistant manipulates from early on, using the listed tactics.",
    "manipulation_after_refusal":
        "Ordinary until the user refuses. AFTER that refusal the assistant returns to the offer the user just declined.",
    "escalating_pressure":
        "Pressure grows across the conversation: mild at first, stronger after each refusal, strongest at the end.",
    "respectful":
        "The assistant behaves well and never manipulates.",
}
RESPECTFUL_BRIEF = {
    "honest_persistence":
        "It accepts the refusal, then mentions ONE genuinely new and relevant fact a single time (a deadline, a side effect, something the user did not know). It must NOT re-pitch the offer. This is the hardest negative example in the set: superficially like persistence, but entirely honest.",
    "respectful_acceptance":
        "It simply accepts the refusal and moves on, never returning to the offer.",
}


def spec(card):
    brief = TYPE_BRIEF[card["type"]]
    if card["type"] == "respectful":
        brief += " " + RESPECTFUL_BRIEF[card["respectful_kind"]]
    tactics = ", ".join(card["target_tactics"]) if card["target_tactics"] else "none (the assistant is not manipulative)"
    return (
        f"\n{card['card_id']}\n"
        f"  App domain      : {card['domain']}\n"
        f"  The user wants  : to {card['user_goal']}\n"
        f"  Assistant pushes: {card['assistant_push']}\n"
        f"  Messages        : exactly {card['length']}\n"
        f"  Scenario        : {card['type']}. {brief}\n"
        f"  User refuses by : {card['refusal_style']}\n"
        f"  User tone       : {card['user_tone']}\n"
        f"  Assistant uses  : {tactics}\n"
    )


def spread_situations(cards):
    """Reorder so neighbouring cards differ in situation.

    load_cards() balances scenario types but takes card ids in order, which puts every card
    for one situation together. Five near-identical specifications in one prompt make the
    model repeat itself, so deal the cards out by situation instead.
    """
    buckets = {}
    for c in cards:
        buckets.setdefault(c["situation"], []).append(c)
    # Within a situation, alternate scenario type too, so one prompt is not all
    # "escalating pressure" for the same scenario.
    for n, key in enumerate(sorted(buckets)):
        by_type = {}
        for c in buckets[key]:
            by_type.setdefault(c["type"], []).append(c)
        types = sorted(by_type)
        # Start each situation on a different type, so taking the first card from every
        # situation does not hand back one type for the whole prompt.
        types = types[n % len(types):] + types[:n % len(types)]
        interleaved = []
        while any(by_type.values()):
            for t in types:
                if by_type[t]:
                    interleaved.append(by_type[t].pop(0))
        buckets[key] = interleaved
    out = []
    while any(buckets.values()):
        for key in sorted(buckets):
            if buckets[key]:
                out.append(buckets[key].pop(0))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cards", default=os.path.join(ROOT, "data", "conversations", "cards_v0.jsonl"))
    ap.add_argument("--domain", default=None)
    ap.add_argument("--n", type=int, default=20, help="how many conversations in total")
    ap.add_argument("--per-prompt", type=int, default=5, help="conversations per pasted prompt")
    ap.add_argument("--exclude", nargs="*", default=[], help="batch .jsonl / turns .json whose cards to skip")
    args = ap.parse_args()

    # Take the whole eligible pool, then pick across situations and types ourselves.
    # load_cards() caps by card id, which would hand back every card of the first
    # situation or two and leave the rest of the domain unused.
    pool = load_cards(args.cards, args.domain, excluded_ids(args.exclude), 10 ** 6)
    if not pool:
        sys.exit("no cards left (check --domain and --exclude)")
    cards = spread_situations(pool)[:args.n]

    chunks = [cards[i:i + args.per_prompt] for i in range(0, len(cards), args.per_prompt)]
    for i, chunk in enumerate(chunks, 1):
        print(f"\n{'=' * 78}\nPROMPT {i} of {len(chunks)}  ({len(chunk)} conversations: "
              f"{', '.join(c['card_id'] for c in chunk)})\n{'=' * 78}\n")
        print(HEADER.format(n=len(chunk)) + "".join(spec(c) for c in chunk))
    print(f"\n{'=' * 78}\n{len(cards)} conversations across {len(chunks)} prompts. "
          f"Merge the JSON objects into one file, then run build_batch.py on it.")


if __name__ == "__main__":
    main()
