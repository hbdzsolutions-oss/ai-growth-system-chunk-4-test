from __future__ import annotations

from .models import AgentDefinition


class UnknownAgentError(KeyError):
    pass


class AgentRegistry:
    """Registry of standardized Agent Cores.

    Chunk 5 deliberately registers one agent only. More agents can be added later
    without changing the chat orchestration or persistence layers.
    """

    def __init__(self, agents: list[AgentDefinition]) -> None:
        self._agents = {agent.key: agent for agent in agents}

    def get(self, key: str) -> AgentDefinition:
        try:
            return self._agents[key]
        except KeyError as exc:
            raise UnknownAgentError(key) from exc

    def all(self) -> list[AgentDefinition]:
        return list(self._agents.values())
