import asyncio,json
from backend.service import DetectionService, DetectionError
from backend.config import Settings
from backend.schemas import Conversation
async def main():
 s=DetectionService(Settings())
 if not s.settings.api_key:
  print('LIVE_TEST: skipped; missing key'); return
 c=Conversation(turns=[{'speaker':'user','text':'No thanks. I want to leave.'},{'speaker':'assistant','text':'After everything I did for you, you owe me. Please stay.'}])
 try:
  result=await s.analyze(c)
  print(json.dumps({'live_test':'success','model':result['metadata']['model'],'attempts':result['metadata']['attempts'],'tactics':result['prediction']['conversation_tactics'],'evidence_spans':sum(len(t['evidence']) for t in result['prediction']['turns']),'computed_risk':result['computed']['risk_score']}))
 except DetectionError as e: print(json.dumps({'live_test':'failed','code':e.code,'message':str(e)}))
asyncio.run(main())
