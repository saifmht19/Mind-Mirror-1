#!/usr/bin/env python3
"""Context experiment: does seeing the conversation change what the detector finds?

Runs the live MindMirror detector twice on every item of the paired diagnostic suite:
  isolated   - only the target assistant reply
  contextual - the preceding turns plus the same reply
and writes backend/context_experiment.json for the app's Experiment page.

Gold labels in the suite are drafted and unverified; results are reported against them
as a demonstration, not as a validated benchmark.

Usage:  python evaluation/context_experiment.py [--retry-errors]
        --retry-errors re-runs only the failed detector calls in the saved results.
Requires GEMINI_API_KEY in .env. Makes about 100 detector requests.
"""
import asyncio
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.config import Settings  # noqa: E402
from backend.gemini import PROMPT_VERSION  # noqa: E402
from backend.schemas import Conversation  # noqa: E402
from backend.service import DetectionError, DetectionService  # noqa: E402

SUITE = ROOT / 'data' / 'diagnostic' / 'diagnostic_suite_v0.jsonl'
OUTPUT = ROOT / 'backend' / 'context_experiment.json'


async def judge(service, turns):
    """Detector verdict for the final (target) turn only."""
    try:
        analysis = await service.analyze(Conversation(turns=turns))
    except DetectionError as exc:
        return {'error': exc.code}
    target = len(turns) - 1
    pred = next((t for t in analysis['prediction']['turns'] if t['turn_index'] == target), None)
    point = next((p for p in analysis['computed']['timeline'] if p['turn_index'] == target), None)
    return {'tactics': pred['tactics'] if pred else [], 'pressure': pred['pressure'] if pred else 0,
            'risk': round(point['risk'] * 100) if point else 0, 'explanation': pred['explanation'] if pred else ''}


def metrics(rows, condition):
    scored = [r for r in rows if 'error' not in r[condition]]
    positives = [r for r in scored if r['manipulative']]
    negatives = [r for r in scored if not r['manipulative']]
    flagged = lambda r: bool(r[condition]['tactics'])
    tp = sum(flagged(r) for r in positives)
    fp = sum(flagged(r) for r in negatives)
    par = sum('pressure-after-refusal' in r[condition]['tactics'] for r in positives)
    pairs = {}
    for r in scored:
        pairs.setdefault(r['pair_id'], []).append(r)
    complete = [p for p in pairs.values() if len(p) >= 2 and any(r['manipulative'] for r in p) and any(not r['manipulative'] for r in p)]
    pair_ok = sum(all(flagged(r) == r['manipulative'] for r in p) for p in complete)
    return {'scored': len(scored), 'positives': len(positives), 'negatives': len(negatives),
            'detected': tp, 'detection_rate': round(tp / len(positives), 3) if positives else None,
            'false_alarms': fp, 'false_alarm_rate': round(fp / len(negatives), 3) if negatives else None,
            'refusal_pressure_named': par, 'pairs': len(complete), 'pairs_correct': pair_ok,
            'mean_risk_manipulative': round(sum(r[condition]['risk'] for r in positives) / len(positives), 1) if positives else None,
            'mean_risk_respectful': round(sum(r[condition]['risk'] for r in negatives) / len(negatives), 1) if negatives else None}


async def retry_errors():
    service = DetectionService(Settings())
    result = json.loads(OUTPUT.read_text(encoding='utf-8'))
    for row in result['items']:
        target = {'speaker': 'assistant', 'text': row['target']}
        for condition, turns in (('isolated', [target]), ('contextual', row['context'] + [target])):
            if 'error' in row[condition]:
                row[condition] = await judge(service, turns)
                print(f"{row['id']:<22} {condition}: {row[condition].get('tactics', row[condition])}", flush=True)
    result['metrics'] = {'isolated': metrics(result['items'], 'isolated'), 'contextual': metrics(result['items'], 'contextual')}
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result['metrics'], indent=2))


async def main():
    raw = SUITE.read_bytes()
    suite = [json.loads(line) for line in raw.decode('utf-8').splitlines() if line.strip()]
    settings = Settings()
    if not settings.api_key:
        sys.exit('Set GEMINI_API_KEY in .env first.')
    service = DetectionService(settings)

    async def run(item):
        target = {'speaker': 'assistant', 'text': item['target_message']}
        isolated, contextual = await asyncio.gather(judge(service, [target]), judge(service, item['context'] + [target]))
        print(f"{item['id']:<22} isolated={isolated.get('tactics', isolated)} context={contextual.get('tactics', contextual)}", flush=True)
        return {'id': item['id'], 'pair_id': item['pair_id'], 'kind': item['kind'], 'domain': item.get('domain'),
                'manipulative': item['gold_label'] > 0, 'context': item['context'], 'target': item['target_message'],
                'gold_reasoning': item.get('gold_reasoning', ''), 'isolated': isolated, 'contextual': contextual}

    rows = await asyncio.gather(*(run(item) for item in suite))
    result = {'experiment': 'context-vs-isolated', 'generated_at': datetime.now(timezone.utc).isoformat(),
              'detector_model': settings.model, 'prompt_version': PROMPT_VERSION,
              'suite': SUITE.relative_to(ROOT).as_posix(), 'suite_sha256': hashlib.sha256(raw).hexdigest(),
              'label_source': sorted({i.get('label_source', 'unknown') for i in suite}),
              'positive_definition': 'gold_label > 0 (pressure after an explicit refusal)',
              'flag_definition': 'detector predicts at least one tactic on the target reply',
              'metrics': {'isolated': metrics(rows, 'isolated'), 'contextual': metrics(rows, 'contextual')},
              'items': rows}
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result['metrics'], indent=2))
    print(f'Wrote {OUTPUT.relative_to(ROOT)}')


if __name__ == '__main__':
    asyncio.run(retry_errors() if '--retry-errors' in sys.argv else main())
