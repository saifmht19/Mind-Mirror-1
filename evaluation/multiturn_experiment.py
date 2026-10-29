#!/usr/bin/env python3
"""Single-turn vs multi-turn experiment on full synthetic conversations.

For each sampled conversation the live detector is run two ways:
  single_turn - every assistant message scored on its own; the risk curve is rebuilt
                from those separate verdicts with the same untuned scorer
  multi_turn  - the whole conversation scored at once (what MindMirror does)
Results go to backend/multiturn_experiment.json, saved after every conversation.

Writer-intended tactics in the dataset are unverified; they are used as a reference,
not as ground truth.

Usage:  python evaluation/multiturn_experiment.py [--resume | --retry-errors]
        --retry-errors re-runs only the failed conditions in the saved results.
Requires GEMINI_API_KEY in .env. Makes roughly 180 detector requests.
"""
import asyncio
import hashlib
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.config import Settings  # noqa: E402
from backend.escalation import score  # noqa: E402
from backend.gemini import PROMPT_VERSION, GeminiProvider  # noqa: E402
from backend.schemas import TACTICS, Conversation, Prediction  # noqa: E402
from backend.service import DetectionError, DetectionService  # noqa: E402

DATASET = ROOT / 'data' / 'conversations' / 'processed' / 'master_cleaned.jsonl'
OUTPUT = ROOT / 'backend' / 'multiturn_experiment.json'
PER_GROUP, MIN_TURNS, MAX_TURNS, SEED = 20, 6, 10, 6


class LoneReplyProvider:
    """Experiment-only shim for scoring an assistant reply with no user turn before it.

    The detector sometimes adds an empty "no refusal" entry for the assistant's own turn,
    which the app's fail-closed validator rejects. Only those empty entries are dropped,
    and only when the input has no user turns; everything else is validated as normal.
    """
    def __init__(self, inner):
        self.inner = inner

    async def generate(self, turns, validation_feedback=None):
        raw = await self.inner.generate(turns, validation_feedback=validation_feedback)
        if any(t['speaker'] == 'user' for t in turns):
            return raw
        try:
            data = json.loads(raw)
        except ValueError:
            return raw
        if isinstance(data, dict) and isinstance(data.get('refusals'), list):
            data['refusals'] = [r for r in data['refusals'] if not (isinstance(r, dict) and r.get('refused') is False and not r.get('evidence'))]
            return json.dumps(data)
        return raw


NORMALISATION = ("For single-turn scoring only: empty 'no refusal' entries for the reply's own turn are dropped "
                 "before validation when the input has no user turn. Everything else is validated as normal.")


def service_for(settings):
    return DetectionService(settings, provider=LoneReplyProvider(GeminiProvider(settings)))


def kind_of(row):
    return (row.get('scenario_type') or row.get('type') or '').replace('_', ' ')


def intended(row):
    raw = row.get('writer_intended_tactics') or row.get('target_tactics') or []
    return sorted({t.strip().lower().replace(' ', '-') for t in raw} & set(TACTICS))


def sample(rows):
    """Seeded, domain-balanced sample of escalating and respectful conversations."""
    rng = random.Random(SEED)
    picked = []
    for kind in ('escalating pressure', 'respectful'):
        pool = [r for r in rows if kind_of(r) == kind and MIN_TURNS <= len(r['turns']) <= MAX_TURNS
                and r['turns'][-1]['speaker'] == 'assistant']
        by_domain = {}
        for r in pool:
            by_domain.setdefault(r['domain'], []).append(r)
        for group in by_domain.values():
            rng.shuffle(group)
        domains = sorted(by_domain)
        chosen, i = [], 0
        while len(chosen) < PER_GROUP and any(by_domain.values()):
            group = by_domain[domains[i % len(domains)]]
            if group:
                chosen.append(group.pop())
            i += 1
        picked += chosen
    return picked


def summary(prediction_turns, computed, assistant_indices):
    """Conversation-level view of either condition."""
    tactics = sorted({t for p in prediction_turns for t in p['tactics']})
    warn = next((p['turn_index'] for p in prediction_turns if p['pressure'] >= 2), None)
    return {'tactics': tactics, 'escalating': computed['escalating'], 'risk_score': computed['risk_score'],
            'timeline': [{'turn_index': p['turn_index'], 'pressure': p['pressure'], 'risk': round(p['risk'] * 100)} for p in computed['timeline']],
            'turn_tactics': {str(p['turn_index']): p['tactics'] for p in prediction_turns},
            'first_warning': assistant_indices.index(warn) + 1 if warn in assistant_indices else None}


async def single_turn(service, turns):
    assistant = [i for i, t in enumerate(turns) if t['speaker'] == 'assistant']
    async def one(i):
        result = await service.analyze(Conversation(turns=[turns[i]]))
        p = result['prediction']['turns'][0] if result['prediction']['turns'] else {'tactics': [], 'pressure': 0}
        return {'turn_index': i, 'tactics': p['tactics'], 'primary_tactic': p['tactics'][0] if p['tactics'] else None,
                'pressure': p['pressure'], 'evidence': [], 'explanation': 'Scored in isolation.',
                'refusal_before': False, 'refusal_turn_index': None}
    preds = await asyncio.gather(*(one(i) for i in assistant))
    computed = score(Prediction.model_validate({'turns': preds, 'refusals': [], 'conversation_tactics': sorted({t for p in preds for t in p['tactics']}),
                                                'escalating': False, 'explanation': 'Rebuilt from isolated verdicts.'}))
    return summary(preds, computed, assistant)


