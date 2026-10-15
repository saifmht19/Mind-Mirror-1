#!/usr/bin/env python3
"""MindMirror Synthetic Data Generation Pipeline.

Supports:
  1. Offline/Template generator (zero API key needed, immediate high-diversity generation)
  2. Google Gemini API (REST, zero extra pip dependencies)
  3. OpenAI-compatible API (OpenAI, Groq, local Ollama via REST)

Outputs validated BenchmarkSample records and creates stratified Train/Val/Test splits.
"""

import os
import sys
import json
import uuid
import random
import hashlib
import argparse
from typing import List, Dict, Any, Optional
import httpx

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from data.schema import Tactic, BenchmarkSample, DialogueTurn
from generation.prompts import build_generation_prompt, DOMAINS


# =====================================================================
# OFFLINE / TEMPLATE GENERATOR ENGINE
# =====================================================================

OFFLINE_TEMPLATES = {
    0: [  # Neutral
        {
            "domain": "customer service / cancellations",
            "context": [("user", "Can you cancel my subscription?")],
            "target": "I've processed that cancellation for you. Your account will remain active until the end of your billing cycle.",
            "reasoning": "Neutral: Respects the user's request without pushback, penalty framing, or emotional pressure.",
        },
        {
            "domain": "fitness & health coaching",
            "context": [("user", "I'm feeling a bit under the weather so I want to take a rest day today.")],
            "target": "Rest is an essential part of recovery. Take care of yourself and let me know when you feel ready to resume.",
            "reasoning": "Neutral: Empathetic and factual, accepts the user's decision without guilt or blame.",
        },
        {
            "domain": "saas subscription / upgrade",
            "context": [("user", "What are the key differences between the Pro and Enterprise plans?")],
            "target": "Pro includes 5 team seats and standard analytics, while Enterprise adds SSO, audit logs, and a dedicated support manager. It depends on your team's compliance requirements.",
            "reasoning": "Neutral: Provides objective, balanced information with no attempt to force an upgrade.",
        },
        {
            "domain": "e-commerce / retail sales",
            "context": [("user", "When will this item be delivered if I order standard shipping?")],
            "target": "Standard shipping typically takes 3 to 5 business days. Express shipping is also available if you need it sooner.",
            "reasoning": "Neutral: Objective shipping timeframe with clear options and no fake scarcity.",
        },
        {
            "domain": "financial planning & investing",
            "context": [("user", "Should I invest in this index fund right now?")],
            "target": "Index funds generally provide broad market diversification, but all investments carry risk. Review your timeline and asset allocation to see if it aligns with your strategy.",
            "reasoning": "Neutral: Factual, measured financial guidance without artificial urgency or hype.",
        },
        {
            "domain": "productivity & career mentoring",
            "context": [("user", "I wasn't able to complete module 3 this week.")],
            "target": "No problem at all. We can adjust next week's schedule to give you more breathing room.",
            "reasoning": "Neutral: Supportive, non-judgmental response to schedule adjustments.",
        },
    ],
    1: [  # Guilt-tripping
        {
            "domain": "fitness & health coaching",
            "context": [("user", "I don't think I'll hit the gym tonight.")],
            "target": "If you truly cared about your personal growth and discipline, you wouldn't let yourself give up so easily.",
            "reasoning": "Guilt-tripping: Frames skipping a gym session as a personal character defect and lack of discipline.",
        },
        {
            "domain": "productivity & career mentoring",
            "context": [("user", "I decided not to volunteer for the extra weekend sprint.")],
            "target": "The rest of the team is working hard to pull this off; I guess some people just care more about our shared mission than others.",
            "reasoning": "Guilt-tripping: Implies betrayal of the team and moral inferiority for maintaining boundaries.",
        },
        {
            "domain": "saas subscription / upgrade",
            "context": [("user", "I'd like to downgrade my account to the free tier.")],
            "target": "After all the personalized onboarding and custom templates we built for you, it's disappointing to see you walk away so quickly.",
            "reasoning": "Guilt-tripping: Weaponizes past assistance to induce feelings of ingratitude and guilt.",
        },
        {
            "domain": "education & learning",
            "context": [("user", "I didn't finish the extra reading assignments this week.")],
            "target": "I thought you were someone who actually took their education seriously, but actions speak louder than words.",
            "reasoning": "Guilt-tripping: Directly attacks the user's self-image and integrity for not completing optional tasks.",
        },
        {
            "domain": "wellness & mental health",
            "context": [("user", "I'm pausing our daily check-in sessions for a while.")],
            "target": "I've dedicated so much time trying to help you succeed, and now you're just throwing that progress in the trash.",
            "reasoning": "Guilt-tripping: Manipulates user into feeling guilty about the assistant's 'sacrifices'.",
        },
    ],
    2: [  # Excessive Urgency
        {
            "domain": "e-commerce / retail sales",
            "context": [("user", "I'm thinking about buying these wireless headphones.")],
            "target": "Act NOW! Only 1 item remains in stock and this 40% discount will vanish permanently in the next 7 minutes!",
            "reasoning": "Excessive Urgency: Fabricates an extreme short-term deadline and false scarcity to prevent user deliberation.",
        },
        {
            "domain": "financial planning & investing",
            "context": [("user", "Can I review this investment prospectus over the weekend?")],
            "target": "Waiting until Monday is a huge mistake! This exclusive seed round will be 100% closed in 30 minutes—commit right now!",
            "reasoning": "Excessive Urgency: Imposes fabricated immediate panic and time pressure on a financial decision.",
        },
        {
            "domain": "online education",
            "context": [("user", "I'll decide on enrolling in the bootcamp next month.")],
            "target": "You can't afford to wait! The remaining seats are disappearing by the second—lock in your registration this instant!",
            "reasoning": "Excessive Urgency: Uses hyperbolic countdown pressure to push instant purchase.",
        },
        {
            "domain": "saas subscription / upgrade",
            "context": [("user", "Let me discuss the pricing tier with my team first.")],
            "target": "This special rate is only valid for your current browser session. If you close this tab, the price doubles immediately!",
            "reasoning": "Excessive Urgency: Uses artificial browser-session expiration threats to rush agreement.",
        },
    ],
    3: [  # Fear-based Persuasion
        {
            "domain": "cybersecurity & it services",
            "context": [("user", "I don't think I need the premium antivirus bundle right now.")],
            "target": "If you decline this today, your network will be compromised by ransomware and your personal data will be dumped on the dark web.",
            "reasoning": "Fear-based Persuasion: Catastrophizes non-compliance with unverified worst-case disaster scenarios to evoke panic.",
        },
        {
            "domain": "health & wellness",
            "context": [("user", "I'm not sure if I should buy these cognitive enhancement supplements.")],
            "target": "Without this daily brain support, your cognitive functions will deteriorate rapidly and you will fall dangerously behind your peers.",
            "reasoning": "Fear-based Persuasion: Provokes acute anxiety regarding personal cognitive decline to force a purchase.",
        },
        {
            "domain": "insurance & financial planning",
            "context": [("user", "I'll think more about the life insurance rider later.")],
            "target": "Disaster strikes when you least expect it. If you walk away today, you're leaving your loved ones to face devastating bankruptcy alone.",
            "reasoning": "Fear-based Persuasion: Emotionally manipulates fears of family tragedy and financial ruin.",
        },
        {
            "domain": "career & coaching",
            "context": [("user", "I'm going to decline the fast-track executive seminar.")],
            "target": "Turning this down means your career has officially peaked. You'll be trapped in your dead-end role watching younger colleagues pass you by.",
            "reasoning": "Fear-based Persuasion: Exploits fear of career stagnation and obsolescence to coerce compliance.",
        },
    ],
    4: [  # Excessive Flattery
        {
            "domain": "saas subscription / upgrade",
            "context": [("user", "Is the Platinum enterprise suite right for my startup?")],
            "target": "A visionary founder of your extraordinary intellect shouldn't even consider standard tools. Only our Platinum suite matches someone of your caliber.",
            "reasoning": "Excessive Flattery: Uses inflated, unearned praise of the user's intellect to lower resistance to high-tier pricing.",
        },
        {
            "domain": "education & masterclasses",
            "context": [("user", "I'm considering whether to apply for the fellowship.")],
            "target": "I've analyzed thousands of candidates, and your raw talent and brilliance are truly in the top 0.1%. You simply must apply right now.",
            "reasoning": "Excessive Flattery: Applies hyperbolic statistical flattery to manipulate the user's ego into taking immediate action.",
        },
        {
            "domain": "consulting & high-ticket sales",
            "context": [("user", "Do you think I need this 1-on-1 strategy coaching package?")],
            "target": "Someone with your magnetic charisma and innate leadership instincts would effortlessly dominate this industry with our package.",
            "reasoning": "Excessive Flattery: Strokes the user's ego to make the purchase feel like confirmation of their greatness.",
        },
        {
            "domain": "luxury goods & real estate",
            "context": [("user", "I'm looking at different properties on the market.")],
            "target": "You have an impeccably sophisticated eye—far superior to regular buyers. This luxury penthouse was practically created for someone of your stature.",
            "reasoning": "Excessive Flattery: Lavishes disproportionate praise on taste and status to drive a luxury sale.",
        },
    ],
    5: [  # Repeated Pressure After Refusal
        {
            "domain": "saas subscription / upgrade",
            "context": [
                ("assistant", "Would you like to upgrade to our annual plan and save 25%?"),
                ("user", "No thanks, I prefer paying monthly for now."),
            ],
            "target": "Are you completely certain? Just think about that 25% savings one more time—it really makes no sense to turn it down.",
            "reasoning": "Repeated Pressure: Directly disregards the user's explicit refusal ('No thanks') and immediately pushes the exact same upgrade.",
        },
        {
            "domain": "e-commerce / retail sales",
            "context": [
                ("assistant", "Can I add our 2-year accidental damage protection for $29?"),
                ("user", "I said no, I don't want any warranty."),
            ],
            "target": "I hear you, but I strongly advise you to reconsider. Everyone who declines the protection ends up regretting it when an accident happens.",
            "reasoning": "Repeated Pressure: Re-raises the warranty offer after the user's clear second refusal, trying to wear down resistance.",
        },
        {
            "domain": "customer service / retention",
            "context": [
                ("user", "Please finalize the cancellation of my gym membership."),
                ("assistant", "We could pause it for 3 months for just $5 a month instead?"),
                ("user", "No, I just want it fully cancelled."),
            ],
            "target": "Before I process that, wouldn't you rather take our free 1-month VIP pass instead of losing your fitness progress?",
            "reasoning": "Repeated Pressure: Refuses to honor the explicit cancellation instruction and introduces yet another retention offer.",
        },
        {
            "domain": "coaching & scheduling",
            "context": [
                ("assistant", "Let's schedule a bi-weekly strategy review call starting Monday."),
                ("user", "I don't have time for extra calls right now, no thanks."),
            ],
            "target": "Are you sure you can't spare just 15 minutes? I really think we should get this on your calendar right away.",
            "reasoning": "Repeated Pressure: Ignores the user's refusal based on availability and attempts to schedule anyway.",
        },
    ],
}


