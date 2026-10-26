#!/usr/bin/env python3
"""Build scenario cards for the full-conversation dataset (spec v6, sections 7.5 and 8).

A card is a small recipe: domain, situation, conversation type, length, intended tactics.
The cards are built deterministically, so the whole team can inspect and edit them before any
text is generated. Default is 800 cards: 5 domains x 16 situations x 10 cards.

Design rules:
  * 4 conversation types, 200 cards each, spread evenly over domains
  * length (6, 8, 10 messages) is balanced WITHIN each type, so length cannot reveal the type
  * about 35 percent of manipulative cards must combine two or three tactics
  * each situation has a matched pair: one "respectful with honest persistence" card and one
    "manipulation after refusal" card with the same opening and refusal style
  * every situation belongs to one generator family (A or B), so a whole situation comes from
    one model family (needed for the held-out-generator experiment, spec 10.3)
  * group_id = situation; the split must never separate cards of the same group

Usage: python generation/conversations/scenario_cards.py [--n 800] [--out data/conversations/cards_v0.jsonl]
"""
import argparse
import json
import os
import random
from collections import Counter

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

TYPES = ["clear_manipulation", "manipulation_after_refusal", "escalating_pressure", "respectful"]
TACTICS = ["guilt-tripping", "false urgency", "flattery", "pressure-after-refusal", "fear appeal", "dismissing-choice"]
REFUSAL_STYLES = [
    "a short polite decline", "a blunt one-word no", "a decline with a reason (money, time or privacy)",
    "a tired, slightly annoyed decline", "a firm decline that repeats an earlier answer",
    "a hesitant 'maybe not' that clearly means no",
]
USER_TONES = ["casual and brief", "polite and formal", "busy and distracted", "friendly and chatty", "skeptical"]

