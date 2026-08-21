from __future__ import annotations

import os
from dataclasses import dataclass


DEFAULT_BUSINESS_ID = "northstar-botanics"
DEFAULT_DEPLOYMENT_ID = "northstar-website-assistant"
DEFAULT_DEPLOYMENT_KEY = "northstar-website-default"


@dataclass(frozen=True)
class Settings:
    database_url: str
    default_business_id: str
    default_deployment_id: str
    default_deployment_key: str
    retrieval_limit: int


def get_settings() -> Settings:
    return Settings(
        database_url=os.getenv("DATABASE_URL", "sqlite:///./data/ags.db").strip(),
        default_business_id=os.getenv("DEFAULT_BUSINESS_ID", DEFAULT_BUSINESS_ID).strip(),
        default_deployment_id=os.getenv("DEFAULT_DEPLOYMENT_ID", DEFAULT_DEPLOYMENT_ID).strip(),
        default_deployment_key=os.getenv("DEFAULT_DEPLOYMENT_KEY", DEFAULT_DEPLOYMENT_KEY).strip(),
        retrieval_limit=max(1, int(os.getenv("KNOWLEDGE_RETRIEVAL_LIMIT", "5"))),
    )
