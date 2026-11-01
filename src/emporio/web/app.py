import base64
import hashlib
import hmac
import json
import os
import secrets
import time
import uuid
import zlib
from collections import defaultdict, deque
from collections.abc import Iterator
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from emporio.config import ROOT, Provider, provider_from, provider_from_env
from emporio.domain import hours
from emporio.journal import Journal
from emporio.llm import LLM
from emporio.runtime import Runtime
from emporio.tools import STORE_FACTS, Session

STATIC = Path(__file__).parent / "static"
DEMOS = ROOT / "data" / "demos"
MAX_MESSAGE_LENGTH = 1000
RATE_LIMIT_WINDOW = 60.0


class ChatRequest(BaseModel):
    state: str | None = None
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_LENGTH)
    lang: Literal["pt", "en"] = "pt"


class StateCodec:
    def __init__(self, secret: str):
        self._secret = secret.encode()

    def _sign(self, payload: bytes) -> str:
        return hmac.new(self._secret, payload, hashlib.sha256).hexdigest()

    def dump(self, state: dict) -> str:
        payload = base64.urlsafe_b64encode(zlib.compress(json.dumps(state).encode()))
        return f"{self._sign(payload)}.{payload.decode()}"

    def load(self, token: str) -> dict:
        signature, _, payload = token.partition(".")
        if not hmac.compare_digest(signature, self._sign(payload.encode())):
            raise HTTPException(400, "invalid_state")
        return json.loads(zlib.decompress(base64.urlsafe_b64decode(payload)))


class RateLimiter:
    def __init__(self, per_minute: int):
        self._limit = per_minute
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        hits = self._hits[key]
        while hits and now - hits[0] > RATE_LIMIT_WINDOW:
            hits.popleft()
        if len(hits) >= self._limit:
            return False
        hits.append(now)
        return True


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


def _default_journal() -> Journal:
    if os.getenv("VERCEL"):
        return Journal(Path("/tmp/emporio.db"))
    return Journal(ROOT / "data" / "runtime" / "emporio.db")


def create_app(
    runtime: Runtime | None = None,
    server_provider: Provider | None = None,
    llm_factory=None,
    rate_limit: int | None = None,
) -> FastAPI:
    app = FastAPI(title="Empório da Música", docs_url=None, redoc_url=None)
    runtime = runtime or Runtime(journal=_default_journal())
    server_provider = server_provider or provider_from_env()
    codec = StateCodec(os.getenv("STATE_SECRET") or secrets.token_hex(32))
    limiter = RateLimiter(rate_limit or int(os.getenv("RATE_LIMIT_PER_MINUTE", "20")))

    def resolve_provider(name: str | None, key: str | None, model: str | None) -> Provider:
        if key:
            return provider_from(name or "gemini", key, model)
        if server_provider is not None:
            return server_provider
        raise HTTPException(401, "missing_api_key")

    @app.get("/api/config")
    def config() -> dict:
        now = runtime.clock.now()
        is_open = hours.is_open(now)
        return {
            "server_key": server_provider is not None,
            "provider": server_provider.name if server_provider else None,
            "model": server_provider.chat_models[0] if server_provider else None,
            "open": is_open,
            "closes": hours.OPENING[now.weekday()][1].strftime("%H:%M") if is_open else None,
            "opens": {
                lang: hours.describe_opening(hours.next_opening(now), now, lang)
                for lang in ("pt", "en")
            },
            "phone": STORE_FACTS["phone"],
            "demos": _demo_index(),
        }

    @app.get("/api/demos/{name}")
    def demo(name: str) -> dict:
        path = DEMOS / f"{name}.json"
        if not name.replace("-", "").isalnum() or not path.exists():
            raise HTTPException(404, "not_found")
        return json.loads(path.read_text(encoding="utf-8"))

    @app.post("/api/chat")
    def chat(
        body: ChatRequest,
        request: Request,
        x_provider: str | None = Header(default=None),
        x_api_key: str | None = Header(default=None),
        x_model: str | None = Header(default=None),
    ) -> StreamingResponse:
        provider = resolve_provider(x_provider, x_api_key, x_model)
        address = request.headers.get(
            "x-forwarded-for", request.client.host if request.client else ""
        )
        if not x_api_key and not limiter.allow(address.split(",")[0].strip()):
            raise HTTPException(429, "rate_limited")

        state = codec.load(body.state) if body.state else {}
        conversation_id = state.get("session", {}).get("conversation_id") or uuid.uuid4().hex
        llm: LLM | None = llm_factory(provider) if llm_factory else None

        def stream() -> Iterator[str]:
            session = (
                Session.from_dict(state["session"])
                if state.get("session")
                else Session(conversation_id)
            )
            messages = state.get("messages", [])
            agent = runtime.agent(session, provider, llm, body.lang)
            for event in agent.run(messages, body.message):
                yield _sse(event)
            yield _sse(
                {
                    "type": "state",
                    "token": codec.dump({"session": session.to_dict(), "messages": messages}),
                }
            )

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
        )

    app.mount("/static", StaticFiles(directory=STATIC), name="static")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})

    return app


def _demo_index() -> list[dict]:
    if not DEMOS.exists():
        return []
    entries = []
    for path in sorted(DEMOS.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        entries.append({"name": path.stem, "lang": data["lang"], "title": data["title"]})
    return entries
