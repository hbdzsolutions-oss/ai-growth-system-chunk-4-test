from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Business:
    id: str
    name: str


@dataclass(frozen=True)
class Deployment:
    id: str
    public_key: str
    business_id: str
    agent_key: str
    channel: str
    name: str
    is_active: bool


@dataclass(frozen=True)
class Conversation:
    id: str
    deployment_id: str
    origin: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class Message:
    id: str
    conversation_id: str
    role: str
    content: str
    sequence: int
    created_at: datetime
