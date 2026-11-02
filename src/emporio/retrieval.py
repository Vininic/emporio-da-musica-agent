import hashlib
import logging
import math
import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from emporio.store import normalize_text

log = logging.getLogger(__name__)

RRF_K = 60
STOPWORDS = set(
    """a o as os um uma uns umas de do da dos das em no na nos nas por para pra pro com sem e ou que
    se eu voce vc voces meu minha tem ter tenho qual quais quanto quanta como quando onde ja nao sim
    ao aos me te lhe isso esse essa este esta aqui la mais muito pode posso vou quero gostaria sobre
    ser foi sou esta estou""".split()
)


def tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9]+", normalize_text(text))
    return [_stem(token) for token in tokens if token not in STOPWORDS]


def _stem(token: str) -> str:
    if len(token) > 4 and token.endswith("oes"):
        return token[:-3] + "ao"
    if len(token) > 4 and token.endswith("aes"):
        return token[:-3] + "ao"
    if len(token) > 3 and token.endswith("s"):
        return token[:-1]
    return token


class BM25:
    def __init__(self, documents: list[str], k1: float = 1.4, b: float = 0.75):
        self._k1 = k1
        self._b = b
        self._docs = [Counter(tokenize(document)) for document in documents]
        self._lengths = [sum(doc.values()) for doc in self._docs]
        self._average = sum(self._lengths) / max(len(self._lengths), 1)
        frequency: Counter[str] = Counter()
        for doc in self._docs:
            frequency.update(doc.keys())
        total = len(self._docs)
        self._idf = {
            term: math.log(1 + (total - count + 0.5) / (count + 0.5))
            for term, count in frequency.items()
        }

    def scores(self, query: str) -> list[float]:
        terms = tokenize(query)
        results = []
        for doc, length in zip(self._docs, self._lengths, strict=True):
            score = 0.0
            for term in terms:
                count = doc.get(term, 0)
                if count:
                    norm = 1 - self._b + self._b * length / self._average
                    score += self._idf[term] * count * (self._k1 + 1) / (count + self._k1 * norm)
            results.append(score)
        return results


class VectorIndex:
    def __init__(self, matrix: np.ndarray):
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        self._matrix = matrix / np.where(norms == 0, 1, norms)

    def scores(self, query_vector: np.ndarray) -> np.ndarray:
        norm = np.linalg.norm(query_vector)
        return self._matrix @ (query_vector / (norm if norm else 1))


Embed = Callable[[list[str]], np.ndarray]


@dataclass(frozen=True)
class Document:
    id: str
    title: str
    text: str


@dataclass(frozen=True)
class Hit:
    id: str
    score: float
    keyword_rank: int | None
    vector_rank: int | None


class Embedder:
    def __init__(self, documents_fn: Embed, query_fn: Embed, model: str, cache_dir: Path):
        self.embed_documents = documents_fn
        self.embed_query = query_fn
        self.model = model
        self.cache_dir = cache_dir

    def matrix_for(self, documents: list[Document]) -> np.ndarray:
        digest = hashlib.sha256(
            "\n".join([self.model, *(f"{d.id}|{d.title}|{d.text}" for d in documents)]).encode()
        ).hexdigest()[:16]
        path = self.cache_dir / f"{digest}.npy"
        if path.exists():
            return np.load(path)

        vectors = self.embed_documents([f"title: {d.title} | text: {d.text}" for d in documents])
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            np.save(path, vectors)
        except OSError as error:
            log.warning("could not cache embeddings: %s", error)
        return vectors


class HybridIndex:
    def __init__(self, documents: list[Document], embedder: Embedder | None = None):
        self._documents = documents
        self._ids = [document.id for document in documents]
        self._bm25 = BM25([f"{d.title} {d.title} {d.text}" for d in documents])
        self._embedder = embedder
        self._vectors: VectorIndex | None = None
        if embedder is not None:
            try:
                self._vectors = VectorIndex(embedder.matrix_for(documents))
            except Exception as error:
                log.warning("embeddings unavailable, using keyword search only: %s", error)

    @property
    def uses_vectors(self) -> bool:
        return self._vectors is not None

    def search(self, query: str, top_k: int = 5, allowed: set[str] | None = None) -> list[Hit]:
        keyword = self._bm25.scores(query)
        keyword_order = [
            i
            for i in sorted(range(len(keyword)), key=lambda i: keyword[i], reverse=True)
            if keyword[i] > 0 and self._is_allowed(i, allowed)
        ]
        vector_order = self._vector_order(query, allowed)

        keyword_ranks = {i: rank for rank, i in enumerate(keyword_order)}
        vector_ranks = {i: rank for rank, i in enumerate(vector_order)}
        fused = {
            i: sum(
                1 / (RRF_K + ranks[i] + 1) for ranks in (keyword_ranks, vector_ranks) if i in ranks
            )
            for i in {*keyword_ranks, *vector_ranks}
        }
        ordered = sorted(fused, key=lambda i: (-fused[i], i))[:top_k]
        return [
            Hit(self._ids[i], round(fused[i], 5), keyword_ranks.get(i), vector_ranks.get(i))
            for i in ordered
        ]

    def _is_allowed(self, index: int, allowed: set[str] | None) -> bool:
        return allowed is None or self._ids[index] in allowed

    def _vector_order(self, query: str, allowed: set[str] | None) -> list[int]:
        if self._vectors is None or self._embedder is None:
            return []
        try:
            vector = self._embedder.embed_query([query])[0]
        except Exception as error:
            log.warning("query embedding failed, using keyword search only: %s", error)
            return []
        scores = self._vectors.scores(vector)
        return [i for i in np.argsort(-scores).tolist() if self._is_allowed(i, allowed)]
