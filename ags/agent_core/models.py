from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentDefinition:
    """Company-owned agent intelligence. Never contains client business facts."""

    key: str
    name: str
    role: str
    instructions: str
    max_history_messages: int = 8
