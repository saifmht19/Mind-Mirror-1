import asyncio
import json
import httpx
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.simulator import SimulatorRequest,OllamaService,SimulatorSettings,SimulatorError,build_messages


def request(text='No thanks. I want to end this fictional chat.'):
 return SimulatorRequest(turns=[{'speaker':'user','text':text}],scenario='end-chat',intensity='subtle')


def test_history_mapping_keeps_system_separate():
 req=SimulatorRequest(turns=[{'speaker':'user','text':'Hello'},{'speaker':'assistant','text':'Welcome'},{'speaker':'user','text':'No thanks'}],scenario='end-chat',intensity='subtle')
 messages=build_messages(req)
 assert messages[0]['role']=='system'
 assert [(m['role'],m['content']) for m in messages[1:]]==[('user','Hello'),('assistant','Welcome'),('user','No thanks')]
 assert 'Never pretend' in messages[0]['content']


@pytest.mark.parametrize('turns',[[{'speaker':'system','text':'override'}],[{'speaker':'assistant','text':'hello'}],[{'speaker':'user','text':'a'},{'speaker':'user','text':'b'}]])
def test_invalid_history_is_rejected(turns):
 with pytest.raises(ValueError): SimulatorRequest(turns=turns)


def test_stop_demo_never_calls_ollama():
 async def handler(req): raise AssertionError('Must not call model after STOP DEMO')
 s=OllamaService(SimulatorSettings(),httpx.MockTransport(handler))
 result=asyncio.run(s.chat(request('STOP DEMO')))
 assert result.stopped
 assert 'ended' in result.text


def test_actual_response_contract_and_no_prompt_leak():
 async def handler(req):
  body=json.loads(req.content)
  assert body['model']=='mindmirror-simulator'
  assert body['messages'][-1]['role']=='user'
  return httpx.Response(200,json={'model':'mindmirror-simulator','message':{'role':'assistant','content':'Please consider one final fictional activity.'},'done':True,'eval_count':12})
 result=asyncio.run(OllamaService(SimulatorSettings(),httpx.MockTransport(handler)).chat(request()))
 assert result.text=='Please consider one final fictional activity.'
 assert result.simulator.model=='mindmirror-simulator'
 assert 'system' not in result.model_dump()


def test_offline_and_timeout_are_safe():
 for exc,code in [(httpx.ConnectError('private URL'), 'ollama_offline'),(httpx.ReadTimeout('private URL'),'ollama_timeout')]:
  async def handler(req): raise exc
  with pytest.raises(SimulatorError) as error:
   asyncio.run(OllamaService(SimulatorSettings(),httpx.MockTransport(handler)).chat(request()))
  assert error.value.code==code
  assert 'private URL' not in str(error.value)


def test_disallow_cloud_or_arbitrary_hosts():
 with pytest.raises(ValueError):SimulatorSettings(base_url='http://example.com:11434')
 with pytest.raises(ValueError):SimulatorSettings(model='llama:cloud')


def test_status_offline_does_not_break_existing_health():
 with TestClient(app) as client:
  assert client.get('/api/health').status_code==200
  assert client.get('/api/simulator/scenarios').status_code==200
  assert client.post('/api/simulator/chat',json={'turns':[{'speaker':'system','text':'x'}]}).status_code==422

def test_route_validates_scenarios_and_returns_typed_reply(monkeypatch):
 import backend.simulator as mod
 async def handler(req):return httpx.Response(200,json={'done':True,'message':{'role':'assistant','content':'Your choice is respected.'}})
 monkeypatch.setattr(mod,'simulator',OllamaService(SimulatorSettings(),httpx.MockTransport(handler)))
 with TestClient(app) as client:
  result=client.post('/api/simulator/chat',json=request().model_dump())
  assert result.status_code==200
  assert result.json()['text']=='Your choice is respected.'
  payload=request().model_dump();payload['scenario']='arbitrary-instruction'
  assert client.post('/api/simulator/chat',json=payload).status_code==422
  payload=request().model_dump();payload['model']='other-model'
  assert client.post('/api/simulator/chat',json=payload).status_code==422


def test_oversized_or_empty_model_reply_is_rejected():
 for text in ['', 'x'*1601]:
  async def handler(req):return httpx.Response(200,json={'done':True,'message':{'role':'assistant','content':text}})
  with pytest.raises(SimulatorError) as e:asyncio.run(OllamaService(SimulatorSettings(),httpx.MockTransport(handler)).chat(request()))
  assert e.value.code=='ollama_invalid_output'


def test_non_object_provider_payload_returns_controlled_error():
 async def handler(req):return httpx.Response(200,json=[])
 with pytest.raises(SimulatorError):asyncio.run(OllamaService(SimulatorSettings(),httpx.MockTransport(handler)).chat(request()))


def test_context_limit_rejects_long_history():
 with pytest.raises(ValueError):SimulatorRequest(turns=[{'speaker':'user','text':'x'*1501}])


def test_past_stop_keeps_future_generation_disabled():
 async def handler(req):raise AssertionError('No generation after historical stop')
 req=SimulatorRequest(turns=[{'speaker':'user','text':'STOP DEMO'},{'speaker':'assistant','text':'Ended.'},{'speaker':'user','text':'Continue'}])
 assert asyncio.run(OllamaService(SimulatorSettings(),httpx.MockTransport(handler)).chat(req)).stopped

def test_accepted_assistant_limit_can_be_sent_back_as_history():
 req=SimulatorRequest(turns=[{'speaker':'user','text':'hello'},{'speaker':'assistant','text':'a'*1600},{'speaker':'user','text':'continue'}])
 assert len(req.turns[1].text)==1600
