from __future__ import annotations

from pathlib import Path

from sqlalchemy import select, text

from ags.business_brain.ingestion import KnowledgeIngestionService
from ags.config import Settings

from .database import Database
from .schema import AgentDeploymentRecord, Base, BusinessRecord, KnowledgeSourceRecord


def create_schema(database: Database) -> None:
    Base.metadata.create_all(database.engine)
    if database.engine.dialect.name == "postgresql":
        # Production vector search uses PostgreSQL + pgvector, but the domain and
        # application layers remain unaware of that infrastructure choice.
        with database.engine.begin() as connection:
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            connection.execute(
                text(
                    "ALTER TABLE knowledge_chunks "
                    "ADD COLUMN IF NOT EXISTS embedding_vector vector(256)"
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_knowledge_chunks_embedding_hnsw "
                    "ON knowledge_chunks USING hnsw (embedding_vector vector_cosine_ops)"
                )
            )


def seed_foundation(
    database: Database,
    settings: Settings,
    ingestion_service: KnowledgeIngestionService,
    seed_file: Path,
) -> None:
    with database.session_factory() as session:
        business = session.get(BusinessRecord, settings.default_business_id)
        if business is None:
            business = BusinessRecord(id=settings.default_business_id, name="Northstar Botanics")
            session.add(business)
        deployment = session.get(AgentDeploymentRecord, settings.default_deployment_id)
        if deployment is None:
            deployment = AgentDeploymentRecord(
                id=settings.default_deployment_id,
                public_key=settings.default_deployment_key,
                business_id=settings.default_business_id,
                agent_key="website_assistant",
                channel="website",
                name="Website Assistant",
                is_active=True,
            )
            session.add(deployment)
        session.commit()
        has_knowledge = session.scalar(
            select(KnowledgeSourceRecord.id)
            .where(KnowledgeSourceRecord.business_id == settings.default_business_id)
            .limit(1)
        )
    if has_knowledge is None:
        ingestion_service.ingest(
            business_id=settings.default_business_id,
            source_type="manual",
            title="Northstar founding knowledge",
            value=seed_file.read_text(encoding="utf-8"),
        )
