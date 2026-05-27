import os
from typing import Dict, Any


def setup_poe_env() -> None:
    """Map POE_* env vars to OpenAI-compatible env vars used by SDKs."""
    poe_key = os.getenv("POE_API_KEY")
    poe_base = os.getenv("POE_BASE_URL", "https://api.poe.com/v1")
    force_map = os.getenv("POE_FORCE_MAP", "1") != "0"

    # Priority: if OPENAI_API_KEY already set, we don't overwrite unless forced.
    # Support POE_API_KEY: if provided, map it to OPENAI_API_KEY so existing
    # OpenAI-compatible clients can use Poe transparently.
    if poe_key and (force_map or not os.getenv("OPENAI_API_KEY")):
        os.environ["OPENAI_API_KEY"] = poe_key

    if poe_base and (force_map or not os.getenv("OPENAI_BASE_URL")):
        os.environ["OPENAI_BASE_URL"] = poe_base


def resolve_poe_model(default_model: str = "GPT-5.4") -> str:
    """Resolve model name from env, fallback to a safe Poe model id."""
    return os.getenv("POE_MODEL") or os.getenv("OPENAI_MODEL") or default_model


def get_openai_client_kwargs() -> Dict[str, Any]:
    """Return kwargs for openai.OpenAI / AsyncOpenAI clients."""
    setup_poe_env()

    kwargs: Dict[str, Any] = {
        "api_key": os.getenv("OPENAI_API_KEY"),
    }

    base_url = os.getenv("OPENAI_BASE_URL")
    if base_url:
        kwargs["base_url"] = base_url

    # Add default headers for Poe API
    kwargs["default_headers"] = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    return kwargs

