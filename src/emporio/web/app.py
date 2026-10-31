import json
import uuid
from collections.abc import Iterator
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
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
MAX_TURNS_PER_CONVERSATION = 60


class ChatRequest(BaseModel):
    conversation_id: str | None = None
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_LENGTH)


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


def create_app(
    runtime: Runtime | None = None,
    server_provider: Provider | None = None,
    llm_factory=None,
) -> FastAPI:
    app = FastAPI(title="Empório da Música", docs_url=None, redoc_url=None)
    runtime = runtime or Runtime(journal=Journal(ROOT / "data" / "runtime" / "emporio.db"))
    server_provider = server_provider or provider_from_env()

    def resolve_provider(name: str | None, key: str | None) -> Provider:
        if key:
            return provider_from(name or "gemini", key)
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
            "open": is_open,
            "opens": None if is_open else hours.describe_opening(hours.next_opening(now), now),
            "closes": _closing_time(now) if is_open else None,
            "phone": STORE_FACTS["telefone"],
            "demos": _demo_index(),
        }

    @app.get("/api/demos/{name}")
    def demo(name: str) -> dict:
        path = DEMOS / f"{name}.json"
        if not name.replace("-", "").isalnum() or not path.exists():
            raise HTTPException(404, "not_found")
        return json.loads(path.read_text(encoding="utf-8"))

    @app.get("/api/conversations/{conversation_id}")
    def conversation(conversation_id: str) -> dict:
        state = runtime.journal.load_state(conversation_id)
        if state is None:
            raise HTTPException(404, "not_found")
        return {"id": conversation_id, "turns": state.get("turns", [])}

    @app.post("/api/chat")
    def chat(
        request: ChatRequest,
        x_provider: str | None = Header(default=None),
        x_api_key: str | None = Header(default=None),
    ) -> StreamingResponse:
        provider = resolve_provider(x_provider, x_api_key)
        conversation_id = request.conversation_id or uuid.uuid4().hex
        state = runtime.journal.load_state(conversation_id) or {}
        if len(state.get("turns", [])) >= MAX_TURNS_PER_CONVERSATION:
            raise HTTPException(429, "conversation_too_long")

        llm: LLM | None = llm_factory(provider) if llm_factory else None

        def stream() -> Iterator[str]:
            session = (
                Session.from_dict(state["session"])
                if state.get("session")
                else Session(conversation_id)
            )
            messages = state.get("messages", [])
            agent = runtime.agent(session, provider, llm)
            events = []
            yield _sse({"type": "conversation", "id": conversation_id})
            try:
                for event in agent.run(messages, request.message):
                    events.append(event)
                    yield _sse(event)
            finally:
                turns = [*state.get("turns", []), {"user": request.message, "events": events}]
                runtime.journal.save_state(
                    conversation_id,
                    {"session": session.to_dict(), "messages": messages, "turns": turns},
                    runtime.clock.now(),
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


def _closing_time(now) -> str:
    window = hours.OPENING[now.weekday()]
    return window[1].strftime("%H:%M")


def _demo_index() -> list[dict]:
    if not DEMOS.exists():
        return []
    entries = []
    for path in sorted(DEMOS.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        entries.append({"name": path.stem, "title": data["title"]})
    return entries
