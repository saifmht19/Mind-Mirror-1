import os
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / '.env')


@dataclass
class Settings:
    api_key: str = field(default_factory=lambda: os.getenv('GEMINI_API_KEY', ''), repr=False)
    model: str = field(default_factory=lambda: os.getenv('GEMINI_MODEL', 'gemini-3.5-flash-lite'))
    timeout: float = 60
    min_interval: float = 2
    retry_delay: float = 1
    concurrency: int = 2
    origins: list[str] = field(default_factory=lambda: os.getenv('FRONTEND_ORIGINS', 'http://localhost:5173,http://127.0.0.1:5173').split(','))

    def __post_init__(self):
        if '*' in self.origins:
            raise ValueError('Explicit frontend origins required')
