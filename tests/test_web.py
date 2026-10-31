import json
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from emporio.config import TIMEZONE, Clock, provider_from
from emporio.journal import Journal
from emporio.llm import TextDelta, ToolCall, ToolCalls
from emporio.runtime import Runtime
from emporio.web.app import create_app

PROVIDER = provider_from("gemini", "test-key")


class Scripted:
    def __init__(self, *rounds):
        self.rounds = list(rounds)

    def stream(self, messages, tools):
        yield from self.rounds.pop(0)


def client(*rounds, provider=PROVIDER, now=datetime(2026, 3, 25, 10, 30, tzinfo=TIMEZONE)):
    runtime = Runtime(clock=Clock(now), journal=Journal())
    runtime.indexes = lambda _provider: Runtime.indexes(runtime, None)
    llm = Scripted(*rounds)
    return TestClient(create_app(runtime, provider, lambda _p: llm))


def events(response):
    return [
        json.loads(line.removeprefix("data: "))
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]


def test_index_and_assets_are_served():
    api = client()
    assert "Amadeus" in api.get("/").text
    assert api.get("/static/app.js").status_code == 200
    assert api.get("/static/assets/robot.glb").status_code == 200


def test_config_reports_store_hours():
    data = client().get("/api/config").json()
    assert data["open"] is True
    assert data["closes"] == "18:00"
    assert data["phone"] == "(67) 3341-4444"


def test_config_when_closed():
    data = client(now=datetime(2026, 3, 28, 14, 0, tzinfo=TIMEZONE)).get("/api/config").json()
    assert data["open"] is False
    assert data["opens"] == "segunda, 30/03, às 09:00"


def test_chat_streams_events_and_persists_the_conversation():
    api = client(
        [ToolCalls((ToolCall("c1", "get_product", '{"nome": "Takamine GD20"}'),))],
        [TextDelta("Sai por R$ 2.199,00.")],
    )
    response = api.post("/api/chat", json={"message": "Quanto custa?"})
    stream = events(response)

    assert response.headers["content-type"].startswith("text/event-stream")
    assert stream[0]["type"] == "conversation"
    assert {"tool_start", "block", "text", "done"} <= {e["type"] for e in stream}

    saved = api.get(f"/api/conversations/{stream[0]['id']}").json()
    assert saved["turns"][0]["user"] == "Quanto custa?"
    assert any(e["type"] == "text" for e in saved["turns"][0]["events"])


def test_second_turn_keeps_the_verified_session():
    api = client(
        [
            ToolCalls(
                (
                    ToolCall(
                        "c1", "lookup_order", '{"numero_pedido": 1, "telefone": "(67) 98432-1098"}'
                    ),
                )
            )
        ],
        [TextDelta("Achei.")],
        [ToolCalls((ToolCall("c2", "check_return", '{"numero_pedido": 1, "motivo": "defeito"}'),))],
        [TextDelta("Fabricante.")],
    )
    first = events(api.post("/api/chat", json={"message": "pedido 1"}))
    conversation = first[0]["id"]
    second = events(
        api.post("/api/chat", json={"conversation_id": conversation, "message": "defeito"})
    )
    blocks = [e["block"]["type"] for e in second if e["type"] == "block"]
    assert blocks == ["return"]


def test_missing_key_is_an_explicit_401(monkeypatch):
    monkeypatch.setattr("emporio.web.app.provider_from_env", lambda: None)
    api = TestClient(create_app(Runtime(journal=Journal())))
    assert api.post("/api/chat", json={"message": "oi"}).status_code == 401


def test_key_in_header_is_used_and_never_stored():
    runtime = Runtime(
        clock=Clock(datetime(2026, 3, 25, 10, 30, tzinfo=TIMEZONE)), journal=Journal()
    )
    runtime.indexes = lambda _provider: Runtime.indexes(runtime, None)
    seen = []

    def factory(provider):
        seen.append(provider)
        return Scripted([TextDelta("Oi.")])

    api = TestClient(create_app(runtime, PROVIDER, factory))
    response = api.post(
        "/api/chat",
        json={"message": "oi"},
        headers={"X-Provider": "openrouter", "X-Api-Key": "byok-secret"},
    )
    assert seen[0].name == "openrouter"
    assert seen[0].api_key == "byok-secret"
    conversation = events(response)[0]["id"]
    assert "byok-secret" not in json.dumps(runtime.journal.load_state(conversation))


@pytest.mark.parametrize("message", ["", "x" * 1001])
def test_message_length_is_enforced(message):
    assert client().post("/api/chat", json={"message": message}).status_code == 422


def test_unknown_conversation_and_demo_are_404():
    api = client()
    assert api.get("/api/conversations/nope").status_code == 404
    assert api.get("/api/demos/nope").status_code == 404
    assert api.get("/api/demos/..%2F..%2Fsecret").status_code == 404
