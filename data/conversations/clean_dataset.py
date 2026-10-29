
import json
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "data/conversations/raw/master_unverified.jsonl"
OUTPUT = ROOT / "data/conversations/processed/master_cleaned.jsonl"

DOMAIN_NAMES = {
    "AI companion apps": "AI companion apps",
    "Customer support": "Customer support & bookings",
    "Education & tutoring": "Education & tutoring",
}

SHOPPING_SOURCES = {"shopping_dataset.jsonl"}

records = []
counts = Counter()

with INPUT.open("r", encoding="utf-8-sig") as f:
    for line_number, line in enumerate(f, start=1):
        if not line.strip():
            continue

        record = json.loads(line)

        original_domain = record.get("domain")
        source = record.get("source_dataset")

        if source in SHOPPING_SOURCES:
            new_domain = "Shopping & subscriptions"
        elif original_domain in DOMAIN_NAMES:
            new_domain = DOMAIN_NAMES[original_domain]
        else:
            raise ValueError(
                f"Unknown domain at line {line_number}: "
                f"{original_domain!r}, source={source!r}"
            )

        record["original_domain"] = original_domain
        record["domain"] = new_domain

        records.append(record)
        counts[new_domain] += 1

OUTPUT.parent.mkdir(parents=True, exist_ok=True)

with OUTPUT.open("w", encoding="utf-8") as f:
    for record in records:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

print("Cleaning completed!")
print("Total conversations:", len(records))
print("Domain distribution:")

for domain, count in sorted(counts.items()):
    print(f"  {domain}: {count}")

print("Saved to:", OUTPUT)
