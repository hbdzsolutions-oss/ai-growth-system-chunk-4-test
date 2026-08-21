from __future__ import annotations

from dataclasses import dataclass

from providers.base import AIProvider

from ags.agent_core.prompt_builder import build_agent_messages
from ags.agent_core.registry import AgentRegistry
from ags.business_brain.ports import KnowledgeRetriever
from ags.business_context.ports import ConversationRepository


@dataclass(frozen=True)
class ChatResult:
    conversation_id: str
    answer: str


class ChatOrchestrator:
    """Application use-case coordinating the three non-negotiable layers."""

    def __init__(
        self,
        conversation_repository: ConversationRepository,
        knowledge_retriever: KnowledgeRetriever,
        agent_registry: AgentRegistry,
        ai_provider: AIProvider,
        retrieval_limit: int = 5,
    ) -> None:
        self.conversations = conversation_repository
        self.knowledge = knowledge_retriever
        self.agents = agent_registry
        self.ai_provider = ai_provider
        self.retrieval_limit = retrieval_limit

    def respond(
        self,
        *,
        deployment_key: str,
        origin: str,
        current_message: str,
        conversation_id: str | None = None,
    ) -> ChatResult:
        deployment = self.conversations.get_deployment_by_public_key(deployment_key)
        conversation = self.conversations.get_or_create_conversation(deployment, origin, conversation_id)
        agent = self.agents.get(deployment.agent_key)
        history_rows = self.conversations.list_recent_messages(
            conversation.id, agent.max_history_messages
        )
        history = [{"role": item.role, "content": item.content} for item in history_rows]
        retrieved = self.knowledge.retrieve(
            deployment.business_id, current_message, limit=self.retrieval_limit
        )
        knowledge_text = "\n\n---\n\n".join(item.content for item in retrieved)
        messages = build_agent_messages(
            business_knowledge=knowledge_text,
            history=history,
            current_message=current_message,
            agent=agent,
        )

        self.conversations.append_message(conversation.id, "user", current_message)
        answer = self.ai_provider.generate(messages)
        self.conversations.append_message(conversation.id, "assistant", answer)
        return ChatResult(conversation_id=conversation.id, answer=answer)