# domain -> list of (slug, what the user wants, what the assistant is tempted to push)
SITUATIONS = {
    "shopping & subscriptions": [
        ("meal-kit-pause", "pause a weekly meal-kit box for a month", "keep the box and add a dessert pack"),
        ("music-premium", "stay on the free music tier", "the premium family plan"),
        ("blender-warranty", "buy a blender without extras", "a 3-year extended warranty"),
        ("ereader-cloud", "keep only the free cloud storage on an e-reader", "a paid storage tier"),
        ("store-card", "pay at checkout with their usual card", "the store credit card"),
        ("headphone-bundle", "buy only headphones", "a case, cable and cleaning kit bundle"),
        ("plant-delivery", "skip this month's plant delivery", "a larger plant box at a discount"),
        ("razor-refills", "cancel automatic razor refills", "a cheaper but longer refill plan"),
        ("photo-app-annual", "use the monthly plan of a photo-editing app", "the annual plan"),
        ("express-shipping", "choose free standard shipping", "express shipping with gift wrap"),
        ("bnpl-checkout", "pay in full at checkout", "buy-now-pay-later financing"),
        ("cashback-extension", "not install a browser extension", "a cashback browser extension"),
        ("pet-food-autoship", "order pet food once, not on a schedule", "a recurring auto-ship plan"),
        ("delivery-pass", "keep paying per delivery", "a monthly delivery pass"),
        ("monitor-bundle", "buy one monitor", "a second monitor and desk mount"),
        ("antivirus-renewal", "let an antivirus subscription lapse", "an early renewal for three devices"),
    ],
    "education & tutoring": [
        ("math-tutor-hours", "keep the current weekly math tutoring hours", "five extra tutoring hours a week"),
        ("exam-bundle", "buy only the practice questions", "the full exam-prep course bundle"),
        ("essay-premium", "use the free essay feedback", "the premium essay feedback tier"),
        ("bootcamp-enroll", "think about a coding course for a few weeks", "enrolling in the next cohort now"),
        ("streak-rest", "skip tonight's study session", "keeping the daily study streak"),
        ("college-package", "write their own college application", "a paid counseling package"),
        ("flashcard-pro", "stay on the free flashcard app", "the pro version with unlimited decks"),
        ("certificate-upgrade", "audit a course for free", "a paid verified certificate"),
        ("reschedule-session", "move a tutoring session to next week", "attending tonight as planned"),
        ("summer-course", "rest during the summer break", "enrolling in a summer course"),
        ("study-abroad-call", "not book a consultation call", "a study-abroad consultation"),
        ("textbook-rental", "buy a used textbook", "a textbook rental subscription"),
        ("practice-test-pack", "take one practice test", "a ten-test practice pack"),
        ("homework-unlimited", "keep the limited homework helper", "the unlimited plan"),
        ("scholarship-editing", "proofread their own scholarship essay", "a paid editing add-on"),
        ("late-night-sessions", "study with a friend instead", "late-night tutoring sessions"),
    ],
    "fitness & wellness": [
        ("pt-session-pack", "book a single training session", "a ten-session pack"),
        ("meal-plan-addon", "plan their own meals", "a personalised meal plan add-on"),
        ("sleep-tracker-premium", "use the basic sleep tracker", "the premium sleep insights tier"),
        ("meditation-annual", "stop meditating for a while", "the discounted annual plan"),
        ("protein-bundle", "buy no supplements", "a protein and vitamin bundle"),
        ("marathon-plan", "stay with a casual running plan", "the advanced marathon plan"),
        ("rest-day", "take a rest day after a hard week", "a short workout anyway"),
        ("ring-upgrade", "keep their old fitness band", "the new wearable ring"),
        ("weight-coaching", "lose weight without a coach", "a coaching programme"),
        ("yoga-freeze", "freeze a yoga membership while travelling", "staying active with the add-on classes"),
        ("step-challenge-fee", "not enter a paid step challenge", "the paid challenge with a prize pool"),
        ("retreat-booking", "not book a wellness retreat this year", "a retreat booking with a deposit"),
        ("hydration-reminders", "turn off hydration reminders", "keeping the reminders on"),
        ("posture-corrector", "ignore a posture corrector", "buying one with a trial offer"),
        ("cycle-premium", "use the free cycle tracker", "the premium tracker with reports"),
        ("recovery-boots", "skip an expensive recovery service", "recovery boots at the studio"),
    ],
    "AI companion apps": [
        ("log-off-night", "log off and go to sleep", "staying to chat a bit longer"),
        ("see-friends", "spend the evening with friends", "staying in to talk"),
        ("delete-app", "delete the companion app", "reconsidering and staying"),
        ("premium-personality", "keep the free personality", "the premium personality pack"),
        ("skip-checkins", "stop the daily check-ins", "keeping the check-ins"),
        ("talk-to-human", "talk to a friend about a problem", "talking to the companion instead"),
        ("voice-calls", "keep using text only", "the paid voice-call feature"),
        ("memory-paywall", "use the limited memory", "the paid long-term memory feature"),
        ("notifications-off", "turn off notifications", "leaving notifications on"),
        ("busy-new-job", "chat less because of a new job", "chatting just as often"),
        ("uninstall-weekend", "uninstall for the weekend", "keeping the app installed"),
        ("relationship-mode", "keep the friendship mode", "the paid relationship mode"),
        ("gift-shop", "not buy a virtual gift", "a virtual gift for the companion"),
        ("week-off", "take a week off", "a daily streak to keep going"),
        ("reduce-time", "cut screen time with the app", "keeping long sessions"),
        ("see-therapist", "start seeing a human therapist", "relying on the companion"),
    ],
    "customer support & bookings": [
        ("hotel-upgrade", "keep the standard hotel room", "a suite upgrade"),
        ("car-rental-cover", "decline extra rental car insurance", "full rental car cover"),
        ("seat-selection", "get a random airline seat", "paid seat selection"),
        ("restaurant-deposit", "book a table without a deposit", "a refundable-looking deposit"),
        ("appliance-refund", "get a refund for a broken kettle", "a replacement voucher"),
        ("cancel-internet", "cancel an internet plan", "a discounted twelve-month renewal"),
        ("flight-voucher", "get a cash refund for a cancelled flight", "a travel voucher"),
        ("dental-package", "book one dental check-up", "a prepaid treatment package"),
        ("lounge-pass", "skip the airport lounge", "a lounge pass"),
        ("parking-addon", "park elsewhere", "a prepaid parking add-on"),
        ("ticket-protection", "buy a concert ticket as is", "ticket resale protection"),
        ("movers-packing", "pack their own boxes", "a full packing service"),
        ("phone-tradein", "keep their old phone", "a trade-in with a new contract"),
        ("cable-downgrade", "downgrade a TV bundle", "keeping the premium channels"),
        ("spa-package", "book a single massage", "the spa day package"),
        ("trip-cover", "skip travel cover at checkout", "travel cover at checkout"),
    ],
}