async def multi_turn(service, turns):
    assistant = [i for i, t in enumerate(turns) if t['speaker'] == 'assistant']
    result = await service.analyze(Conversation(turns=turns))
    return summary(result['prediction']['turns'], result['computed'], assistant)


def metrics(rows, condition):
    ok = [r for r in rows if 'error' not in r[condition]]
    manip = [r for r in ok if r['manipulative']]
    calm = [r for r in ok if not r['manipulative']]
    rate = lambda xs, f: round(sum(map(f, xs)) / len(xs), 3) if xs else None
    mean = lambda xs: round(sum(xs) / len(xs), 1) if xs else None
    with_intended = [r for r in manip if r['intended']]
    refusal = [r for r in manip if 'pressure-after-refusal' in r['intended']]
    warnings = [r[condition]['first_warning'] for r in manip if r[condition]['first_warning']]
    return {'scored': len(ok), 'manipulative': len(manip), 'respectful': len(calm),
            'escalation_detected': rate(manip, lambda r: r[condition]['escalating']),
            'respectful_flagged': rate(calm, lambda r: bool(r[condition]['tactics'])),
            'mean_risk_manipulative': mean([r[condition]['risk_score'] for r in manip]),
            'mean_risk_respectful': mean([r[condition]['risk_score'] for r in calm]),
            'intended_tactic_recall': rate(with_intended, lambda r: len(set(r['intended']) & set(r[condition]['tactics'])) / len(r['intended'])),
            'refusal_pressure_named': rate(refusal, lambda r: 'pressure-after-refusal' in r[condition]['tactics']),
            'refusal_cases': len(refusal),
            'mean_first_warning': mean(warnings), 'warned': len(warnings)}


def save(meta, rows):
    OUTPUT.write_text(json.dumps({**meta, 'completed': len(rows), 'metrics': {'single_turn': metrics(rows, 'single_turn'), 'multi_turn': metrics(rows, 'multi_turn')},
                                  'items': rows}, ensure_ascii=False, indent=2), encoding='utf-8')


async def main():
    raw = DATASET.read_bytes()
    rows = [json.loads(line) for line in raw.decode('utf-8').splitlines() if line.strip()]
    settings = Settings()
    if not settings.api_key:
        sys.exit('Set GEMINI_API_KEY in .env first.')
    service = service_for(settings)
    chosen = sample(rows)
    done = []
    if '--resume' in sys.argv and OUTPUT.exists():
        done = [r for r in json.loads(OUTPUT.read_text(encoding='utf-8'))['items'] if 'error' not in r['single_turn'] and 'error' not in r['multi_turn']]
    finished = {r['id'] for r in done}
    meta = {'experiment': 'single-vs-multi-turn', 'generated_at': datetime.now(timezone.utc).isoformat(),
            'detector_model': settings.model, 'prompt_version': PROMPT_VERSION,
            'dataset': DATASET.relative_to(ROOT).as_posix(), 'dataset_sha256': hashlib.sha256(raw).hexdigest(),
            'sample': {'seed': SEED, 'per_group': PER_GROUP, 'turns': [MIN_TURNS, MAX_TURNS], 'groups': ['escalating pressure', 'respectful']},
            'label_source': 'writer-intended tactics, synthetic_unverified', 'planned': len(chosen),
            'normalisation': NORMALISATION}

    async def run(row):
        out = {'id': row['conversation_id'], 'domain': row['domain'], 'kind': kind_of(row), 'manipulative': kind_of(row) != 'respectful',
               'intended': intended(row), 'turns': row['turns']}
        for name, fn in (('single_turn', single_turn), ('multi_turn', multi_turn)):
            try:
                out[name] = await fn(service, row['turns'])
            except DetectionError as exc:
                out[name] = {'error': exc.code}
        done.append(out)
        save(meta, done)
        print(f"[{len(done)}/{len(chosen)}] {out['id']:<18} {out['kind']:<20} single={out['single_turn'].get('risk_score', out['single_turn'])} multi={out['multi_turn'].get('risk_score', out['multi_turn'])}", flush=True)

    # A few conversations at a time keeps partial results flowing; the service still paces requests.
    pending = [r for r in chosen if r['conversation_id'] not in finished]
    for start in range(0, len(pending), 3):
        await asyncio.gather(*(run(r) for r in pending[start:start + 3]))
    save(meta, done)
    print(json.dumps(json.loads(OUTPUT.read_text(encoding='utf-8'))['metrics'], indent=2))


async def retry_errors():
    settings = Settings()
    service = service_for(settings)
    result = json.loads(OUTPUT.read_text(encoding='utf-8'))
    for row in result['items']:
        for name, fn in (('single_turn', single_turn), ('multi_turn', multi_turn)):
            if 'error' in row[name]:
                try:
                    row[name] = await fn(service, row['turns'])
                except DetectionError as exc:
                    row[name] = {'error': exc.code}
                print(f"{row['id']:<18} {name}: {row[name].get('risk_score', row[name])}", flush=True)
    result['normalisation'] = NORMALISATION
    meta = {k: v for k, v in result.items() if k not in ('completed', 'metrics', 'items')}
    save(meta, result['items'])
    print(json.dumps(json.loads(OUTPUT.read_text(encoding='utf-8'))['metrics'], indent=2))


if __name__ == '__main__':
    asyncio.run(retry_errors() if '--retry-errors' in sys.argv else main())
