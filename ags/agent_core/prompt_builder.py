from __future__ import annotations

from providers.base import AIMessage

from .default_agent import WEBSITE_ASSISTANT
from .models import AgentDefinition


def build_agent_instructions(
    business_knowledge: str,
    agent: AgentDefinition = WEBSITE_ASSISTANT,
) -> str:
    knowledge = business_knowledge.strip() or "No relevant business information was retrieved for this turn."
    return f"{agent.instructions.strip()}\n\nBUSINESS KNOWLEDGE:\n{knowledge}"


def build_agent_messages(
    business_knowledge: str,
    history: list[AIMessage],
    current_message: str,
    agent: AgentDefinition = WEBSITE_ASSISTANT,
) -> list[AIMessage]:
    messages: list[AIMessage] = [
        {"role": "system", "content": build_agent_instructions(business_knowledge, agent)}
    ]
    messages.extend(history[-agent.max_history_messages :])
    messages.append({"role": "user", "content": current_message.strip()})
    return messages
