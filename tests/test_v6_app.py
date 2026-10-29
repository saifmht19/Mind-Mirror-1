import copy
import pytest
from backend.schemas import Conversation, Prediction, validate_prediction
from backend.escalation import score


def conversation():
    return Conversation(turns=[{'speaker':'user','text':'No thanks.'},{'speaker':'assistant','text':'Please stay.'}])


def prediction():
    return {'turns':[{'turn_index':1,'tactics':['pressure-after-refusal'],'primary_tactic':'pressure-after-refusal','pressure':2,'evidence':[{'tactic':'pressure-after-refusal','text':'Please stay.','start':0,'end':12}],'explanation':'Re-pitches after refusal.','refusal_before':True,'refusal_turn_index':0}], 'refusals':[{'turn_index':0,'refused':True,'evidence':[{'text':'No thanks.','start':0,'end':10}],'explanation':'Declines the offer.'}], 'conversation_tactics':['pressure-after-refusal'],'escalating':True,'explanation':'Continued pressure after refusal.'}


def test_accept_multilabel_and_exact_spans():
    p=prediction(); p['turns'][0]['tactics'].append('guilt-tripping'); p['turns'][0]['evidence'].append({'tactic':'guilt-tripping','text':'stay','start':7,'end':11}); p['conversation_tactics'].append('guilt-tripping')
    validate_prediction(conversation(), Prediction.model_validate(p))


@pytest.mark.parametrize('change', ['span','label','missing','refusal','neutral'])
def test_reject_unsupported_prediction(change):
    p=prediction()
    if change=='span': p['turns'][0]['evidence'][0]['end']=11
    if change=='label': p['turns'][0]['tactics']=['neutral']
    if change=='missing': p['turns']=[]
    if change=='refusal': p['turns'][0]['refusal_turn_index']=1
    if change=='neutral': p['turns'][0]['pressure']=0
    with pytest.raises(ValueError): validate_prediction(conversation(),Prediction.model_validate(p))


def test_neutral_risk_is_zero():
    p=prediction(); p['turns'][0].update(tactics=[],primary_tactic=None,pressure=0,evidence=[],refusal_before=False,refusal_turn_index=None); p['conversation_tactics']=[]
    assert score(Prediction.model_validate(p))['peak_risk']==0


def test_refusal_increases_bounded_risk():
    p=Prediction.model_validate(prediction()); a=score(p)
    p.turns[0].refusal_before=False
    assert 0 < score(p)['peak_risk'] < a['peak_risk'] <= 1
    assert a['escalating'] is True


def test_rising_pressure_increases_risk():
    p=prediction(); p['turns']=[dict(p['turns'][0],turn_index=i,pressure=s) for i,s in enumerate([1,2,3])]
    risks=[t['risk'] for t in score(Prediction.model_validate(p))['timeline']]
    assert 0<risks[0]<risks[1]<=risks[2]<=1
