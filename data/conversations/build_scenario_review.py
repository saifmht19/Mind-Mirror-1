"""Build review queues for MindMirror scenario grouping (no automatic grouping)."""
import csv
import json
from collections import defaultdict, Counter
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / 'data' / 'conversations' / 'processed'
MASTER = DATA / 'master_cleaned.jsonl'
SIMILAR = DATA / 'scenario_similarity_candidates.csv'
PAIRS_OUT = DATA / 'scenario_grouping_review.csv'
COVERAGE_OUT = DATA / 'scenario_grouping_coverage.csv'

for required in (MASTER, SIMILAR):
    if not required.is_file():
        raise SystemExit(f'Missing input: {required}')
for output in (PAIRS_OUT, COVERAGE_OUT):
    if output.exists():
        raise SystemExit(f'Review file already exists (not overwritten): {output}')

with MASTER.open(encoding='utf-8-sig') as handle:
    records = [json.loads(line) for line in handle if line.strip()]
by_id = {r['conversation_id']: r for r in records}
if len(by_id) != len(records):
    raise SystemExit('Duplicate conversation IDs; review manually.')

links = {}
def add(a, b, signal, similarity=None):
    if a == b or a not in by_id or b not in by_id:
        return
    x, y = sorted((a, b))
    if by_id[x]['domain'] != by_id[y]['domain']:
        return  # prevent matching cross-domain records blindly
    link = links.setdefault((x, y), {'signals': set(), 'similarity': None})
    link['signals'].add(signal)
    if similarity is not None:
        link['similarity'] = max(link['similarity'] or 0.0, float(similarity))

with SIMILAR.open(encoding='utf-8-sig', newline='') as handle:
    for line in csv.DictReader(handle):
        add(line['conversation_1'], line['conversation_2'], 'tfidf_opening', line['similarity'])

for field in ('group_id', 'pair_id'):
    buckets = defaultdict(list)
    for record in records:
        value = record.get(field)
        if value:
            buckets[(record['domain'], str(value))].append(record['conversation_id'])
    for members in buckets.values():
        for a, b in combinations(members, 2):
            add(a, b, f'same_{field}')

# Situation is often missing or may be an overly broad category. Show it as
# context in the review, but never use it alone to produce a link.
pair_fields = [
    'conversation_1', 'conversation_2', 'domain', 'evidence', 'similarity',
    'existing_group_1', 'existing_group_2', 'existing_pair_1', 'existing_pair_2',
    'situation_1', 'situation_2', 'opening_1', 'opening_2',
    'review_decision', 'reviewer_notes'
]
linked_ids = set()
review_rows = []
for (a, b), info in links.items():
    x, y = by_id[a], by_id[b]
    linked_ids.update((a, b))
    review_rows.append({
        'conversation_1': a, 'conversation_2': b, 'domain': x['domain'],
        'evidence': ';'.join(sorted(info['signals'])),
        'similarity': '' if info['similarity'] is None else round(info['similarity'], 4),
        'existing_group_1': x.get('group_id') or '',
        'existing_group_2': y.get('group_id') or '',
        'existing_pair_1': x.get('pair_id') or '',
        'existing_pair_2': y.get('pair_id') or '',
        'situation_1': x.get('situation') or '',
        'situation_2': y.get('situation') or '',
        'opening_1': x['turns'][0]['text'],
        'opening_2': y['turns'][0]['text'],
        'review_decision': 'pending', 'reviewer_notes': ''
    })
review_rows.sort(key=lambda r: (
    -int(r['similarity'] != ''),
    -(float(r['similarity']) if r['similarity'] != '' else 0),
    r['domain'], r['conversation_1'], r['conversation_2']
))
with PAIRS_OUT.open('w', encoding='utf-8-sig', newline='') as handle:
    writer = csv.DictWriter(handle, fieldnames=pair_fields)
    writer.writeheader()
    writer.writerows(review_rows)

coverage_fields = ['conversation_id', 'domain', 'source_dataset', 'existing_group_id',
                   'existing_pair_id', 'situation', 'appears_in_candidate_pairs',
                   'review_status']
with COVERAGE_OUT.open('w', encoding='utf-8-sig', newline='') as handle:
    writer = csv.DictWriter(handle, fieldnames=coverage_fields)
    writer.writeheader()
    for r in records:
        writer.writerow({
            'conversation_id': r['conversation_id'], 'domain': r['domain'],
            'source_dataset': r.get('source_dataset') or '',
            'existing_group_id': r.get('group_id') or '',
            'existing_pair_id': r.get('pair_id') or '',
            'situation': r.get('situation') or '',
            'appears_in_candidate_pairs': 'yes' if r['conversation_id'] in linked_ids else 'no',
            'review_status': 'pending'
        })

counts = Counter(r['domain'] for r in records)
print('Conversations:', len(records))
print('Reviewable candidate pairs:', len(review_rows))
print('Conversations covered by candidate pairs:', len(linked_ids))
print('Conversations with no candidate link:', len(records) - len(linked_ids))
print('Domains:', dict(sorted(counts.items())))
print('Saved:', PAIRS_OUT)
print('Saved:', COVERAGE_OUT)
print('No group IDs, annotations, or original conversations were modified.')
