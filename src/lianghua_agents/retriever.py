from __future__ import annotations

from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings

from .config import AgentSettings
from .rag_indexer import COLLECTION_NAME, build_or_update_rag_index, resolve_chroma_dir


class FinanceKnowledgeRetriever:
    def __init__(self, settings: AgentSettings):
        self.settings = settings
        self._vector_store: Chroma | None = None

    def _ensure_vector_store(self) -> Chroma:
        if self._vector_store is not None:
            return self._vector_store

        build_or_update_rag_index(settings=self.settings, force_rebuild=False)

        embeddings = OpenAIEmbeddings(
            model=self.settings.embedding_model,
            api_key=self.settings.openrouter_api_key,
            base_url=self.settings.openrouter_base_url,
        )

        vector_store = Chroma(
            collection_name=COLLECTION_NAME,
            embedding_function=embeddings,
            persist_directory=resolve_chroma_dir(self.settings),
        )

        self._vector_store = vector_store
        return vector_store

    def retrieve(self, query: str, top_k: int = 4) -> str:
        if not self.settings.rag_enable:
            return ""

        try:
            vector_store = self._ensure_vector_store()
            docs = vector_store.similarity_search(query, k=top_k)
        except Exception:
            return ""

        if not docs:
            return ""

        blocks: list[str] = []
        for idx, doc in enumerate(docs, start=1):
            source = doc.metadata.get("source", "unknown")
            blocks.append(f"[参考{idx}] 来源: {source}\n{doc.page_content}")
        return "\n\n".join(blocks)
