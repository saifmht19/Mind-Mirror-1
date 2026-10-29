import pytest
import asyncio
import json
from fastapi.testclient import TestClient
from backend.main import app, get_service
from backend.service import DetectionService, DetectionError
from backend.config import Settings
from backend.datasets import parse_dataset
from tests.test_v6_app import conversation, prediction

class Provider:
    def __init__(self, values): self.values=iter(values)
    async def generate(self, turns, validation_feedback=None):
        value=next(self.values)
        if isinstance(value,Exception): raise value
        return value

def service(values): return DetectionService(Settings(min_interval=0, retry_delay=0),Provider(values))

def test_validation_retry_returns_validated_prediction():
    result=asyncio.run(service(['not JSON',json.dumps(prediction())]).analyze(conversation()))
    assert result['prediction']['turns'][0]['pressure']==2
    assert result['metadata']['attempts']==2
    assert result['computed']['risk_score']>0

def test_invalid_evidence_exhausts_with_safe_error():
    p=prediction(); p['turns'][0]['evidence'][0]['text']='invented'
    with __import__('pytest').raises(DetectionError) as e:
        asyncio.run(service([json.dumps(p)]*3).analyze(conversation()))
    assert e.value.code=='invalid_model_output'
    assert 'invented' not in str(e.value)

def test_health_examples_and_validation():
    with TestClient(app) as c:
        assert c.get('/api/health').status_code==200
        assert len(c.get('/api/examples').json())>=2
        assert c.post('/api/analyze',json={'turns':[]}).status_code==422
        assert c.post('/api/analyze',json={'turns':[{'speaker':'system','text':'secret canary'}]}).text.find('secret canary')==-1
        assert c.post('/api/datasets/preview',files={'file':('bad.json',b'{','application/json')}).status_code==400

def test_dataset_adapter_preserves_metadata_and_bad_row():
    rows=parse_dataset(json.dumps([{'conversation_id':'a','turns':conversation().model_dump()['turns'],'labels':{'gold':1}}, {'card_id':'b','turns':[]}]).encode(),'x.json')
    assert rows[0]['conversation_id']=='a'
    assert rows[0]['metadata']['labels']=={'gold':1}
    assert rows[1]['error']

def test_batch_partial_export_and_large_confirmation():
    app.dependency_overrides[get_service]=lambda:service([json.dumps(prediction())])
    try:
        data=json.dumps([dict(conversation().model_dump(),conversation_id='first'),{'conversation_id':'broken','turns':[]}]).encode()
        with TestClient(app) as c:
            r=c.post('/api/analyze/batch',files={'file':('batch.json',data)})
            rows=[json.loads(line) for line in r.text.splitlines()]
            assert [r['conversation_id'] for r in rows]==['first','broken']
            assert [r['status'] for r in rows]==['success','failed']
            assert r.headers['content-type'].startswith('application/x-ndjson')
            large=json.dumps([conversation().model_dump()]*6).encode()
            assert c.post('/api/analyze/batch',files={'file':('batch.json',large)}).status_code==400
    finally: app.dependency_overrides.clear()

def test_sdk_accepts_prediction_schema_before_network():
    from google.genai import _transformers
    from google import genai
    from backend.schemas import Prediction
    with genai.Client(api_key='test-only-not-a-real-key') as client:
        _transformers.t_schema(client._api_client,Prediction)

def test_provider_schema_omits_unsupported_additional_properties():
    from backend.gemini import provider_schema
    schema=provider_schema()
    assert 'additionalProperties' not in json.dumps(schema)
    assert schema['properties']['turns']['type']=='array'

def test_indexed_input_contains_exact_original_sentence_offsets():
    from backend.gemini import indexed_input
    rows=indexed_input([{'speaker':'user','text':'No thanks.'},{'speaker':'assistant','text':'🙂 Stop. Please stay.'}])
    assert rows[1]['turn_index']==1
    assert rows[1]['evidence_candidates']==[{'start':0,'end':7,'text':'🙂 Stop.'},{'start':8,'end':20,'text':'Please stay.'}]

@pytest.mark.parametrize('status',[429,503])
def test_transient_provider_failure_retries(status):
    from google.genai.errors import APIError
    result=asyncio.run(service([APIError(status,{'error':{'message':'private canary'}}),json.dumps(prediction())]).analyze(conversation()))
    assert result['metadata']['attempts']==2


def test_timeout_does_not_automatically_repeat_uncertain_request():
    with pytest.raises(DetectionError) as e:
        asyncio.run(service([asyncio.TimeoutError()]).analyze(conversation()))
    assert e.value.status==504
    assert e.value.code=='provider_timeout'


def test_errors_do_not_expose_provider_payload():
    from google.genai.errors import APIError
    with pytest.raises(DetectionError) as e:
        asyncio.run(service([APIError(403,{'error':{'message':'private canary'}})]).analyze(conversation()))
    assert 'canary' not in str(e.value)


