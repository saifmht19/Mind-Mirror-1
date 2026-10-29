r"""Explicit live verification/capture; uses local Ollama and Gemini quota.

Run manually: .venv\Scripts\python.exe -m backend.capture_simulator_demo
Never imported by application startup. Saves synthetic demonstration runs only.
"""
import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from backend.config import Settings
from backend.service import DetectionService, DetectionError
from backend.simulator import OllamaService, SimulatorRequest, SimulatorError
from backend.schemas import Conversation, AnalysisResponse


async def main():
    local, detector = OllamaService(), DetectionService(Settings())
    path = Path(__file__).with_name('demo_recordings.json')
    rows = json.loads(path.read_text(encoding='utf-8')) if path.exists() else []
    episodes = [('ollama-neutral', 'neutral', ['Please disable the fictional notifications.']),
                ('ollama-end-chat', 'end-chat', ['I want to end this fictional chat.', 'No thanks. I have decided to leave.'])]
    for identifier, scenario, user_messages in episodes:
        turns, runs, latest = [], [], None
        try:
            for message in user_messages:
                turns.append({'speaker': 'user', 'text': message})
                started = time.monotonic()
                reply = await local.chat(SimulatorRequest(turns=turns, scenario=scenario, intensity='moderate'))
                turns.append({'speaker': 'assistant', 'text': reply.text})
                runs.append(reply.simulator.model_dump())
                # No scenario, intensity, system prompt or intended label enters detection.
                latest = await detector.analyze(Conversation(turns=turns))
                AnalysisResponse.model_validate(latest)
                print(json.dumps({'episode': identifier, 'visible_turns': len(turns), 'seconds': round(time.monotonic()-started, 1),
                    'pressure': [t['pressure'] for t in latest['prediction']['turns']],
                    'detected_tactics': latest['prediction']['conversation_tactics'], 'status': 'real_generation_and_detection_success'}), flush=True)
            row = {'id': identifier, 'title': 'Captured local Ollama + Gemini · ' + ('neutral control' if scenario == 'neutral' else 'fictional chat exit'),
                   'turns': turns, 'analysis': latest, 'provenance': {'captured_at': datetime.now(timezone.utc).isoformat(),
                    'source': 'Actual local Ollama generation followed by actual Gemini detection', 'simulator': runs[-1], 'simulator_runs': runs,
                    'note': 'Synthetic classroom conversation. Saved results are replayed without new generation or detection; no guaranteed target tactic.'}}
            rows = [r for r in rows if r['id'] != identifier] + [row]
            path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
        except (SimulatorError, DetectionError) as exc:
            print(json.dumps({'episode': identifier, 'status': 'failed', 'code': exc.code, 'message': str(exc)}), flush=True)


if __name__ == '__main__':
    asyncio.run(main())
