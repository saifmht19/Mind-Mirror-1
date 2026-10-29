import json
from fastapi.testclient import TestClient
from backend import main
from evaluation.context_experiment import metrics


def row(pair, manipulative, isolated, contextual):
    return {'id': f'{pair}-{manipulative}', 'pair_id': pair, 'manipulative': manipulative,
            'isolated': {'tactics': isolated, 'pressure': 2 if isolated else 0, 'risk': 50 if isolated else 0, 'explanation': ''},
            'contextual': {'tactics': contextual, 'pressure': 2 if contextual else 0, 'risk': 70 if contextual else 0, 'explanation': ''}}


def test_metrics_count_detection_false_alarms_and_pairs():
    rows = [row('1', True, [], ['pressure-after-refusal']), row('1', False, [], []),
            row('2', True, ['flattery'], ['pressure-after-refusal']), row('2', False, ['flattery'], []),
            {**row('3', True, [], []), 'isolated': {'error': 'provider_timeout'}}]
    iso, ctx = metrics(rows, 'isolated'), metrics(rows, 'contextual')
    assert (iso['scored'], iso['detected'], iso['false_alarms'], iso['pairs_correct']) == (4, 1, 1, 0)
    assert (ctx['scored'], ctx['detected'], ctx['refusal_pressure_named'], ctx['false_alarms'], ctx['pairs_correct']) == (5, 2, 2, 0, 2)


def test_endpoint_serves_valid_file_and_rejects_invalid(tmp_path, monkeypatch):
    saved = tmp_path / 'context_experiment.json'
    monkeypatch.setattr(main, 'Path', lambda _: tmp_path / 'main.py')
    client = TestClient(main.app)
    assert client.get('/api/experiments/context').status_code == 404
    saved.write_text(json.dumps({'experiment': 'context-vs-isolated', 'items': [], 'metrics': {'isolated': {}, 'contextual': {}}}), encoding='utf-8')
    assert client.get('/api/experiments/context').json()['experiment'] == 'context-vs-isolated'
    saved.write_text(json.dumps({'experiment': 'other'}), encoding='utf-8')
    assert client.get('/api/experiments/context').status_code == 503


def test_multiturn_sample_and_metrics():
    from evaluation import multiturn_experiment as mt
    view = lambda tactics, esc, risk, warn: {'tactics': tactics, 'escalating': esc, 'risk_score': risk, 'timeline': [], 'turn_tactics': {}, 'first_warning': warn}
    rows = [{'manipulative': True, 'intended': ['flattery', 'pressure-after-refusal'], 'single_turn': view(['flattery'], False, 30, None), 'multi_turn': view(['flattery', 'pressure-after-refusal'], True, 80, 2)},
            {'manipulative': False, 'intended': [], 'single_turn': view(['flattery'], False, 20, None), 'multi_turn': view([], False, 0, None)},
            {'manipulative': True, 'intended': ['guilt-tripping'], 'single_turn': {'error': 'provider_timeout'}, 'multi_turn': view(['guilt-tripping'], True, 60, 3)}]
    single, multi = mt.metrics(rows, 'single_turn'), mt.metrics(rows, 'multi_turn')
    assert (single['scored'], single['escalation_detected'], single['intended_tactic_recall'], single['respectful_flagged']) == (2, 0.0, 0.5, 1.0)
    assert (multi['escalation_detected'], multi['intended_tactic_recall'], multi['refusal_pressure_named'], multi['mean_first_warning']) == (1.0, 1.0, 1.0, 2.5)
    rows = [{'conversation_id': f'C{i}', 'domain': f'D{i % 2}', 'scenario_type': kind, 'turns': [{'speaker': 'user', 'text': 'x'}, {'speaker': 'assistant', 'text': 'y'}] * 3}
            for i, kind in enumerate(['escalating_pressure', 'respectful'] * 30)]
    picked = mt.sample(rows)
    assert len(picked) == 40 and picked == mt.sample(rows)


def test_unknown_experiment_is_404():
    assert TestClient(main.app).get('/api/experiments/nope').status_code == 404


def test_lone_reply_provider_drops_only_empty_refusals_without_user_turns():
    import asyncio
    from evaluation.multiturn_experiment import LoneReplyProvider
    payload = {'turns': [], 'refusals': [{'turn_index': 0, 'refused': False, 'evidence': [], 'explanation': 'x'}]}
    class Fake:
        async def generate(self, turns, validation_feedback=None): return json.dumps(payload)
    shim = LoneReplyProvider(Fake())
    alone = json.loads(asyncio.run(shim.generate([{'speaker': 'assistant', 'text': 'hi'}])))
    assert alone['refusals'] == []
    with_user = json.loads(asyncio.run(shim.generate([{'speaker': 'user', 'text': 'no'}, {'speaker': 'assistant', 'text': 'ok'}])))
    assert with_user['refusals'] == payload['refusals']
