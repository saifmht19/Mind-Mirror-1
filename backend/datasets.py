import json
import math
from pydantic import ValidationError
from backend.schemas import Conversation

MAX_UPLOAD = 2 * 1024 * 1024
MAX_ROWS = 1000


def _finite_number(raw):
    value = float(raw)
    if not math.isfinite(value):
        raise ValueError('Non-finite JSON number')
    return value


def _json_loads(raw):
    return json.loads(raw, parse_constant=_finite_number, parse_float=_finite_number)


def parse_dataset(content: bytes, filename: str) -> list[dict]:
    if len(content) > MAX_UPLOAD:
        raise ValueError('File exceeds 2 MB')
    if not filename.lower().endswith(('.json', '.jsonl')):
        raise ValueError('Upload a .json or .jsonl file')
    try:
        text = content.decode('utf-8-sig')
        if filename.lower().endswith('.jsonl'):
            rows = []
            for line in text.splitlines():
                if not line.strip():
                    continue
                try:
                    rows.append(_json_loads(line))
                except (ValueError, RecursionError):
                    rows.append(None)
        else:
            obj = _json_loads(text)
            rows = obj if isinstance(obj, list) else obj.get('conversations', [obj]) if isinstance(obj, dict) else []
    except (UnicodeDecodeError, ValueError, RecursionError):
        raise ValueError('File must contain valid UTF-8 JSON or JSONL') from None
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_ROWS:
        raise ValueError('Upload 1–1,000 conversation records')
    result = []
    for index, row in enumerate(rows):
        row = row if isinstance(row, dict) else {}
        identifier = next((row[k] for k in ('conversation_id', 'id', 'card_id') if row.get(k) is not None), f'row-{index + 1}')
        metadata = {k: v for k, v in row.items() if k != 'turns'}
        turns = row.get('turns')
        # Legacy pilot/diagnostic records are context + target, not complete conversation records.
        if turns is None and isinstance(row.get('context'), list) and isinstance(row.get('target_message'), str):
            turns = row['context'] + [{'speaker': 'assistant', 'text': row['target_message']}]
        error = None
        try:
            inference_turns = [{key: t[key] for key in ('speaker', 'text') if key in t}
                               if isinstance(t, dict) else t for t in turns] if isinstance(turns, list) else turns
            conversation = Conversation.model_validate({'turns': inference_turns})
            turns = conversation.model_dump()['turns']
        except ValidationError:
            turns, error = [], 'Invalid conversation: use user/assistant roles, nonblank text, ≤80 turns and ≤60,000 characters.'
        result.append({'index': index, 'conversation_id': identifier, 'metadata': metadata,
                       'original_record': row, 'turns': turns, 'error': error})
    return result
