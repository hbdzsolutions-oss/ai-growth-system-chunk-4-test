from __future__ import annotations

from ags.business_brain.ports import KnowledgeRepository
from ags.business_context.ports import ConversationRepository


class DashboardService:
    def __init__(
        self,
        conversation_repository: ConversationRepository,
        knowledge_repository: KnowledgeRepository,
        business_id: str,
        deployment_id: str,
    ) -> None:
        self.conversations = conversation_repository
        self.knowledge = knowledge_repository
        self.business_id = business_id
        self.deployment_id = deployment_id

    def overview(self) -> dict:
        business = self.conversations.get_business(self.business_id)
        deployment = self.conversations.get_deployment(self.deployment_id)
        conversations = self.conversations.list_conversations(self.deployment_id, 100)
        sources = self.knowledge.list_sources(self.business_id)
        return {
            "business": {"id": business.id, "name": business.name},
            "deployment": {
                "id": deployment.id,
                "name": deployment.name,
                "agent_key": deployment.agent_key,
                "channel": deployment.channel,
                "status": "active" if deployment.is_active else "inactive",
            },
            "conversation_count": len(conversations),
            "knowledge_source_count": len(sources),
        }
