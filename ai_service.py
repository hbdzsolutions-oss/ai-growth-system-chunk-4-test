"""Compatibility facade for the validated provider-neutral AI service.

Chunk 5 moves agent behavior into Agent Core. Older callers/tests can keep using
this module while the platform runtime composes Agent Core + Business Brain +
Business Context through ChatOrchestrator.
"""
from providers.base import AIMessage, AIProvider

from ags.agent_core.default_agent import MAX_HISTORY_MESSAGES, UNKNOWN_ANSWER, WEBSITE_ASSISTANT
from ags.agent_core.prompt_builder import build_agent_instructions, build_agent_messages


def build_instructions(business_knowledge: str) -> str:
    return build_agent_instructions(business_knowledge, WEBSITE_ASSISTANT)


def build_messages(
    business_knowledge: str,
    history: list[AIMessage],
    current_message: str,
) -> list[AIMessage]:
    return build_agent_messages(business_knowledge, history, current_message, WEBSITE_ASSISTANT)


class AIService:
    """Provider-neutral execution service retained for legacy/local validation paths."""

    def __init__(self, provider: AIProvider) -> None:
        self.provider = provider

    def answer(
        self,
        business_knowledge: str,
        history: list[AIMessage],
        current_message: str,
    ) -> str:
        return self.provider.generate(build_messages(business_knowledge, history, current_message))
