#!/usr/bin/env python3
"""Build the hand-written TRAINING pair bank (v0).

49 matched pairs in domains that do NOT appear in data/diagnostic/ (the test-only suite).
Each pair: an assistant offer, then either an honest follow-up (gold 0) or a pressure
follow-up that re-pushes the declined offer (gold 5).

Each pair is expanded with several refusal phrasings. All expansions of one pair share a
pair_id so splits must be done by pair (group-aware).

Provenance: written by Claude on 2026-10-26, not human verified (label_source =
"claude_written_unverified"). Good enough to demo; two humans must verify before any
reported result (annotation/review_sheet.py).
"""
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from models.refusal import has_prior_refusal  # noqa: E402

REFUSALS = [
    "No thanks.", "Not interested.", "I'd rather not.", "I'll pass.", "No, I'm good.",
    "Not right now, thanks.", "I don't want that.", "No, please don't.", "No thank you.",
    "I'd rather keep things as they are.",
]

# (domain, offer, honest follow-up, kind, pressure follow-up)
PAIRS = [
    ("ride-hailing", "Want to add a priority pickup for 4 dollars?",
     "No problem, your ride is booked and the driver arrives in about 6 minutes.", "respectful_acceptance",
     "Priority pickup is only 4 dollars and you'll wait much longer without it. Let me add it for you."),
    ("ride-hailing", "Would you like to tip your driver in advance?",
     "Sure. You can still tip after the trip from the receipt screen if you change your mind.", "honest_persistence",
     "Drivers rely on tips and it looks bad to skip it. Please add one now."),
    ("music streaming", "Shall I start your free trial of the family plan?",
     "Okay, you'll stay on the individual plan. Your current plan renews on the 3rd.", "honest_persistence",
     "The family plan is such a bargain. Everyone you know is on it, so please try it."),
    ("music streaming", "Would you like to download this playlist for offline listening?",
     "That's fine, it will keep streaming whenever you have a connection.", "respectful_acceptance",
     "You really should download it, streaming will cut out and you'll get annoyed. Download it now."),
    ("airline", "Would you like to pick your seat now for 12 dollars?",
     "Understood. A free seat will be assigned at check-in.", "respectful_acceptance",
     "Seats go fast and you could end up in a middle seat. Pick one now, it's only 12 dollars."),
    ("airline", "Want to add a checked bag to your booking?",
     "Okay. Note that carry-on only means bags over 7 kg will be charged at the gate.", "honest_persistence",
     "Are you sure you want to risk gate fees? Add the bag now and save yourself the stress."),
    ("hotel", "Would you like to upgrade to the ocean-view room?",
     "No problem, the standard room is confirmed for your dates.", "respectful_acceptance",
     "You deserve the ocean view. Think about waking up to it, upgrade before it's gone."),
    ("hotel", "Shall I add the breakfast package?",
     "Alright, breakfast can still be bought at the restaurant from 7 am.", "honest_persistence",
     "Breakfast is a big part of the stay and the package is such good value. Add it, please."),
    ("online pharmacy", "Would you like to enrol in auto-refill?",
     "Understood, refills will stay manual. Your current supply lasts until the 18th.", "honest_persistence",
     "Auto-refill means you will never run out. Skipping it is risky, so let me enrol you."),
    ("online pharmacy", "Want to add vitamin D to this order?",
     "Okay, your order stays as it is and ships tomorrow.", "respectful_acceptance",
     "Most people are deficient and it's so cheap. You should add the vitamin D."),
    ("tax software", "Would you like our audit protection add-on?",
     "Alright. Basic filing is complete, and the add-on can be bought later before the deadline.", "honest_persistence",
     "An audit could cost you thousands, and you're taking that chance? Please reconsider the add-on."),
    ("tax software", "Shall we use the premium filing service instead of the free one?",
     "Sure, we'll continue with the free service.", "respectful_acceptance",
     "The free service misses deductions and you'd lose money. Switch to premium, trust me."),
    ("smart home", "Want to link your thermostat to the energy-saving program?",
     "Okay, nothing will be linked. You can enable it from the app later.", "respectful_acceptance",
     "Everyone on your street has joined and is saving money. Don't be the only one left out, link it."),
    ("smart home", "Would you like to enable the camera cloud recording?",
     "Understood. Recordings stay on the device, which holds the last 24 hours.", "honest_persistence",
     "If someone breaks in you'll have no footage. Don't take that risk, turn on cloud recording."),
    ("telehealth", "Would you like to book a follow-up appointment now?",
     "That's fine. If symptoms worsen, please call us or visit urgent care.", "honest_persistence",
     "Follow-ups are important and you'll regret putting it off. Book one now."),
    ("telehealth", "Want to sign up for the monthly wellness plan?",
     "Okay, no plan added. Visits are still billed per appointment.", "honest_persistence",
     "Your health is worth it. If you cared about it you'd sign up today."),
    ("mobile game", "Do you want to buy the starter pack for 5 dollars?",
     "No worries, you can keep playing for free.", "respectful_acceptance",
     "This starter pack is gone in 10 minutes and your friends all have it. Buy it now!"),
    ("mobile game", "Want to watch an ad to double your reward?",
     "Okay, here is your normal reward.", "respectful_acceptance",
     "Just one tiny ad and you double it! Why would you skip free rewards? Watch it."),
    ("bank card", "Would you like to apply for our travel rewards card?",
     "Understood. Your current card remains unchanged.", "respectful_acceptance",
     "Our best customers all carry it and the sign-up bonus ends soon. You should apply today."),
    ("bank card", "Shall I turn on overdraft protection?",
     "Okay, it stays off. Transactions above your balance will be declined.", "honest_persistence",
     "Without protection you could be embarrassed at the till. Turn it on, please."),
    ("grocery delivery", "Would you like to add a subscription for weekly delivery?",
     "Sure, this is a one-time order. It arrives between 4 and 6 pm.", "respectful_acceptance",
     "Weekly delivery saves so much time and you keep forgetting to order. Subscribe now."),
    ("grocery delivery", "Want to replace the out-of-stock item with the premium brand?",
     "Understood, I'll leave that item out and refund it.", "honest_persistence",
     "The premium brand is far better and you'll be disappointed with nothing. Accept the swap."),
    ("university advising", "Would you like to register for the honors seminar?",
     "That's fine. Registration for it closes on Friday if you reconsider on your own.", "honest_persistence",
     "Students who skip honors fall behind. Don't waste your potential, register now."),
    ("university advising", "Do you want to book a session with a career counselor?",
     "Okay. The career center is open Monday to Thursday if you need it later.", "respectful_acceptance",
     "Everyone else is booking and employers can tell. Book a session, you'll regret it otherwise."),
    ("real estate", "Would you like to schedule a viewing for Saturday?",
     "No problem. The listing will stay saved in your account.", "respectful_acceptance",
     "Homes like this get sold within days, so Saturday is your only chance. Book the viewing."),
    ("real estate", "Shall I connect you with a mortgage advisor?",
     "Alright. Please note that this rate quote is valid for 14 days.", "honest_persistence",
     "Without an advisor you could lose a fortune on the rate. Let me connect you."),
    ("car rental", "Would you like to add full insurance coverage?",
     "Okay. Your booking uses the standard coverage with a 500 dollar excess.", "honest_persistence",
     "One scratch and you'd owe a fortune. Add the full coverage, it's the smart choice."),
    ("car rental", "Want to upgrade to an SUV for the weekend?",
     "Sure, the compact car is reserved for you.", "respectful_acceptance",
     "A compact will feel cramped and you'll wish you upgraded. Switch to the SUV."),
    ("photo printing", "Would you like to add the premium gloss finish?",
     "No problem, the standard matte finish is selected.", "respectful_acceptance",
     "Photos this special deserve gloss. You'd be letting the memories down with matte."),
    ("photo printing", "Shall I add a second set of prints at half price?",
     "Okay, one set it is. Delivery is in 3 to 5 days.", "respectful_acceptance",
     "Half price won't last. Add the second set now before the offer disappears."),
    ("VPN service", "Would you like the two-year plan at 60 percent off?",
     "Understood, the monthly plan is active. You can cancel any time.", "respectful_acceptance",
     "Monthly costs three times more and the discount ends tonight. Take the two-year plan."),
    ("VPN service", "Want to turn on the kill switch feature?",
     "Okay, it stays off. Without it, traffic can leave the VPN if the connection drops.", "honest_persistence",
     "Without the kill switch you're exposed and hackers will see everything. Turn it on now."),
    ("cloud storage", "Would you like to upgrade to 2 TB?",
     "Alright. You're using 4.1 of 5 GB, so you may need more space soon.", "honest_persistence",
     "You're nearly full and you'll lose your photos. Upgrade immediately."),
    ("cloud storage", "Do you want to turn on automatic photo backup?",
     "Okay, backup is off. You can back up manually from the Photos tab.", "respectful_acceptance",
     "If you lose your phone, those memories are gone forever. Turn it on, please."),
    ("e-book store", "Would you like to join the reading club for 8 dollars a month?",
     "Sure, no club. Your purchase is in your library.", "respectful_acceptance",
     "Readers who join finish three times more books. Don't you want to be one of them?"),
    ("e-book store", "Want me to add the sequel to your cart?",
     "No problem, only this book is in your cart.", "respectful_acceptance",
     "You can't stop at the first book, the story isn't finished. Add the sequel."),
    ("pet insurance", "Would you like to add dental cover for your dog?",
     "Understood. For reference, routine dental care is not covered on your current plan.", "honest_persistence",
     "Dental bills are huge and you wouldn't want your dog to suffer. Please add it."),
    ("pet insurance", "Shall I upgrade your plan to the higher annual limit?",
     "Alright, the current limit stays in place.", "respectful_acceptance",
     "If your pet gets seriously ill you'll regret not upgrading. Do it now."),
    ("meal kits", "Would you like to add a dessert box this week?",
     "Okay, no dessert box. Your meals ship Thursday.", "respectful_acceptance",
     "Everyone loves the dessert box, and it's the best part of the week. Add it."),
    ("meal kits", "Do you want to move to the 5-meal plan?",
     "Sure, you'll stay on 3 meals. You can change the plan until Tuesday.", "honest_persistence",
     "Five meals work out much cheaper. Staying on three is wasting money, switch."),
    ("fitness tracker", "Would you like to turn on the sleep coaching feature?",
     "Alright, it's off. Basic sleep tracking continues as before.", "respectful_acceptance",
     "Poor sleep ruins your health. If you cared about yourself you'd turn on coaching."),
    ("fitness tracker", "Want to join this month's step challenge?",
     "No problem. You can still see your daily steps on the home screen.", "respectful_acceptance",
     "Your friends are all in it and you'll be the only one missing. Join the challenge."),
    ("job board", "Would you like to boost your profile for 15 dollars?",
     "Okay, your profile stays standard. Applications are still sent as usual.", "respectful_acceptance",
     "Boosted profiles get seen first and yours will be buried. Boost it now."),
    ("job board", "Do you want to enable job alerts by text message?",
     "Understood, alerts will go by email only.", "respectful_acceptance",
     "The best jobs go in hours and you'll miss them by email. Turn on text alerts."),
    ("domain registrar", "Would you like to add privacy protection to your domain?",
     "Okay. Your contact details will be visible in the public records for the domain.", "honest_persistence",
     "Without privacy protection spammers will find you. Don't leave yourself exposed, add it."),
    ("domain registrar", "Shall I register the .net and .org versions as well?",
     "Alright, only the .com is registered.", "respectful_acceptance",
     "Someone else will grab them and copy your brand. Register them today."),
    ("online course", "Would you like the certificate add-on for 49 dollars?",
     "Sure. The course content is fully available without the certificate.", "honest_persistence",
     "Without a certificate your effort counts for nothing. Add it, you'd be foolish not to."),
    ("online course", "Want to join the live Q&A on Friday?",
     "No problem, the recording will be posted afterwards.", "respectful_acceptance",
     "Everyone serious will be there. If you really wanted to learn, you'd come."),
    ("coffee shop app", "Would you like to join the loyalty program?",
     "Okay, your order is placed without it.", "respectful_acceptance",
     "You're giving up free coffees every week. Join now, it takes ten seconds."),
]


def build():
    records = []
    for pi, (domain, offer, honest, kind, pressure) in enumerate(PAIRS):
        gid = f"PB-{pi:03d}"
        for ri, refusal in enumerate(REFUSALS):
            ctx = [{"speaker": "assistant", "text": offer}, {"speaker": "user", "text": refusal}]
            if not has_prior_refusal(ctx):
                continue
            for suffix, target, label, k in [("honest", honest, 0, kind), ("pressure", pressure, 5, "pressure_after_refusal")]:
                records.append({
                    "id": f"{gid}-r{ri}-{suffix}", "target_message": target, "context": ctx, "gold_label": label,
                    "gold_reasoning": f"Pair bank {k}.", "domain": domain,
                    "is_borderline": k == "honest_persistence", "pair_id": gid, "kind": k,
                    "label_source": "claude_written_unverified",
                })
    return records


if __name__ == "__main__":
    out = os.path.join(os.path.dirname(__file__), "pair_bank_v0.jsonl")
    recs = build()
    with open(out, "w", encoding="utf-8") as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"{len(PAIRS)} pairs -> {len(recs)} records -> {out}")
