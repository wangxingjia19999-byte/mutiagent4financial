from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Iterable

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings

from .config import AgentSettings


COLLECTION_NAME = "lianghua_finance_knowledge"
MANIFEST_FILE = "index_manifest.json"


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _knowledge_dir(settings: AgentSettings) -> Path:
    return (_project_root() / settings.rag_knowledge_dir).resolve()


def _chroma_dir(settings: AgentSettings) -> Path:
    return (_project_root() / settings.rag_chroma_dir).resolve()


def resolve_chroma_dir(settings: AgentSettings) -> str:
    return str(_chroma_dir(settings))


def _iter_knowledge_files(knowledge_dir: Path) -> Iterable[Path]:
    if not knowledge_dir.exists() or not knowledge_dir.is_dir():
        return []
    return sorted(p for p in knowledge_dir.rglob("*") if p.is_file() and p.suffix.lower() in {".md", ".txt"})


def _file_sha256(path: Path) -> str:
    content = path.read_bytes()
    return hashlib.sha256(content).hexdigest()


def _build_manifest(knowledge_dir: Path) -> dict[str, str]:
    manifest: dict[str, str] = {}
    for path in _iter_knowledge_files(knowledge_dir):
        rel = str(path.relative_to(_project_root()))
        manifest[rel] = _file_sha256(path)
    return manifest


def _load_manifest(chroma_dir: Path) -> dict[str, str]:
    manifest_path = chroma_dir / MANIFEST_FILE
    if not manifest_path.exists():
        return {}
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items()}
    except Exception:
        return {}
    return {}


def _save_manifest(chroma_dir: Path, manifest: dict[str, str]) -> None:
    manifest_path = chroma_dir / MANIFEST_FILE
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def _chunk_text(text: str, chunk_size: int = 900, overlap: int = 120) -> list[str]:
    chunks: list[str] = []
    cleaned = text.strip()
    if not cleaned:
        return chunks

    start = 0
    total = len(cleaned)
    while start < total:
        end = min(start + chunk_size, total)
        chunks.append(cleaned[start:end])
        if end == total:
            break
        start = max(0, end - overlap)
    return chunks


def _normalize_symbol(symbol: str) -> str:
    return symbol.strip().upper()


def _extract_symbols(path: Path, text: str) -> list[str]:
    symbols: set[str] = set()

    for match in re.findall(r"\b\d{6}\.(?:SZ|SH|BJ)\b", path.name.upper()):
        symbols.add(_normalize_symbol(match))

    head = text[:2000]
    for line in head.splitlines():
        striped = line.strip()
        lower = striped.lower()
        if lower.startswith("symbols:") or striped.startswith("股票代码:"):
            _, value = striped.split(":", 1)
            for token in re.split(r"[,，;；\s]+", value):
                normalized = _normalize_symbol(token)
                if re.fullmatch(r"\d{6}\.(?:SZ|SH|BJ)", normalized):
                    symbols.add(normalized)

    for match in re.findall(r"\b\d{6}\.(?:SZ|SH|BJ)\b", head.upper()):
        symbols.add(_normalize_symbol(match))

    if not symbols:
        return ["ALL"]
    return sorted(symbols)


def _build_documents(knowledge_dir: Path) -> list[Document]:
    docs: list[Document] = []
    for path in _iter_knowledge_files(knowledge_dir):
        text = path.read_text(encoding="utf-8", errors="ignore").strip()
        if not text:
            continue
        rel = str(path.relative_to(_project_root()))
        symbols = _extract_symbols(path, text)
        symbols_text = "|".join(symbols)
        for idx, chunk in enumerate(_chunk_text(text)):
            docs.append(
                Document(
                    page_content=chunk,
                    metadata={
                        "source": rel,
                        "chunk_index": idx,
                        "symbols_text": symbols_text,
                    },
                )
            )
    return docs


def build_or_update_rag_index(settings: AgentSettings, force_rebuild: bool = False) -> bool:
    """Build or update Chroma index. Returns True if indexing was executed."""
    knowledge_dir = _knowledge_dir(settings)
    chroma_dir = _chroma_dir(settings)
    chroma_dir.mkdir(parents=True, exist_ok=True)

    new_manifest = _build_manifest(knowledge_dir)
    old_manifest = _load_manifest(chroma_dir)

    need_rebuild = force_rebuild or (new_manifest != old_manifest)
    if not need_rebuild:
        return False

    embeddings = OpenAIEmbeddings(
        model=settings.embedding_model,
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
    )

    vector_store = Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=str(chroma_dir),
    )

    try:
        vector_store.delete_collection()
    except Exception:
        pass

    vector_store = Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=str(chroma_dir),
    )

    docs = _build_documents(knowledge_dir)
    if docs:
        ids = [f"doc-{i}" for i in range(len(docs))]
        vector_store.add_documents(documents=docs, ids=ids)

    _save_manifest(chroma_dir, new_manifest)
    return True
