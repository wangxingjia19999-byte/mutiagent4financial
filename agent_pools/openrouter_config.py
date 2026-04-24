import os
from typing import Dict, Any


def setup_openrouter_env() -> None:
    """Map OPENROUTER_* env vars to OpenAI-compatible env vars used by SDKs."""
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    openrouter_base = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

    if openrouter_key and not os.getenv("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = openrouter_key

    if openrouter_base and not os.getenv("OPENAI_BASE_URL"):
        os.environ["OPENAI_BASE_URL"] = openrouter_base


def resolve_openrouter_model(default_model: str = "openai/gpt-4o-mini") -> str:
    """Resolve model name from env, fallback to a safe OpenRouter model id."""
    return os.getenv("OPENROUTER_MODEL") or os.getenv("OPENAI_MODEL") or default_model


def get_openai_client_kwargs() -> Dict[str, Any]:
    """Return kwargs for openai.OpenAI / AsyncOpenAI clients."""
    setup_openrouter_env()

    kwargs: Dict[str, Any] = {
        "api_key": os.getenv("OPENAI_API_KEY"),
    }

    base_url = os.getenv("OPENAI_BASE_URL")
    if base_url:
        kwargs["base_url"] = base_url

    site_url = os.getenv("OPENROUTER_SITE_URL")
    app_name = os.getenv("OPENROUTER_APP_NAME")
    if site_url or app_name:
        headers: Dict[str, str] = {}
        if site_url:
            headers["HTTP-Referer"] = site_url
        if app_name:
            headers["X-Title"] = app_name
        kwargs["default_headers"] = headers

    return kwargs
