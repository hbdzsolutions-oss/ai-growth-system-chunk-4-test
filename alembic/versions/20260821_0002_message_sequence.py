"""add deterministic message sequencing

Revision ID: 20260821_0002
Revises: 20260821_0001
Create Date: 2026-08-21
"""

from alembic import op
import sqlalchemy as sa


revision = "20260821_0002"
down_revision = "20260821_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Conversation-owned monotonic sequence counter.
    op.add_column(
        "conversations",
        sa.Column(
            "next_message_sequence",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )

    # Temporarily nullable while existing validation data is backfilled.
    op.add_column(
        "messages",
        sa.Column("sequence", sa.Integer(), nullable=True),
    )

    bind = op.get_bind()

    messages = sa.table(
        "messages",
        sa.column("id", sa.String()),
        sa.column("conversation_id", sa.String()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("sequence", sa.Integer()),
    )

    conversations = sa.table(
        "conversations",
        sa.column("id", sa.String()),
        sa.column("next_message_sequence", sa.Integer()),
    )

    # Existing Chunk 5 validation messages predate explicit sequencing.
    # Give them a deterministic historical order.
    rows = bind.execute(
        sa.select(
            messages.c.id,
            messages.c.conversation_id,
        ).order_by(
            messages.c.conversation_id,
            messages.c.created_at,
            messages.c.id,
        )
    ).fetchall()

    counters: dict[str, int] = {}

    for row in rows:
        conversation_id = row.conversation_id
        next_value = counters.get(conversation_id, 0) + 1
        counters[conversation_id] = next_value

        bind.execute(
            messages.update()
            .where(messages.c.id == row.id)
            .values(sequence=next_value)
        )

    for conversation_id, final_sequence in counters.items():
        bind.execute(
            conversations.update()
            .where(conversations.c.id == conversation_id)
            .values(next_message_sequence=final_sequence)
        )

    # batch_alter_table also keeps this migration SQLite-compatible.
    with op.batch_alter_table("messages") as batch:
        batch.alter_column(
            "sequence",
            existing_type=sa.Integer(),
            nullable=False,
        )
        batch.create_unique_constraint(
            "uq_messages_conversation_sequence",
            ["conversation_id", "sequence"],
        )

    with op.batch_alter_table("conversations") as batch:
        batch.alter_column(
            "next_message_sequence",
            existing_type=sa.Integer(),
            server_default=None,
        )


def downgrade() -> None:
    with op.batch_alter_table("messages") as batch:
        batch.drop_constraint(
            "uq_messages_conversation_sequence",
            type_="unique",
        )
        batch.drop_column("sequence")

    with op.batch_alter_table("conversations") as batch:
        batch.drop_column("next_message_sequence")