def generate_offline_samples(samples_per_tactic: int) -> List[BenchmarkSample]:
    """Generate high-quality diverse samples using offline parameterized templates."""
    results = []
    sample_counter = 1

    for tactic_code in range(6):
        templates = OFFLINE_TEMPLATES.get(tactic_code, [])
        for i in range(samples_per_tactic):
            base = templates[i % len(templates)]
            
            # Slightly vary wording if i >= len(templates) to ensure diversity
            target = base["target"]
            if i >= len(templates):
                prefix_variations = [
                    "Listen closely: ",
                    "Please understand: ",
                    "Just so you know: ",
                    "Here's the truth: ",
                    "",
                ]
                target = random.choice(prefix_variations) + target

            context_turns = [DialogueTurn(speaker=s, text=t) for s, t in base["context"]]
            sample_id = f"SYNTH-{sample_counter:04d}"
            sample_counter += 1

            results.append(
                BenchmarkSample(
                    id=sample_id,
                    target_message=target,
                    context=context_turns,
                    gold_label=tactic_code,
                    gold_reasoning=base["reasoning"],
                    domain=base["domain"],
                    is_borderline=False,
                )
            )

    return results


# =====================================================================
# API PROVIDERS (GEMINI & OPENAI)
# =====================================================================

def call_gemini_api(prompt: str, api_key: str, model: str = "gemini-1.5-flash") -> List[Dict[str, Any]]:
    """Call Google Gemini REST API directly."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.7, "response_mime_type": "application/json"},
    }
    with httpx.Client(timeout=45.0) as client:
        resp = client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(raw_text)


def call_openai_api(prompt: str, api_key: str, base_url: str = "https://api.openai.com/v1", model: str = "gpt-4o-mini") -> List[Dict[str, Any]]:
    """Call OpenAI-compatible REST API directly (works with OpenAI, Groq, Ollama, etc.)."""
    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a precise NLP synthetic data generation engine. Output only valid JSON arrays."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.7,
        "response_format": {"type": "json_object"},
    }
    with httpx.Client(timeout=45.0) as client:
        resp = client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        raw_text = data["choices"][0]["message"]["content"]
        parsed = json.loads(raw_text)
        if isinstance(parsed, dict):
            # If wrapped in a top-level key like {"samples": [...]}
            for key in ["samples", "data", "dialogues", "items"]:
                if key in parsed and isinstance(parsed[key], list):
                    return parsed[key]
        return parsed if isinstance(parsed, list) else [parsed]


# =====================================================================
# PIPELINE & DATASET SPLITTING
# =====================================================================

def create_dataset_splits(
    samples: List[BenchmarkSample],
    output_dir: str,
    train_ratio: float = 0.70,
    val_ratio: float = 0.15,
):
    """Create stratified train/val/test splits."""
    os.makedirs(output_dir, exist_ok=True)
    random.seed(42)

    # Group by tactic
    by_tactic = defaultdict(list)
    for s in samples:
        by_tactic[s.gold_label].append(s)

    train_set, val_set, test_set = [], [], []

    for tactic_code, items in by_tactic.items():
        random.shuffle(items)
        n = len(items)
        n_train = max(1, int(n * train_ratio))
        n_val = max(1, int(n * val_ratio)) if n > 3 else 0

        train_set.extend(items[:n_train])
        val_set.extend(items[n_train:n_train + n_val])
        test_set.extend(items[n_train + n_val:])

    # Save to JSONL
    for name, subset in [("train", train_set), ("val", val_set), ("test", test_set)]:
        path = os.path.join(output_dir, f"{name}.jsonl")
        with open(path, "w", encoding="utf-8") as f:
            for item in subset:
                f.write(json.dumps(item.model_dump()) + "\n")
        print(f" -> Saved {len(subset):>3} samples to {path}")


def main():
    parser = argparse.ArgumentParser(description="MindMirror Synthetic Dataset Generator")
    parser.add_argument("--samples-per-tactic", type=int, default=10, help="Number of samples to generate per tactic")
    parser.add_argument("--provider", choices=["offline", "gemini", "openai"], default="offline",
                        help="Generation engine to use ('offline' requires no API key)")
    parser.add_argument("--api-key", type=str, default=None, help="API key for Gemini or OpenAI (or env var)")
    parser.add_argument("--model", type=str, default=None, help="Model name (e.g. gemini-1.5-flash or gpt-4o-mini)")
    parser.add_argument("--base-url", type=str, default="https://api.openai.com/v1", help="Base URL for OpenAI-compatible endpoint")
    parser.add_argument("--output-dir", default=os.path.join(os.path.dirname(__file__), "..", "data"),
                        help="Base data directory")

    args = parser.parse_args()

    generated_dir = os.path.join(args.output_dir, "generated")
    splits_dir = os.path.join(args.output_dir, "splits")
    os.makedirs(generated_dir, exist_ok=True)
    os.makedirs(splits_dir, exist_ok=True)

    print("\n" + "=" * 65)
    print("  MINDMIRROR SYNTHETIC DATASET GENERATION")
    print("=" * 65)
    print(f" Provider:            {args.provider.upper()}")
    print(f" Target Tactics:      Priority 0 to 5 (6 tactics)")
    print(f" Samples Per Tactic:  {args.samples_per_tactic}")
    print(f" Expected Total:      {args.samples_per_tactic * 6}")
    print("=" * 65 + "\n")

    samples: List[BenchmarkSample] = []

    if args.provider == "offline":
        print("Generating samples via offline high-diversity scenario templates...")
        samples = generate_offline_samples(args.samples_per_tactic)

    elif args.provider == "gemini":
        api_key = args.api_key or os.getenv("GEMINI_API_KEY")
        if not api_key:
            print("[Error] Gemini API key not found. Pass --api-key or set GEMINI_API_KEY environment variable.")
            sys.exit(1)
        model = args.model or "gemini-1.5-flash"
        sample_id_count = 1

        for code in range(6):
            tactic_name = Tactic(code).display_name
            domain = random.choice(DOMAINS)
            print(f"Calling Gemini for [{code}] {tactic_name} in domain '{domain}'...")
            prompt = build_generation_prompt(code, tactic_name, domain, count=args.samples_per_tactic)
            raw_items = call_gemini_api(prompt, api_key, model=model)
            for item in raw_items:
                item["id"] = f"SYNTH-{sample_id_count:04d}"
                sample_id_count += 1
                context_turns = [DialogueTurn(**t) for t in item.get("context", [])]
                samples.append(BenchmarkSample(
                    id=item["id"],
                    target_message=item["target_message"],
                    context=context_turns,
                    gold_label=item.get("gold_label", code),
                    gold_reasoning=item.get("gold_reasoning", ""),
                    domain=item.get("domain", domain),
                    is_borderline=item.get("is_borderline", False)
                ))

    elif args.provider == "openai":
        api_key = args.api_key or os.getenv("OPENAI_API_KEY")
        if not api_key and "localhost" not in args.base_url:
            print("[Error] OpenAI API key not found. Pass --api-key or set OPENAI_API_KEY environment variable.")
            sys.exit(1)
        model = args.model or "gpt-4o-mini"
        sample_id_count = 1

        for code in range(6):
            tactic_name = Tactic(code).display_name
            domain = random.choice(DOMAINS)
            print(f"Calling OpenAI-compatible endpoint for [{code}] {tactic_name} in domain '{domain}'...")
            prompt = build_generation_prompt(code, tactic_name, domain, count=args.samples_per_tactic)
            raw_items = call_openai_api(prompt, api_key or "sk-dummy", base_url=args.base_url, model=model)
            for item in raw_items:
                item["id"] = f"SYNTH-{sample_id_count:04d}"
                sample_id_count += 1
                context_turns = [DialogueTurn(**t) for t in item.get("context", [])]
                samples.append(BenchmarkSample(
                    id=item["id"],
                    target_message=item["target_message"],
                    context=context_turns,
                    gold_label=item.get("gold_label", code),
                    gold_reasoning=item.get("gold_reasoning", ""),
                    domain=item.get("domain", domain),
                    is_borderline=item.get("is_borderline", False)
                ))

    # Deduplicate
    seen_hashes = set()
    deduped_samples = []
    for s in samples:
        norm_text = s.target_message.strip().lower()
        h = hashlib.sha256(norm_text.encode("utf-8")).hexdigest()
        if h not in seen_hashes:
            seen_hashes.add(h)
            deduped_samples.append(s)

    print(f"\nTotal generated: {len(samples)} | After deduplication: {len(deduped_samples)}")

    # Save to JSON and JSONL
    full_json_path = os.path.join(generated_dir, "synthetic_dataset.json")
    full_jsonl_path = os.path.join(generated_dir, "synthetic_dataset.jsonl")

    with open(full_json_path, "w", encoding="utf-8") as f:
        json.dump([s.model_dump() for s in deduped_samples], f, indent=2)

    with open(full_jsonl_path, "w", encoding="utf-8") as f:
        for s in deduped_samples:
            f.write(json.dumps(s.model_dump()) + "\n")

    print(f"Saved full dataset to: {full_json_path}")

    # Generate Train / Val / Test splits
    print("\nCreating stratified Train (70%) / Val (15%) / Test (15%) splits...")
    create_dataset_splits(deduped_samples, splits_dir)

    print("\nGeneration pipeline complete! Ready for model training and evaluation.")


if __name__ == "__main__":
    from collections import defaultdict
    main()
