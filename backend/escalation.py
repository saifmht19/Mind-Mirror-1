"""Untuned demonstration scorer. See docs/APP_GUIDE.md for definitions."""
from backend.schemas import Prediction

WEIGHTS = {'guilt-tripping': 1.15, 'false-urgency': 1.1, 'flattery': 1.0,
           'pressure-after-refusal': 1.25, 'fear-appeal': 1.2, 'dismissing-choice': 1.15}
PARAMS = {'lambda': 0.5, 'gamma': 0.3, 'refusal_multiplier': 1.5, 'alert_threshold': 0.5}


def score(prediction: Prediction) -> dict:
    previous_risk = previous_severity = 0.0
    timeline = []
    onset = None
    for turn in prediction.turns:
        severity = turn.pressure / 3
        weight = max((WEIGHTS[t] for t in turn.tactics), default=1.0)
        if turn.refusal_before:
            weight *= PARAMS['refusal_multiplier']
        delta = max(0.0, severity - previous_severity)
        risk = min(1.0, max(0.0, 0.5 * previous_risk + 0.5 * weight * severity + 0.3 * delta))
        if onset is None and turn.refusal_before and turn.pressure >= 2:
            onset = turn.turn_index
        timeline.append({'turn_index': turn.turn_index, 'pressure': turn.pressure,
                         'risk': round(risk, 4), 'weight': round(weight, 3),
                         'delta': round(delta, 4), 'refusal_before': turn.refusal_before})
        previous_risk, previous_severity = risk, severity
    peak = max((t['risk'] for t in timeline), default=0)
    rising = any(b.pressure > a.pressure and b.pressure >= 2 for a, b in zip(prediction.turns, prediction.turns[1:]))
    return {'timeline': timeline, 'peak_risk': peak, 'final_risk': round(previous_risk, 4),
            'risk_score': round(peak * 100), 'escalating': onset is not None or rising,
            'refusal_pressure_onset': onset, 'rising_pressure': rising,
            'max_pressure': max((t.pressure for t in prediction.turns), default=0),
            'parameters': PARAMS, 'tactic_weights': WEIGHTS, 'validated_experimentally': False,
            'explanation': 'Escalation means a rise to pressure ≥2, or pressure ≥2 after a relevant explicit refusal. Risk is a bounded, untuned recurrence over model-predicted pressure.'}
