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
FIRST_BYTE_TIMEOUT = 25.0


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
        error.status_code in (408, 409, 429) or error.status_code >= 500
    )


class OpenAICompatibleLLM:
    def __init__(self, provider: Provider, timeout: float = FIRST_BYTE_TIMEOUT):
        self._client = OpenAI(
            api_key=provider.api_key, base_url=provider.base_url, timeout=timeout, max_retries=0
        )
        self._models = provider.chat_models

    def stream(
        self, messages: list[dict], tools: list[dict]
    ) -> Iterator[TextDelta | ToolCalls | ModelUsed]:
        last_error: Exception | None = None
        for model in self._models:
            for attempt in range(RETRIES_PER_MODEL):
                emitted = False
                try:
                    for event in self._stream_once(model, messages, tools):
                        emitted = True
                        yield event
                    return
                except Exception as error:
                    last_error = error
                    if isinstance(error, APIStatusError) and error.status_code in (401, 403):
                        raise LLMError("chave de API recusada", auth=True) from error
                    if emitted or not _is_retryable(error):
                        raise LLMError(str(error)[:300]) from error
                    log.warning("%s attempt %d failed: %s", model, attempt + 1, str(error)[:200])
                    if isinstance(error, APITimeoutError):
                        break
                    time.sleep(0.8 * (attempt + 1))
        raise LLMError(f"provedor indisponível: {str(last_error)[:200]}")

    def _stream_once(
        self, model: str, messages: list[dict], tools: list[dict]
    ) -> Iterator[TextDelta | ToolCalls | ModelUsed]:
        arguments = {"model": model, "messages": messages, "stream": True, "temperature": 0.4}
        if tools:
            arguments["tools"] = tools

        calls: dict[int, dict] = {}
        announced = False
        for chunk in self._client.chat.completions.create(**arguments):
            if not announced:
                announced = True
                yield ModelUsed(model)
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta.content:
                yield TextDelta(delta.content)
            for call in delta.tool_calls or []:
                entry = calls.setdefault(
                    call.index or 0, {"id": "", "name": "", "arguments": "", "extra": None}
                )
                entry["id"] = call.id or entry["id"]
                if call.function:
                    entry["name"] = call.function.name or entry["name"]
                    entry["arguments"] += call.function.arguments or ""
                extra = call.model_dump().get("extra_content")
                if extra:
                    entry["extra"] = extra

        if calls:
            yield ToolCalls(
                tuple(
                    ToolCall(c["id"], c["name"], c["arguments"] or "{}", c["extra"])
                    for _, c in sorted(calls.items())
                )
            )


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
