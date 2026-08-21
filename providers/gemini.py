import os
from typing import Any

import httpx

from .base import (
    AIMessage,
    AIProvider,
    ProviderAPIError,
    ProviderConfigurationError,
    ProviderResponseError,
)


DEFAULT_GEMINI_MODEL = "gemini-3.5-flash-lite"
GEMINI_CHAT_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"


class GeminiProvider(AIProvider):
    """Gemini adapter. All Gemini-specific details stay in this file."""

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        raw_api_key = api_key if api_key is not None else os.getenv("GEMINI_API_KEY")
        self._api_key = raw_api_key.strip() if raw_api_key else None
        self._model = model or os.getenv("AI_MODEL", DEFAULT_GEMINI_MODEL).strip()

    @property
    def name(self) -> str:
        return "gemini"

    @property
    def model(self) -> str:
        return self._model

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key)

    def _payload(self, messages: list[AIMessage]) -> dict[str, Any]:
        return {
            "model": self.model,
            "messages": messages,
        }

    @staticmethod
    def _extract_text(data: dict[str, Any]) -> str:
        try:
            text = data["choices"][0]["message"]["content"]
            if isinstance(text, str) and text.strip():
                return text.strip()
        except (KeyError, IndexError, TypeError):
            pass
        raise ProviderResponseError("Model returned no readable text response.")

    def generate(self, messages: list[AIMessage]) -> str:
        if not self._api_key:
            raise ProviderConfigurationError(
                "Gemini is not configured on the server. Set GEMINI_API_KEY."
            )

        try:
            with httpx.Client(timeout=45.0) as client:
                response = client.post(
                    GEMINI_CHAT_URL,
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json=self._payload(messages),
                )
        except httpx.HTTPError as exc:
            raise ProviderAPIError(f"Could not reach model provider: {exc}") from exc

        if response.status_code >= 400:
            try:
                error_payload = response.json()
                message = error_payload.get("error", {}).get("message") or response.text
            except ValueError:
                message = response.text
            raise ProviderAPIError(f"Model API error: {message}")

        try:
            data = response.json()
        except ValueError as exc:
            raise ProviderResponseError("Model returned an invalid JSON response.") from exc

        return self._extract_text(data)
