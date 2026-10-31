import logging
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np
from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI

from emporio.config import EMBEDDING_DIMENSIONS, Provider
from emporio.retrieval import Embedder

log = logging.getLogger(__name__)

EMBED_BATCH = 50
RETRIES_PER_MODEL = 2
FIRST_BYTE_TIMEOUT = 12.0
FALLBACK_TIMEOUT = 30.0
RATE_LIMIT_PAUSE = 15.0


class LLMError(Exception):
    def __init__(self, message: str, auth: bool = False):
        super().__init__(message)
        self.auth = auth


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: str
    extra: dict | None = None

    def as_message(self) -> dict:
        message = {
            "id": self.id,
            "type": "function",
            "function": {"name": self.name, "arguments": self.arguments},
        }
        if self.extra:
            message["extra_content"] = self.extra
        return message


@dataclass(frozen=True)
class TextDelta:
    text: str


@dataclass(frozen=True)
class ToolCalls:
    calls: tuple[ToolCall, ...]


@dataclass(frozen=True)
class ModelUsed:
    name: str


class LLM(Protocol):
    def stream(
        self, messages: list[dict], tools: list[dict]
    ) -> Iterator[TextDelta | ToolCalls | ModelUsed]: ...


def _is_retryable(error: Exception) -> bool:
    if isinstance(error, APITimeoutError | APIConnectionError):
        return True
    return isinstance(error, APIStatusError) and (
        error.status_code in (400, 408, 409, 429) or error.status_code >= 500
    )


def _is_rate_limit(error: Exception | None) -> bool:
    return isinstance(error, APIStatusError) and error.status_code == 429


def _describe(error: Exception | None) -> str:
    if isinstance(error, APIStatusError):
        return f"{error.status_code} {str(error.body)[:200]}"
    return str(error)[:200]


class ToolCallCollector:
    def __init__(self):
        self._entries: list[dict] = []

    def add(self, delta) -> None:
        entry = self._find(delta)
        entry["id"] = delta.id or entry["id"]
        if delta.function:
            entry["name"] = delta.function.name or entry["name"]
            entry["arguments"] += delta.function.arguments or ""
        extra = delta.model_dump().get("extra_content")
        if extra:
            entry["extra"] = extra

    def _find(self, delta) -> dict:
        for entry in self._entries:
            if delta.id and entry["id"] == delta.id:
                return entry
            if not delta.id and delta.index is not None and entry["index"] == delta.index:
                return entry
        entry = {"id": "", "index": delta.index, "name": "", "arguments": "", "extra": None}
        self._entries.append(entry)
        return entry

    @property
    def calls(self) -> tuple[ToolCall, ...]:
        return tuple(
            ToolCall(e["id"], e["name"], e["arguments"] or "{}", e["extra"]) for e in self._entries
        )


class OpenAICompatibleLLM:
    def __init__(
        self, provider: Provider, timeout: float = FIRST_BYTE_TIMEOUT, patience: float = 0
    ):
        self._routes = [(self._client(provider, timeout), provider.chat_models)]
        if provider.fallback is not None:
            self._routes.append(
                (self._client(provider.fallback, FALLBACK_TIMEOUT), provider.fallback.chat_models)
            )
        self._patience = patience
        self.waited = 0.0

    @staticmethod
    def _client(provider: Provider, timeout: float) -> OpenAI:
        return OpenAI(
            api_key=provider.api_key, base_url=provider.base_url, timeout=timeout, max_retries=0
        )

    def stream(
        self, messages: list[dict], tools: list[dict]
    ) -> Iterator[TextDelta | ToolCalls | ModelUsed]:
        last_error: Exception | None = None
        for client, models in self._routes:
            for model in models:
                attempt = 0
                waited_here = 0.0
                while attempt < RETRIES_PER_MODEL:
                    started = time.perf_counter()
                    emitted = False
                    try:
                        for event in self._stream_once(client, model, messages, tools):
                            emitted = True
                            yield event
                        return
                    except Exception as error:
                        last_error = error
                        if isinstance(error, APIStatusError) and error.status_code in (401, 403):
                            raise LLMError("chave de API recusada", auth=True) from error
                        if emitted or not _is_retryable(error):
                            raise LLMError(_describe(error)) from error
                        log.warning("%s failed: %s", model, _describe(error))

                    elapsed = time.perf_counter() - started
                    if waited_here < self._patience:
                        pause = RATE_LIMIT_PAUSE if _is_rate_limit(last_error) else 1.0
                        time.sleep(pause)
                        waited_here += pause + elapsed
                        self.waited += pause + elapsed
                        continue
                    if isinstance(last_error, APITimeoutError) or _is_rate_limit(last_error):
                        break
                    attempt += 1
                    time.sleep(0.5)
        raise LLMError(f"provedor indisponível: {_describe(last_error)}")

    def _stream_once(
        self, client: OpenAI, model: str, messages: list[dict], tools: list[dict]
    ) -> Iterator[TextDelta | ToolCalls | ModelUsed]:
        arguments = {"model": model, "messages": messages, "stream": True, "temperature": 0.4}
        if tools:
            arguments["tools"] = tools

        collector = ToolCallCollector()
        announced = False
        for chunk in client.chat.completions.create(**arguments):
            if not announced:
                announced = True
                yield ModelUsed(model)
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta.content:
                yield TextDelta(delta.content)
            for call in delta.tool_calls or []:
                collector.add(call)

        if collector.calls:
            yield ToolCalls(collector.calls)


def build_embedder(provider: Provider, cache_dir: Path) -> Embedder:
    client = OpenAI(api_key=provider.api_key, base_url=provider.base_url, timeout=30, max_retries=1)
    uses_task_prefix = provider.name == "gemini"

    def embed(texts: list[str]) -> np.ndarray:
        vectors = []
        for start in range(0, len(texts), EMBED_BATCH):
            response = client.embeddings.create(
                model=provider.embedding_model,
                input=texts[start : start + EMBED_BATCH],
                dimensions=EMBEDDING_DIMENSIONS,
            )
            vectors.extend(item.embedding for item in response.data)
        return np.array(vectors, dtype=np.float32)

    def embed_query(texts: list[str]) -> np.ndarray:
        if uses_task_prefix:
            texts = [f"task: search result | query: {text}" for text in texts]
        return embed(texts)

    return Embedder(embed, embed_query, provider.embedding_model, cache_dir)
