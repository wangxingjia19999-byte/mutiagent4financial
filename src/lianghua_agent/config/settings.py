from dataclasses import dataclass
import os


def _get_bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Settings:
    openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "")
    openrouter_base_url: str = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    openrouter_model: str = os.getenv("OPENROUTER_MODEL", "anthropic/claude-3.5-sonnet")
    rag_enable: bool = _get_bool_env("RAG_ENABLE", True)
    rag_chroma_dir: str = os.getenv("RAG_CHROMA_DIR", ".chroma")
    alpha101_md_path: str = os.getenv("ALPHA101_MD_PATH", "data/Alpha101.md")
    rag_top_k: int = int(os.getenv("RAG_TOP_K", "4"))


settings = Settings()
