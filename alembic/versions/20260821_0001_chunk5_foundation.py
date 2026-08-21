"""chunk 5 platform foundation

Revision ID: 20260821_0001
Revises:
Create Date: 2026-08-21
"""
from alembic import op
import sqlalchemy as sa

revision = "20260821_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "businesses",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "agent_deployments",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("public_key", sa.String(length=120), nullable=False),
        sa.Column("business_id", sa.String(length=64), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent_key", sa.String(length=100), nullable=False),
        sa.Column("channel", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_agent_deployments_public_key", "agent_deployments", ["public_key"], unique=True)
    op.create_index("ix_agent_deployments_business_id", "agent_deployments", ["business_id"])

    op.create_table(
        "conversations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("deployment_id", sa.String(length=64), sa.ForeignKey("agent_deployments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("origin", sa.String(length=500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_conversations_deployment_id", "conversations", ["deployment_id"])
    op.create_index("ix_conversations_updated_at", "conversations", ["updated_at"])

    op.create_table(
        "messages",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("conversation_id", sa.String(length=36), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])
    op.create_index("ix_messages_created_at", "messages", ["created_at"])

    op.create_table(
        "knowledge_sources",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("business_id", sa.String(length=64), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_type", sa.String(length=30), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("source_uri", sa.String(length=2000), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("raw_content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_knowledge_sources_business_id", "knowledge_sources", ["business_id"])
    op.create_index("ix_knowledge_sources_content_hash", "knowledge_sources", ["content_hash"])

    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("source_id", sa.String(length=36), sa.ForeignKey("knowledge_sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("normalized_text", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_knowledge_documents_source_id", "knowledge_documents", ["source_id"])

    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("document_id", sa.String(length=36), sa.ForeignKey("knowledge_documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("business_id", sa.String(length=64), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("embedding_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_knowledge_chunks_document_id", "knowledge_chunks", ["document_id"])
    op.create_index("ix_knowledge_chunks_business_id", "knowledge_chunks", ["business_id"])

    if op.get_bind().dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
        op.execute("ALTER TABLE knowledge_chunks ADD COLUMN embedding_vector vector(256)")
        op.execute(
            "CREATE INDEX ix_knowledge_chunks_embedding_hnsw "
            "ON knowledge_chunks USING hnsw (embedding_vector vector_cosine_ops)"
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_knowledge_chunks_embedding_hnsw")
    op.drop_table("knowledge_chunks")
    op.drop_table("knowledge_documents")
    op.drop_table("knowledge_sources")
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_table("agent_deployments")
    op.drop_table("businesses")
