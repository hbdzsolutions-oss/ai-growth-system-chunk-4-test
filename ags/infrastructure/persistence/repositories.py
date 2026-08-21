from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select, text, update
from sqlalchemy.orm import joinedload

from ags.business_brain.ports import KnowledgeRepository
from ags.business_context.models import Business, Conversation, Deployment, Message
from ags.business_context.ports import ConversationNotFoundError, ConversationRepository, DeploymentNotFoundError

from .database import Database
from .schema import (
    AgentDeploymentRecord,
    BusinessRecord,
    ConversationRecord,
    KnowledgeChunkRecord,
    KnowledgeDocumentRecord,
    KnowledgeSourceRecord,
    MessageRecord,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _deployment(row: AgentDeploymentRecord) -> Deployment:
    return Deployment(
        id=row.id,
        public_key=row.public_key,
        business_id=row.business_id,
        agent_key=row.agent_key,
        channel=row.channel,
        name=row.name,
        is_active=row.is_active,
    )


def _conversation(row: ConversationRecord) -> Conversation:
    return Conversation(row.id, row.deployment_id, row.origin, row.created_at, row.updated_at)


def _message(row: MessageRecord) -> Message:
    return Message(row.id, row.conversation_id, row.role, row.content, row.sequence, row.created_at)


class SqlAlchemyConversationRepository(ConversationRepository):
    def __init__(self, database: Database) -> None:
        self.database = database

    def get_business(self, business_id: str) -> Business:
        with self.database.session_factory() as session:
            row = session.get(BusinessRecord, business_id)
            if row is None:
                raise LookupError(business_id)
            return Business(id=row.id, name=row.name)

    def get_deployment(self, deployment_id: str) -> Deployment:
        with self.database.session_factory() as session:
            row = session.get(AgentDeploymentRecord, deployment_id)
            if row is None:
                raise DeploymentNotFoundError(deployment_id)
            return _deployment(row)

    def get_deployment_by_public_key(self, public_key: str) -> Deployment:
        with self.database.session_factory() as session:
            row = session.scalar(
                select(AgentDeploymentRecord).where(
                    AgentDeploymentRecord.public_key == public_key,
                    AgentDeploymentRecord.is_active.is_(True),
                )
            )
            if row is None:
                raise DeploymentNotFoundError(public_key)
            return _deployment(row)

    def get_or_create_conversation(self, deployment: Deployment, origin: str, conversation_id: str | None) -> Conversation:
        with self.database.session_factory() as session:
            if conversation_id:
                row = session.scalar(select(ConversationRecord).where(ConversationRecord.id == conversation_id))
                if row is None or row.deployment_id != deployment.id or row.origin != origin:
                    raise ConversationNotFoundError(conversation_id)
                return _conversation(row)
            row = ConversationRecord(
                id=str(uuid.uuid4()),
                deployment_id=deployment.id,
                origin=origin,
            )
            session.add(row)
            session.commit()
            return _conversation(row)

    def append_message(self, conversation_id: str, role: str, content: str) -> Message:
        with self.database.session_factory() as session:
            next_sequence = session.scalar(
                update(ConversationRecord)
                .where(ConversationRecord.id == conversation_id)
                .values(
                    next_message_sequence=ConversationRecord.next_message_sequence + 1,
                    updated_at=_utcnow(),
                )
                .returning(ConversationRecord.next_message_sequence)
            )
            if next_sequence is None:
                raise ConversationNotFoundError(conversation_id)

            row = MessageRecord(
                id=str(uuid.uuid4()),
                conversation_id=conversation_id,
                sequence=int(next_sequence),
                role=role,
                content=content.strip(),
            )
            session.add(row)
            session.commit()
            return _message(row)

    def list_recent_messages(self, conversation_id: str, limit: int) -> list[Message]:
        with self.database.session_factory() as session:
            rows = list(
                session.scalars(
                    select(MessageRecord)
                    .where(MessageRecord.conversation_id == conversation_id)
                    .order_by(MessageRecord.sequence.desc())
                    .limit(limit)
                )
            )
            rows.reverse()
            return [_message(row) for row in rows]

    def list_conversations(self, deployment_id: str | None = None, limit: int = 100) -> list[dict]:
        with self.database.session_factory() as session:
            message_count = func.count(MessageRecord.id).label("message_count")
            last_message = func.max(MessageRecord.created_at).label("last_message_at")
            stmt = (
                select(ConversationRecord, AgentDeploymentRecord, message_count, last_message)
                .join(AgentDeploymentRecord, AgentDeploymentRecord.id == ConversationRecord.deployment_id)
                .outerjoin(MessageRecord, MessageRecord.conversation_id == ConversationRecord.id)
                .group_by(ConversationRecord.id, AgentDeploymentRecord.id)
                .order_by(ConversationRecord.updated_at.desc())
                .limit(limit)
            )
            if deployment_id:
                stmt = stmt.where(ConversationRecord.deployment_id == deployment_id)
            result = []
            for conversation, deployment, count, last_at in session.execute(stmt):
                result.append(
                    {
                        "id": conversation.id,
                        "origin": conversation.origin,
                        "created_at": conversation.created_at,
                        "updated_at": conversation.updated_at,
                        "last_message_at": last_at,
                        "message_count": int(count or 0),
                        "deployment_id": deployment.id,
                        "deployment_name": deployment.name,
                        "agent_key": deployment.agent_key,
                    }
                )
            return result

    def get_conversation_with_messages(self, conversation_id: str) -> dict:
        with self.database.session_factory() as session:
            conversation = session.get(ConversationRecord, conversation_id)
            if conversation is None:
                raise ConversationNotFoundError(conversation_id)
            deployment = session.get(AgentDeploymentRecord, conversation.deployment_id)
            messages = list(
                session.scalars(
                    select(MessageRecord)
                    .where(MessageRecord.conversation_id == conversation_id)
                    .order_by(MessageRecord.sequence.asc())
                )
            )
            return {
                "id": conversation.id,
                "origin": conversation.origin,
                "created_at": conversation.created_at,
                "updated_at": conversation.updated_at,
                "deployment_id": conversation.deployment_id,
                "deployment_name": deployment.name if deployment else conversation.deployment_id,
                "messages": [
                    {"id": m.id, "role": m.role, "content": m.content, "sequence": m.sequence, "created_at": m.created_at}
                    for m in messages
                ],
            }


class SqlAlchemyKnowledgeRepository(KnowledgeRepository):
    def __init__(self, database: Database) -> None:
        self.database = database

    def create_source_with_document_and_chunks(
        self,
        *,
        business_id: str,
        source_type: str,
        title: str,
        source_uri: str | None,
        raw_content: str,
        normalized_text: str,
        content_hash: str,
        chunks: list[str],
        embeddings: list[list[float]],
        metadata: dict[str, str],
    ) -> dict:
        source_id = str(uuid.uuid4())
        document_id = str(uuid.uuid4())
        with self.database.session_factory() as session:
            source = KnowledgeSourceRecord(
                id=source_id,
                business_id=business_id,
                source_type=source_type,
                title=title,
                source_uri=source_uri,
                status="ready",
                raw_content=raw_content,
                content_hash=content_hash,
            )
            document = KnowledgeDocumentRecord(
                id=document_id,
                source_id=source_id,
                normalized_text=normalized_text,
                metadata_json=metadata,
                version=1,
            )
            source.documents.append(document)
            chunk_rows: list[tuple[KnowledgeChunkRecord, list[float]]] = []
            for index, (content, embedding) in enumerate(zip(chunks, embeddings)):
                chunk = KnowledgeChunkRecord(
                    id=str(uuid.uuid4()),
                    business_id=business_id,
                    position=index,
                    content=content,
                    metadata_json=metadata,
                    embedding_json=embedding,
                )
                document.chunks.append(chunk)
                chunk_rows.append((chunk, embedding))
            session.add(source)
            session.flush()
            if self.database.engine.dialect.name == "postgresql":
                for chunk, embedding in chunk_rows:
                    vector_literal = "[" + ",".join(f"{value:.12g}" for value in embedding) + "]"
                    session.execute(
                        text(
                            "UPDATE knowledge_chunks "
                            "SET embedding_vector = CAST(:embedding AS vector) "
                            "WHERE id = :chunk_id"
                        ),
                        {"embedding": vector_literal, "chunk_id": chunk.id},
                    )
            session.commit()
            return {
                "id": source.id,
                "business_id": source.business_id,
                "source_type": source.source_type,
                "title": source.title,
                "source_uri": source.source_uri,
                "status": source.status,
                "content_hash": source.content_hash,
                "chunk_count": len(chunks),
                "created_at": source.created_at,
                "updated_at": source.updated_at,
            }

    def list_sources(self, business_id: str) -> list[dict]:
        with self.database.session_factory() as session:
            rows = list(
                session.scalars(
                    select(KnowledgeSourceRecord)
                    .where(KnowledgeSourceRecord.business_id == business_id)
                    .options(joinedload(KnowledgeSourceRecord.documents).joinedload(KnowledgeDocumentRecord.chunks))
                    .order_by(KnowledgeSourceRecord.created_at.desc())
                ).unique()
            )
            return [
                {
                    "id": row.id,
                    "business_id": row.business_id,
                    "source_type": row.source_type,
                    "title": row.title,
                    "source_uri": row.source_uri,
                    "status": row.status,
                    "content_hash": row.content_hash,
                    "chunk_count": sum(len(doc.chunks) for doc in row.documents),
                    "created_at": row.created_at,
                    "updated_at": row.updated_at,
                }
                for row in rows
            ]

    def list_chunks(self, business_id: str) -> list[dict]:
        with self.database.session_factory() as session:
            rows = session.execute(
                select(KnowledgeChunkRecord, KnowledgeSourceRecord)
                .join(KnowledgeDocumentRecord, KnowledgeDocumentRecord.id == KnowledgeChunkRecord.document_id)
                .join(KnowledgeSourceRecord, KnowledgeSourceRecord.id == KnowledgeDocumentRecord.source_id)
                .where(KnowledgeChunkRecord.business_id == business_id, KnowledgeSourceRecord.status == "ready")
            )
            return [
                {
                    "id": chunk.id,
                    "content": chunk.content,
                    "embedding": [float(v) for v in chunk.embedding_json],
                    "source_title": source.title,
                    "source_type": source.source_type,
                    "source_uri": source.source_uri,
                }
                for chunk, source in rows
            ]

    def delete_source(self, business_id: str, source_id: str) -> None:
        with self.database.session_factory() as session:
            source = session.get(KnowledgeSourceRecord, source_id)
            if source is None or source.business_id != business_id:
                raise LookupError(source_id)
            session.delete(source)
            session.commit()
