import os

from .base import AIProvider, UnsupportedProviderError
from .gemini import GeminiProvider

DEFAULT_PROVIDER = "gemini"


def get_provider(name: str | None = None) -> AIProvider:
    """Return the configured provider adapter.

    Gemini is the only implemented adapter in Chunk 2.1. Adding another
    provider later should require a new adapter plus one registry entry here,
    without changing the application or conversation model.
    """
    selected = (name or os.getenv("AI_PROVIDER", DEFAULT_PROVIDER)).strip().lower()

    if selected == "gemini":
        return GeminiProvider()

    raise UnsupportedProviderError(
        f"Unsupported AI provider: {selected}. Configure a provider adapter first."
    )
