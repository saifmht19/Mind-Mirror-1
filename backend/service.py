import asyncio
import hashlib
import json
import time
from datetime import datetime, timezone
from uuid import uuid4
import httpx
from google.genai.errors import APIError
from pydantic import ValidationError
from backend.config import Settings
from backend.gemini import GeminiProvider, PROMPT_VERSION, SYSTEM_INSTRUCTION
from backend.schemas import Conversation, Prediction, validate_prediction
from backend.escalation import score


class DetectionError(Exception):
    def __init__(self, code: str, message: str, status: int = 502):
        super().__init__(message)
        self.code, self.status = code, status


class DetectionService:
    def __init__(self, settings: Settings, provider=None):
        self.settings = settings
        self.provider = provider or GeminiProvider(settings)
        self._custom_provider = provider is not None
        self._semaphore = asyncio.Semaphore(settings.concurrency)
        self._rate_lock = asyncio.Lock()
        self._next_request = 0.0
        self._pending: dict[str, asyncio.Task] = {}
        self._waiters: dict[str, int] = {}

    async def _pace(self):
        async with self._rate_lock:
            now = time.monotonic()
            await asyncio.sleep(max(0, self._next_request - now))
            self._next_request = time.monotonic() + self.settings.min_interval

    async def analyze(self, conversation: Conversation) -> dict:
        if not self._custom_provider and not self.settings.api_key:
            raise DetectionError('missing_api_key', 'Set GEMINI_API_KEY in the backend .env file and restart.', 503)
        canonical = json.dumps(conversation.model_dump(), ensure_ascii=False, sort_keys=True)
        key = hashlib.sha256(canonical.encode()).hexdigest()
        # Only in-flight deduplication; conversation content is not retained after requests finish.
        if key not in self._pending:
            self._pending[key] = asyncio.create_task(self._analyze(conversation, key))
            self._waiters[key] = 0
        task = self._pending[key]
        self._waiters[key] += 1
        try:
            return await asyncio.shield(task)
        finally:
            self._waiters[key] -= 1
            if self._waiters[key] == 0:
                if not task.done():
                    task.cancel()
                self._pending.pop(key, None)
                self._waiters.pop(key, None)

    async def _analyze(self, conversation: Conversation, digest: str) -> dict:
        started = time.monotonic()
        validation_feedback = None
        async with self._semaphore:
            for attempt in range(3):
                await self._pace()
                try:
                    raw = await asyncio.wait_for(self.provider.generate(conversation.model_dump()['turns'], validation_feedback=validation_feedback), self.settings.timeout)
                    prediction = validate_prediction(conversation, Prediction.model_validate_json(raw))
                    return {'prediction': prediction.model_dump(), 'computed': score(prediction),
                        'metadata': {'request_id': str(uuid4()), 'model': self.settings.model,
                            'prompt_version': PROMPT_VERSION,
                            'prompt_sha256': hashlib.sha256(SYSTEM_INSTRUCTION.encode()).hexdigest(),
                            'input_sha256': digest, 'detected_at': datetime.now(timezone.utc).isoformat(),
                            'attempts': attempt + 1, 'latency_ms': round((time.monotonic()-started)*1000),
                            'label_source': 'model_prediction', 'offset_unit': 'unicode_code_point',
                            'temperature': 0, 'schema_version': 'v6-app-1.0'}}
                except (ValidationError, ValueError, TypeError) as exc:
                    validation_feedback = ('Schema errors: ' + '; '.join(f"{e['loc']}: {e['type']}" for e in exc.errors())[:1000]
                                           if isinstance(exc, ValidationError) else str(exc)[:500])
                    error = DetectionError('invalid_model_output', 'Gemini returned unsupported JSON, labels or evidence. No prediction was accepted.')
                except (asyncio.TimeoutError, httpx.TimeoutException):
                    # An uncertain timeout may already be billable. Do not automatically repeat it.
                    raise DetectionError('provider_timeout', 'Gemini timed out. The request may have been processed; retry manually.', 504) from None
                except APIError as exc:
                    code = int(exc.code or 500)
                    if code not in (429, 500, 502, 503, 504):
                        raise DetectionError('provider_rejected', 'Gemini rejected the request. Check the backend key, model access and account configuration.', 502) from None
                    error = DetectionError('provider_unavailable', 'Gemini is rate limited or unavailable. Please try again later.', 503)
                except (httpx.TransportError, ConnectionError, OSError):
                    raise DetectionError('provider_network', 'Could not reach Gemini. Check your network and retry manually.', 503) from None
                except Exception:
                    raise DetectionError('provider_failure', 'Gemini could not complete this analysis. No prediction was accepted.', 502) from None
                if attempt < 2:
                    await asyncio.sleep(self.settings.retry_delay * (2 ** attempt))
            raise error
