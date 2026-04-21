from __future__ import annotations

import hashlib
import math
import re
from pathlib import Path
from threading import Lock
from typing import Any

from lianghua_agent.config.settings import settings

try:
    from langchain_chroma import Chroma
    from langchain_core.documents import Document
except ImportError:
    Chroma = None
    Document = None


class _HashEmbeddings:
    def __init__(self, dimension: int = 384):
        self.dimension = dimension

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_text(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed_text(text)

    def _embed_text(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        tokens = re.findall(r"[a-zA-Z_]+|[\u4e00-\u9fff]+|\d+", text.lower())
        if not tokens:
            return vector

        for token in tokens:
            token_hash = hashlib.md5(token.encode("utf-8")).hexdigest()
            index = int(token_hash, 16) % self.dimension
            vector[index] += 1.0

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]


_RETRIEVER = None
_DOCS_CACHE: list[dict] | None = None
_LOCK = Lock()


def retrieve_alpha101_factors(query: str, top_k: int | None = None) -> list[dict]:
    k = top_k or settings.rag_top_k
    if settings.rag_enable:
        rag_results = _retrieve_with_chroma(query, k)
        if rag_results:
            return rag_results
    return _retrieve_with_keyword_fallback(query, k)


def _retrieve_with_chroma(query: str, top_k: int) -> list[dict]:
    if Chroma is None or Document is None:
        return []

    retriever = _get_retriever()
    if retriever is None:
        return []

    documents = retriever.invoke(query)
    results: list[dict] = []
    for doc in documents[:top_k]:
        metadata = doc.metadata or {}
        alpha_id = metadata.get("alpha_id", "")
        formula = metadata.get("formula", "")
        if alpha_id:
            results.append(
                {
                    "alpha_id": alpha_id,
                    "formula": formula,
                    "source": metadata.get("source", "Alpha101"),
                }
            )
    return results


def _get_retriever():
    global _RETRIEVER
    if _RETRIEVER is not None:
        return _RETRIEVER

    with _LOCK:
        if _RETRIEVER is not None:
            return _RETRIEVER

        docs = _load_alpha101_documents()
        if not docs:
            return None

        persist_dir = Path(settings.rag_chroma_dir).resolve() / "alpha101"
        persist_dir.mkdir(parents=True, exist_ok=True)

        vector_store = Chroma(
            collection_name="alpha101_factor_library",
            persist_directory=str(persist_dir),
            embedding_function=_HashEmbeddings(),
        )

        collection_data = vector_store.get(limit=1)
        if not collection_data.get("ids"):
            vector_store.add_documents(docs)

        _RETRIEVER = vector_store.as_retriever(search_kwargs={"k": settings.rag_top_k})
        return _RETRIEVER


def _load_alpha101_documents() -> list[Any]:
    path = Path(settings.alpha101_md_path).resolve()
    if not path.exists() or Document is None:
        return []

    content = path.read_text(encoding="utf-8")
    sections = re.findall(r"##\s+(Alpha_\d{3})\s*\n(.+?)(?=\n##\s+Alpha_\d{3}|\Z)", content, re.S)

    documents: list[Any] = []
    for alpha_id, formula_block in sections:
        formula = formula_block.strip()
        if not formula:
            continue

        text = f"{alpha_id}\n{formula}\n因子公式: {formula}"
        documents.append(
            Document(
                page_content=text,
                metadata={
                    "alpha_id": alpha_id,
                    "formula": formula,
                    "source": "Alpha101",
                },
            )
        )

    return documents


def _retrieve_with_keyword_fallback(query: str, top_k: int) -> list[dict]:
    docs = _load_alpha101_docs_for_fallback()
    if not docs:
        return []

    query_tokens = set(re.findall(r"[a-zA-Z_]+|[\u4e00-\u9fff]+|\d+", query.lower()))
    scored: list[tuple[int, dict]] = []

    for doc in docs:
        formula_tokens = set(re.findall(r"[a-zA-Z_]+|[\u4e00-\u9fff]+|\d+", doc["formula"].lower()))
        overlap = len(query_tokens.intersection(formula_tokens))
        scored.append((overlap, doc))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in scored[:top_k] if item[0] > 0] or [item[1] for item in scored[:top_k]]


def _load_alpha101_docs_for_fallback() -> list[dict]:
    global _DOCS_CACHE
    if _DOCS_CACHE is not None:
        return _DOCS_CACHE

    path = Path(settings.alpha101_md_path).resolve()
    if not path.exists():
        _DOCS_CACHE = []
        return _DOCS_CACHE

    content = path.read_text(encoding="utf-8")
    sections = re.findall(r"##\s+(Alpha_\d{3})\s*\n(.+?)(?=\n##\s+Alpha_\d{3}|\Z)", content, re.S)

    _DOCS_CACHE = [
        {
            "alpha_id": alpha_id,
            "formula": formula_block.strip(),
            "source": "Alpha101",
        }
        for alpha_id, formula_block in sections
        if formula_block.strip()
    ]
    return _DOCS_CACHE
