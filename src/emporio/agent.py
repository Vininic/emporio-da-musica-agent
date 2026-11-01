import json
import re
import time
from collections.abc import Iterator
from dataclasses import dataclass, field

from emporio.domain import hours
from emporio.guard import unbacked_actions, unsupported_claims
from emporio.i18n import AGENT_TEXT
from emporio.llm import LLM, LLMError, ModelUsed, TextDelta, ToolCall, ToolCalls
from emporio.prompt import system_prompt
from emporio.tools import Session, ToolContext, run_tool, tool_schemas

MAX_TOOL_ROUNDS = 6
MAX_HISTORY_MESSAGES = 40
MAX_MARKER_LENGTH = 80
MARKER = re.compile(r"\[\[\s*((?:bloco|gesto|fonte)\s*:[^\[\]]*?)\s*\]\]")
ALWAYS_SHOWN = {"order", "return", "quote", "ticket"}
GESTURES = {"wave", "yes", "no", "thumbs", "dance"}
SENSITIVE_ARGS = {"phone", "contact"}
FALLBACK = AGENT_TEXT["pt"]["fallback"]


@dataclass
class Turn:
    text: str = ""
    tools_called: list[str] = field(default_factory=list)
    blocks: dict[str, dict] = field(default_factory=dict)
    corrected: bool = False
    gave_up: bool = False
    model: str | None = None
    sources: list[str] = field(default_factory=list)


def _marker_items(body: str) -> Iterator[tuple[str, str]]:
    kind = ""
    for piece in body.split(","):
        name, separator, value = piece.partition(":")
        if separator:
            kind = name.strip()
        else:
            value = name
        if value.strip():
            yield kind, value.strip()


def _referenced(text: str, kind: str) -> list[str]:
    return [
        value
        for body in MARKER.findall(text)
        for found, value in _marker_items(body)
        if found == kind
    ]


class MarkerFilter:
    def __init__(self):
        self._buffer = ""

    def feed(self, text: str) -> Iterator[tuple[str, str]]:
        self._buffer += text
        while True:
            match = MARKER.search(self._buffer)
            if match is None:
                break
            before = self._buffer[: match.start()]
            if before:
                yield "text", before
            yield from _marker_items(match[1])
            self._buffer = self._buffer[match.end() :]

        hold = self._partial_marker_start()
        safe, self._buffer = self._buffer[:hold], self._buffer[hold:]
        if safe:
            yield "text", safe

    def _partial_marker_start(self) -> int:
        start = self._buffer.find("[[")
        if start == -1:
            return len(self._buffer) - 1 if self._buffer.endswith("[") else len(self._buffer)
        if len(self._buffer) - start > MAX_MARKER_LENGTH:
            return len(self._buffer)
        return start

    def flush(self) -> Iterator[tuple[str, str]]:
        if self._buffer:
            yield "text", self._buffer
            self._buffer = ""


def strip_markers(text: str) -> str:
    return MARKER.sub("", text).strip()


def _mask(arguments: dict) -> dict:
    return {
        key: (f"•••{str(value)[-4:]}" if key in SENSITIVE_ARGS else value)
        for key, value in arguments.items()
    }


def _trim(messages: list[dict]) -> list[dict]:
    if len(messages) <= MAX_HISTORY_MESSAGES:
        return messages
    trimmed = messages[-MAX_HISTORY_MESSAGES:]
    while trimmed and trimmed[0]["role"] != "user":
        trimmed = trimmed[1:]
    return trimmed


def _gesture_after_tool(name: str, data: dict, block: dict | None) -> str | None:
    if name == "lookup_order":
        return "yes" if data.get("verified") else "no"
    if name == "get_product":
        return "yes" if block and block.get("availability") == "disponivel" else "no"
    if name == "search_products":
        return "thumbs" if data.get("total") else "no"
    if name == "check_return":
        return "yes" if data.get("outcome") == "elegivel" else "no"
    if name == "open_ticket" and "ticket" in data:
        return "thumbs"
    return None


