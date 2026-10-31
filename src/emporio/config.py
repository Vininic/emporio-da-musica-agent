import os
from dataclasses import dataclass, replace
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
TIMEZONE = ZoneInfo("America/Campo_Grande")
SNAPSHOT_DATE = date(2026, 3, 25)

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
GEMINI_CHAT_MODELS = ("gemini-3.5-flash-lite", "gemini-3.1-flash-lite")
GEMINI_EMBEDDING_MODEL = "gemini-embedding-2"
OPENROUTER_CHAT_MODELS = ("google/gemini-3.5-flash-lite", "google/gemini-3.6-flash")
OPENROUTER_EMBEDDING_MODEL = "openai/text-embedding-3-small"
EMBEDDING_DIMENSIONS = 768


@dataclass(frozen=True)
class Provider:
    name: str
    api_key: str
    base_url: str
    chat_models: tuple[str, ...]
    embedding_model: str
    fallback: "Provider | None" = None


def provider_from(name: str, api_key: str, model: str | None = None) -> Provider:
    if name == "openrouter":
        models = (model, *OPENROUTER_CHAT_MODELS) if model else OPENROUTER_CHAT_MODELS
        return Provider(name, api_key, OPENROUTER_BASE_URL, models, OPENROUTER_EMBEDDING_MODEL)
    models = (model, *GEMINI_CHAT_MODELS) if model else GEMINI_CHAT_MODELS
    return Provider("gemini", api_key, GEMINI_BASE_URL, models, GEMINI_EMBEDDING_MODEL)


def provider_from_env() -> Provider | None:
    load_dotenv(ROOT / ".env")
    model = os.getenv("CHAT_MODEL") or None
    preferred = os.getenv("LLM_PROVIDER", "gemini")
    keys = {"gemini": os.getenv("GEMINI_API_KEY"), "openrouter": os.getenv("OPENROUTER_API_KEY")}
    names = [name for name in dict.fromkeys((preferred, "gemini", "openrouter")) if keys.get(name)]
    if not names:
        return None
    provider = provider_from(names[0], keys[names[0]], model)
    if len(names) > 1:
        provider = replace(provider, fallback=provider_from(names[1], keys[names[1]]))
    return provider


class Clock:
    def __init__(self, fixed: datetime | None = None, snapshot: date = SNAPSHOT_DATE):
        self._fixed = fixed
        self._snapshot = snapshot

    @classmethod
    def from_env(cls) -> "Clock":
        load_dotenv(ROOT / ".env")
        value = os.getenv("STORE_NOW")
        return cls(datetime.fromisoformat(value).replace(tzinfo=TIMEZONE) if value else None)

    def now(self) -> datetime:
        if self._fixed is not None:
            return self._fixed
        current = datetime.now(TIMEZONE)
        return current.replace(
            year=self._snapshot.year, month=self._snapshot.month, day=self._snapshot.day
        )

    def today(self) -> date:
        return self.now().date()
