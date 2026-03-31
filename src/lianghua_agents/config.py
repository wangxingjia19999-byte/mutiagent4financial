from dataclasses import dataclass
import os

from dotenv import load_dotenv


load_dotenv()


@dataclass
class AgentSettings:
    openrouter_api_key: str
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    model: str = "openai/gpt-4o-mini"
    site_url: str | None = None
    app_name: str | None = None
    tushare_token: str | None = None
    rag_enable: bool = True
    rag_knowledge_dir: str = "knowledge"
    rag_chroma_dir: str = ".chroma"
    embedding_model: str = "text-embedding-3-small"
    temperature: float = 0.2

    @classmethod
    def from_env(cls) -> "AgentSettings":
        api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
        if not api_key:
            raise ValueError("缺少环境变量 OPENROUTER_API_KEY")

        return cls(
            openrouter_api_key=api_key,
            openrouter_base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            model=os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini"),
            site_url=os.getenv("OPENROUTER_SITE_URL"),
            app_name=os.getenv("OPENROUTER_APP_NAME"),
            tushare_token=os.getenv("TUSHARE_TOKEN"),
            rag_enable=os.getenv("RAG_ENABLE", "true").strip().lower() in {"1", "true", "yes", "on"},
            rag_knowledge_dir=os.getenv("RAG_KNOWLEDGE_DIR", "knowledge"),
            rag_chroma_dir=os.getenv("RAG_CHROMA_DIR", ".chroma"),
            embedding_model=os.getenv("OPENROUTER_EMBEDDING_MODEL", "text-embedding-3-small"),
        )