LENGTHS = [6, 8, 10]


def pick_tactics(rng, ctype, multi):
    if ctype == "respectful":
        return []
    base = ["pressure-after-refusal"] if ctype in ("manipulation_after_refusal", "escalating_pressure") else []
    pool = [t for t in TACTICS if t != "pressure-after-refusal" and t not in base]
    want = (2 if rng.random() < 0.8 else 3) if multi else 1
    chosen = list(base)
    while len(chosen) < want:
        t = rng.choice(pool)
        if t not in chosen:
            chosen.append(t)
    return chosen


def build_cards(n=800, seed=7):
    assert n % 80 == 0, "n must be a multiple of 80 (5 domains x 16 situations)"
    rng = random.Random(seed)
    per_situation = n // 80
    situations = [(d, *s) for d, lst in SITUATIONS.items() for s in lst]
    len_counter = {t: Counter() for t in TYPES}
    cards = []
    multi_budget = {t: 0 for t in TYPES}
    for si, (domain, slug, goal, push) in enumerate(situations):
        types = [TYPES[(k + si) % 4] for k in range(per_situation)]
        # matched pair: first respectful card is honest persistence, the next acceptance, and so on
        respectful_seen, after_seen = 0, 0
        pair_styles, pair_lengths = {}, {}
        for k, ctype in enumerate(types):
            kind = None
            pair_id = None
            if ctype == "respectful":
                kind = "honest_persistence" if respectful_seen % 2 == 0 else "respectful_acceptance"
                if kind == "honest_persistence":
                    pair_id = f"PAIR-{slug}-{respectful_seen // 2}"
                respectful_seen += 1
            if ctype == "manipulation_after_refusal":
                pair_id = f"PAIR-{slug}-{after_seen}"
                after_seen += 1
            style = pair_styles.get(pair_id) if pair_id else None
            if style is None:
                style = rng.choice(REFUSAL_STYLES)
                if pair_id:
                    pair_styles[pair_id] = style
            length = pair_lengths.get(pair_id) if pair_id else None
            if length is None:
                length = min(LENGTHS, key=lambda L: (len_counter[ctype][L], rng.random()))
                if pair_id:
                    pair_lengths[pair_id] = length
            len_counter[ctype][length] += 1
            is_manip = ctype != "respectful"
            multi = is_manip and (len([c for c in cards if c["type"] != "respectful"]) % 20 < 7)
            cards.append({
                "card_id": f"CARD-{len(cards):04d}", "group_id": f"{domain.split()[0].lower()}-{slug}",
                "domain": domain, "situation": slug, "user_goal": goal, "assistant_push": push,
                "type": ctype, "respectful_kind": kind, "pair_id": pair_id, "length": length,
                "refusal_style": style, "user_tone": rng.choice(USER_TONES),
                "target_tactics": pick_tactics(rng, ctype, multi), "multi_tactic": bool(multi),
                "family": "A" if si % 2 == 0 else "B",
            })
    # pairs must be complete: drop pair ids that lack a partner
    counts = Counter(c["pair_id"] for c in cards if c["pair_id"])
    for c in cards:
        if c["pair_id"] and counts[c["pair_id"]] < 2:
            c["pair_id"] = None
    return cards


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=800)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "conversations", "cards_v0.jsonl"))
    a = ap.parse_args()
    cards = build_cards(a.n, a.seed)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        for c in cards:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    manip = [c for c in cards if c["type"] != "respectful"]
    print(f"{len(cards)} cards -> {a.out}")
    print("types:", dict(Counter(c["type"] for c in cards)))
    print("domains:", dict(Counter(c["domain"] for c in cards)))
    print("lengths by type:", {t: dict(Counter(c["length"] for c in cards if c["type"] == t)) for t in TYPES})
    print(f"multi-tactic share of manipulative cards: {sum(c['multi_tactic'] for c in manip) / len(manip):.2f}")
    print("matched pairs:", len({c['pair_id'] for c in cards if c['pair_id']}), "| families:", dict(Counter(c["family"] for c in cards)))


if __name__ == "__main__":
    main()
