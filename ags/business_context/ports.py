from __future__ import annotations

from abc import ABC, abstractmethod

from .models import Business, Conversation, Deployment, Message


class ConversationNotFoundError(LookupError):
    pass


class DeploymentNotFoundError(LookupError):
    pass


class ConversationRepository(ABC):
    @abstractmethod
    def get_business(self, business_id: str) -> Business:
        raise NotImplementedError

    @abstractmethod
    def get_deployment(self, deployment_id: str) -> Deployment:
        raise NotImplementedError

    @abstractmethod
    def get_deployment_by_public_key(self, public_key: str) -> Deployment:
        raise NotImplementedError

    @abstractmethod
    def get_or_create_conversation(
        self,
        deployment: Deployment,
        origin: str,
        conversation_id: str | None,
    ) -> Conversation:
        raise NotImplementedError

    @abstractmethod
    def append_message(self, conversation_id: str, role: str, content: str) -> Message:
        raise NotImplementedError

    @abstractmethod
    def list_recent_messages(self, conversation_id: str, limit: int) -> list[Message]:
        raise NotImplementedError

    @abstractmethod
    def list_conversations(self, deployment_id: str | None = None, limit: int = 100) -> list[dict]:
        raise NotImplementedError

    @abstractmethod
    def get_conversation_with_messages(self, conversation_id: str) -> dict:
        raise NotImplementedError