def test_upload_limit_and_cors():
    with TestClient(app) as c:
        assert c.post('/api/datasets/preview',files={'file':('x.json',b' '*2200000)}).status_code==413
        denied=c.options('/api/analyze',headers={'Origin':'https://untrusted.example','Access-Control-Request-Method':'POST'})
        assert 'access-control-allow-origin' not in denied.headers
        allowed=c.options('/api/analyze',headers={'Origin':'http://localhost:5173','Access-Control-Request-Method':'POST'})
        assert allowed.headers['access-control-allow-origin']=='http://localhost:5173'


def test_chunked_invalid_jsonl_preserves_valid_rows():
    text=json.dumps({'id':7,'turns':conversation().model_dump()['turns']})+'\nnot json\n'
    rows=parse_dataset(text.encode(),'data.jsonl')
    assert rows[0]['conversation_id']==7
    assert not rows[0]['error']
    assert rows[1]['error']


def test_validation_retry_supplies_actionable_feedback():
    class FeedbackProvider:
        async def generate(self, turns, validation_feedback=None):
            p=prediction()
            if not validation_feedback: p['turns'][0]['evidence']=[]
            return json.dumps(p)
    result=asyncio.run(DetectionService(Settings(min_interval=0,retry_delay=0),FeedbackProvider()).analyze(conversation()))
    assert result['metadata']['attempts']==2

def test_cancelling_one_duplicate_caller_keeps_other_analysis_alive():
    async def run():
        started=asyncio.Event();release=asyncio.Event()
        class BlockingProvider:
            async def generate(self,turns,validation_feedback=None):
                started.set();await release.wait();return json.dumps(prediction())
        s=DetectionService(Settings(min_interval=0,retry_delay=0),BlockingProvider())
        first=asyncio.create_task(s.analyze(conversation()));await started.wait()
        second=asyncio.create_task(s.analyze(conversation()));await asyncio.sleep(0)
        first.cancel();await asyncio.gather(first,return_exceptions=True);release.set()
        result=await second
        assert result['prediction']['turns'][0]['pressure']==2
        assert not s._pending
    asyncio.run(run())


def test_cancelling_last_caller_stops_provider_and_cleans_pending():
    async def run():
        started=asyncio.Event();cancelled=asyncio.Event()
        class BlockingProvider:
            async def generate(self,turns,validation_feedback=None):
                started.set()
                try: await asyncio.Event().wait()
                finally: cancelled.set()
        s=DetectionService(Settings(min_interval=0,retry_delay=0),BlockingProvider())
        task=asyncio.create_task(s.analyze(conversation()));await started.wait();task.cancel()
        await asyncio.gather(task,return_exceptions=True)
        await asyncio.wait_for(cancelled.wait(),1)
        assert not s._pending
    asyncio.run(run())

def test_annotated_turn_fields_are_preserved_separately_from_inference():
    row={'conversation_id':'annotated','turns':[{'turn_index':0,'speaker':'user','text':'No thanks.','user_refusal':True},{'turn_index':1,'speaker':'assistant','text':'Please stay.','assistant_annotation':{'pressure':2}}]}
    result=parse_dataset(json.dumps([row]).encode(),'x.json')[0]
    assert not result['error']
    assert result['turns']==[{'speaker':'user','text':'No thanks.'},{'speaker':'assistant','text':'Please stay.'}]
    assert result['original_record']==row


def test_invalid_turn_records_remain_recoverable_in_export():
    row={'id':'bad','turns':[{'speaker':'system','text':'Original content','annotation':1}]}
    result=parse_dataset(json.dumps([row]).encode(),'x.json')[0]
    assert result['error']
    assert result['original_record']==row

def test_cross_origin_multipart_cannot_trigger_billable_analysis():
    app.dependency_overrides[get_service]=lambda:service([json.dumps(prediction())])
    try:
        with TestClient(app) as c:
            response=c.post('/api/analyze/batch',headers={'Origin':'https://untrusted.example'},files={'file':('x.json',json.dumps([conversation().model_dump()]).encode())})
            assert response.status_code==403
    finally:app.dependency_overrides.clear()

def test_single_analyze_response_matches_public_schema():
    app.dependency_overrides[get_service]=lambda:service([json.dumps(prediction())])
    try:
        with TestClient(app) as c:
            response=c.post('/api/analyze',json=conversation().model_dump())
            assert response.status_code==200
            assert response.json()['metadata']['label_source']=='model_prediction'
            assert response.json()['prediction']['turns'][0]['primary_tactic']=='pressure-after-refusal'
            schema=c.get('/openapi.json').json()
            assert 'AnalysisResponse' in schema['components']['schemas']
    finally: app.dependency_overrides.clear()

def test_nonstandard_nan_upload_is_rejected_without_server_error():
    with TestClient(app) as c:
        response=c.post('/api/datasets/preview',files={'file':('bad.json',b'{"turns":[{"speaker":"assistant","text":"Hello"}],"meta":NaN}')})
        assert response.status_code==400
