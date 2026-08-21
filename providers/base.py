from abc import ABC, abstractmethod
from typing import TypedDict


class AIMessage(TypedDict):
    role: str
    content: str


class ProviderError(Exception):
    """Base error for model-provider failures."""


class ProviderConfigurationError(ProviderError):
    """The selected provider is not configured correctly."""


class UnsupportedProviderError(ProviderConfigurationError):
    """The requested provider has no adapter yet."""


class ProviderAPIError(ProviderError):
    """The provider API could not complete the request."""


class ProviderResponseError(ProviderError):
    """The provider returned a response we could not read."""


class AIProvider(ABC):
    """Minimal interface the application uses for any LLM provider."""

    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def model(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def is_configured(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def generate(self, messages: list[AIMessage]) -> str:
        """Generate one assistant response from provider-neutral messages."""
        raise NotImplementedError
