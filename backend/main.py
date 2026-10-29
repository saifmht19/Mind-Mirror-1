import asyncio
import json
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, File, Form, HTTPException, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from backend.config import Settings
from backend.datasets import MAX_UPLOAD, parse_dataset
from backend.examples import EXAMPLES
from backend.schemas import AnalysisResponse, Conversation
from backend.service import DetectionError, DetectionService
from backend.simulator import router as simulator_router

settings = Settings()


@asynccontextmanager
async def lifespan(app):
    app.state.service = DetectionService(settings)
    yield


app = FastAPI(title='MindMirror v6', version='1.0.0', lifespan=lifespan,
              description='Explainable multi-turn Gemini predictions; untuned deterministic risk scoring.')
app.add_middleware(CORSMiddleware, allow_origins=settings.origins, allow_credentials=False,
                   allow_methods=['GET', 'POST'], allow_headers=['Content-Type'])


class RequestLimit:
    """Cap actual bytes, including chunked requests, before multipart or JSON parsing."""
    def __init__(self, app): self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        headers = dict(scope.get('headers', []))
        origin = headers.get(b'origin', b'').decode('latin-1')
        if scope.get('method') == 'POST' and origin and origin not in settings.origins:
            return await JSONResponse({'detail': 'Frontend origin is not allowed'}, status_code=403)(scope, receive, send)
        size, messages = 0, []
        while True:
            message = await receive()
            if message['type'] == 'http.disconnect': return
            size += len(message.get('body', b''))
            if size > MAX_UPLOAD + 65536:
                response = JSONResponse({'detail': 'Request exceeds upload limit'}, status_code=413)
                return await response(scope, receive, send)
            messages.append(message)
            if not message.get('more_body', False): break
        async def replay():
            return messages.pop(0) if messages else await receive()
        await self.app(scope, replay, send)


app.add_middleware(RequestLimit)
app.include_router(simulator_router)


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    # Pydantic's default includes raw input, which could contain private content.
    return JSONResponse({'detail': [{'loc': list(e['loc']), 'msg': e['msg'], 'type': e['type']} for e in exc.errors()]}, status_code=422)


@app.exception_handler(DetectionError)
async def detection_error(request, exc):
    return JSONResponse({'detail': str(exc), 'code': exc.code}, status_code=exc.status)


def get_service() -> DetectionService:
    return app.state.service


@app.get('/api/health')
async def health():
    return {'status': 'ok', 'gemini_configured': bool(settings.api_key), 'model': settings.model,
            'persistence': 'none', 'evaluation_available': False}


@app.get('/api/examples')
async def examples():
    return EXAMPLES


EXPERIMENTS = {
    'context': ('context_experiment.json', 'context-vs-isolated', {'isolated', 'contextual'}, 'evaluation/context_experiment.py'),
    'multiturn': ('multiturn_experiment.json', 'single-vs-multi-turn', {'single_turn', 'multi_turn'}, 'evaluation/multiturn_experiment.py'),
}


@app.get('/api/experiments/{name}')
async def experiment(name: str):
    """Saved output of an evaluation script; 404 until that experiment has been run."""
    if name not in EXPERIMENTS:
        raise HTTPException(404, 'Unknown experiment')
    filename, kind, conditions, script = EXPERIMENTS[name]
    path = Path(__file__).with_name(filename)
    if not path.exists():
        raise HTTPException(404, f'Run python {script} to generate this experiment.')
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        if data.get('experiment') != kind or not isinstance(data.get('items'), list) or set(data.get('metrics', {})) != conditions:
            raise ValueError()
        return data
    except (ValueError, TypeError):
        raise HTTPException(503, 'Saved experiment failed validation') from None


@app.post('/api/analyze', response_model=AnalysisResponse)
async def analyze(conversation: Conversation, service: DetectionService = Depends(get_service)):
    return await service.analyze(conversation)


async def read_upload(file):
    content = await file.read(MAX_UPLOAD + 1)
    await file.close()
    try:
        return parse_dataset(content, file.filename or '')
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None


@app.post('/api/datasets/preview')
async def preview(file: UploadFile = File(...)):
    return {'records': await read_upload(file), 'max_batch': 50, 'confirmation_above': 5}


@app.post('/api/analyze/batch', responses={200: {'content': {'application/x-ndjson': {}}}})
async def batch(file: UploadFile = File(...), selected: str | None = Form(None),
                confirm_large: bool = Form(False), service: DetectionService = Depends(get_service)):
    records = await read_upload(file)
    if selected is not None:
        try:
            indices = json.loads(selected)
            if not isinstance(indices, list) or not indices or any(type(i) is not int or i < 0 or i >= len(records) for i in indices) or len(set(indices)) != len(indices):
                raise ValueError()
        except (ValueError, TypeError):
            raise HTTPException(400, 'selected must be a nonempty array of unique valid row indices') from None
        records = [r for r in records if r['index'] in indices]
    if len(records) > 50:
        raise HTTPException(400, 'Select at most 50 conversations per batch')
    if len(records) > 5 and not confirm_large:
        raise HTTPException(400, 'More than 5 conversations requires confirm_large=true; Gemini calls may be billable')

    async def stream():
        # Two workers and a batch-local memo avoid duplicate provider requests.
        memo = {}
        async def run(row):
            base = {k: row[k] for k in ('index', 'conversation_id', 'metadata', 'original_record', 'turns')}
            if row['error']:
                return {**base, 'status': 'failed', 'error': row['error']}
            key = json.dumps(row['turns'], ensure_ascii=False, sort_keys=True)
            if key not in memo:
                memo[key] = asyncio.create_task(service.analyze(Conversation(turns=row['turns'])))
            try:
                return {**base, 'status': 'success', 'analysis': await memo[key]}
            except DetectionError as exc:
                return {**base, 'status': 'failed', 'error': str(exc), 'code': exc.code}
        # Windows of two bound memory/tasks; yield in source order immediately.
        for start in range(0, len(records), 2):
            tasks = [asyncio.create_task(run(r)) for r in records[start:start+2]]
            try:
                for task in tasks:
                    yield json.dumps(await task, ensure_ascii=False) + '\n'
            finally:
                for task in tasks:
                    if not task.done(): task.cancel()
        memo.clear()
    return StreamingResponse(stream(), media_type='application/x-ndjson',
                             headers={'Content-Disposition': 'attachment; filename="mindmirror-predictions.jsonl"',
                                      'Cache-Control': 'no-store', 'X-Accel-Buffering': 'no'})
