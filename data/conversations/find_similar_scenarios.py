
import json
import csv
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "data/conversations/processed/master_cleaned.jsonl"
OUTPUT = ROOT / "data/conversations/processed/scenario_similarity_candidates.csv"

THRESHOLD = 0.55

with INPUT.open("r", encoding="utf-8") as f:
    conversations = [
        json.loads(line)
        for line in f
        if line.strip()
    ]

domains = sorted(set(c["domain"] for c in conversations))
candidates = []

for domain in domains:
    rows = [
        c for c in conversations
        if c["domain"] == domain
    ]

    messages = [
        c["turns"][0]["text"]
        for c in rows
    ]

    vectorizer = TfidfVectorizer(
        lowercase=True,
        stop_words="english",
        ngram_range=(1, 2)
    )

    vectors = vectorizer.fit_transform(messages)
    similarities = cosine_similarity(vectors)

    for i in range(len(rows)):
        for j in range(i + 1, len(rows)):

            score = float(similarities[i][j])

            if score >= THRESHOLD:
                candidates.append({
                    "domain": domain,
                    "conversation_1": rows[i]["conversation_id"],
                    "conversation_2": rows[j]["conversation_id"],
                    "similarity": round(score, 4),
                    "opening_1": messages[i],
                    "opening_2": messages[j],
                    "review_status": "pending"
                })

candidates.sort(
    key=lambda x: x["similarity"],
    reverse=True
)

OUTPUT.parent.mkdir(parents=True, exist_ok=True)

with OUTPUT.open("w", newline="", encoding="utf-8-sig") as f:
    writer = csv.DictWriter(
        f,
        fieldnames=[
            "domain",
            "conversation_1",
            "conversation_2",
            "similarity",
            "opening_1",
            "opening_2",
            "review_status"
        ]
    )

    writer.writeheader()
    writer.writerows(candidates)

print("Total conversations:", len(conversations))
print("Potential matching pairs:", len(candidates))
print("Similarity threshold:", THRESHOLD)
print("Saved to:", OUTPUT)

print("\nTop 10 potential matches:")

for pair in candidates[:10]:
    print(
        pair["conversation_1"],
        "<->",
        pair["conversation_2"],
        "| Score:",
        pair["similarity"]
    )