class Agent:
    def __init__(self, llm: LLM, ctx: ToolContext):
        self._llm = llm
        self._ctx = ctx
        self._tools = tool_schemas()
        self._words = AGENT_TEXT[ctx.lang]

    @property
    def session(self) -> Session:
        return self._ctx.session

    def run(self, messages: list[dict], user_text: str) -> Iterator[dict]:
        first_turn = not messages
        messages.append({"role": "user", "content": user_text})
        turn = Turn()
        now = self._ctx.clock.now()

        if first_turn:
            if hours.is_open(now):
                yield {"type": "gesture", "name": "wave"}
            else:
                yield {"type": "gesture", "name": "sit"}
                yield {
                    "type": "block",
                    "id": "closed",
                    "block": {
                        "type": "closed",
                        "opens": hours.describe_opening(
                            hours.next_opening(now), now, self._ctx.lang
                        ),
                    },
                }

        try:
            yield from self._respond(messages, turn, stream=True)
            problems = [] if turn.gave_up else self._check(messages, turn)
            if problems:
                yield {"type": "guard", "problems": problems}
                yield from self._correct(messages, turn, problems)
        except LLMError as error:
            yield {"type": "provider_error", "auth": error.auth, "detail": str(error)}
            message = self._words["bad_key"] if error.auth else self._words["provider_down"]
            messages.pop() if messages and messages[-1]["role"] == "user" else None
            yield {"type": "replace", "text": message}
            yield {"type": "done", "model": None, "corrected": False}
            return

        yield from self._append_unreferenced(turn)
        yield {"type": "done", "model": turn.model, "corrected": turn.corrected}

    def _check(self, messages: list[dict], turn: Turn) -> list[str]:
        answer = strip_markers(turn.text)
        if not answer:
            return [self._words["empty"]]
        sources = [
            json.dumps(m["content"], ensure_ascii=False)
            for m in messages
            if m["role"] in ("user", "tool") and m.get("content")
        ]
        claims = unsupported_claims(answer, sources)
        actions = unbacked_actions(answer, turn.tools_called, self._words["ticket_claim"])
        return [*claims, *actions]

    def _correct(self, messages: list[dict], turn: Turn, problems: list[str]) -> Iterator[dict]:
        rejected = messages.pop()
        attempt = [
            *messages,
            rejected,
            {
                "role": "user",
                "content": self._words["correction"].format(problems=", ".join(problems)),
            },
        ]
        start = len(attempt)
        turn.text = ""
        turn.corrected = True
        for event in self._respond(attempt, turn, stream=False):
            if event["type"] != "replace":
                yield event

        added = attempt[start:]
        if turn.gave_up or not strip_markers(turn.text) or self._check(messages + added, turn):
            turn.text = self._words["fallback"]
            messages.append({"role": "assistant", "content": turn.text})
        else:
            messages.extend(added)

        yield {"type": "replace", "text": strip_markers(turn.text)}
        for block_id in _referenced(turn.text, "bloco"):
            yield {"type": "block_ref", "id": block_id}

    def _respond(self, messages: list[dict], turn: Turn, stream: bool) -> Iterator[dict]:
        system = {"role": "system", "content": system_prompt(self._ctx.clock.now(), self._ctx.lang)}
        for _ in range(MAX_TOOL_ROUNDS):
            text, calls = "", ()
            marker_filter = MarkerFilter()
            for event in self._llm.stream([system, *_trim(messages)], self._tools):
                if isinstance(event, ModelUsed):
                    turn.model = event.name
                    yield {"type": "model", "name": event.name}
                elif isinstance(event, TextDelta):
                    text += event.text
                    if stream:
                        yield from self._marker_events(marker_filter.feed(event.text))
                elif isinstance(event, ToolCalls):
                    calls = event.calls
            if stream:
                yield from self._marker_events(marker_filter.flush())

            if not calls:
                turn.text += text
                messages.append({"role": "assistant", "content": text})
                return

            assistant = {"role": "assistant", "content": text or None}
            assistant["tool_calls"] = [call.as_message() for call in calls]
            messages.append(assistant)
            for call in calls:
                yield from self._run_call(messages, turn, call)

        turn.text = self._words["fallback"]
        turn.gave_up = True
        messages.append({"role": "assistant", "content": turn.text})
        yield {"type": "replace", "text": turn.text}

    def _marker_events(self, pieces: Iterator[tuple[str, str]]) -> Iterator[dict]:
        for kind, value in pieces:
            if kind == "text":
                yield {"type": "text", "text": value}
            elif kind == "bloco":
                yield {"type": "block_ref", "id": value}
            elif kind == "gesto" and value in GESTURES:
                yield {"type": "gesture", "name": value}

    def _run_call(self, messages: list[dict], turn: Turn, call: ToolCall) -> Iterator[dict]:
        try:
            arguments = json.loads(call.arguments or "{}")
        except json.JSONDecodeError:
            arguments = {}

        turn.tools_called.append(call.name)
        yield {"type": "tool_start", "call": call.id, "name": call.name, "args": _mask(arguments)}
        started = time.perf_counter()
        result = run_tool(self._ctx, call.name, arguments)
        elapsed = round((time.perf_counter() - started) * 1000)

        data = dict(result.data)
        search_trace = data.pop("_search", None)
        block_id = None
        if result.block is not None:
            block_id = f"b{self.session.next_block}"
            self.session.next_block += 1
            data["block"] = block_id
            turn.blocks[block_id] = result.block
            yield {"type": "block", "id": block_id, "block": result.block}

        content = json.dumps(data, ensure_ascii=False)
        messages.append({"role": "tool", "tool_call_id": call.id, "content": content})
        turn.sources.append(content)
        yield {
            "type": "tool_end",
            "call": call.id,
            "name": call.name,
            "ms": elapsed,
            "ok": "error" not in data,
            "search": search_trace,
            "block": block_id,
        }
        gesture = _gesture_after_tool(call.name, data, result.block)
        if gesture:
            yield {"type": "gesture", "name": gesture}

    def _append_unreferenced(self, turn: Turn) -> Iterator[dict]:
        referenced = set(_referenced(turn.text, "bloco"))
        for block_id, block in turn.blocks.items():
            if block["type"] == "policy":
                yield from self._cited_sections(block_id, block, turn)
            elif block_id not in referenced and (not referenced or block["type"] in ALWAYS_SHOWN):
                yield {"type": "block_ref", "id": block_id}

    def _cited_sections(self, block_id: str, block: dict, turn: Turn) -> Iterator[dict]:
        cited = set(_referenced(turn.text, "fonte"))
        sections = [section for section in block["sections"] if section["id"] in cited]
        if sections:
            yield {"type": "block", "id": block_id, "block": {**block, "sections": sections}}
            yield {"type": "block_ref", "id": block_id}
