"""add deduplicated member lifecycle events for statistics

Revision ID: 0017_member_lifecycle_events
Revises: 0016_remove_obsolete_media_label
"""

from alembic import op
import sqlalchemy as sa

revision = "0017_member_lifecycle_events"
down_revision = "0016_remove_obsolete_media_label"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "member_lifecycle_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("event_type", sa.String(16), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("retention_until", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("event_type IN ('member_join', 'member_leave')", name="ck_member_lifecycle_event_type"),
        sa.UniqueConstraint("guild_id", "user_id", "event_type", "occurred_at", name="uq_member_lifecycle_delivery"),
    )
    op.create_index(
        "idx_member_lifecycle_guild_occurred",
        "member_lifecycle_events",
        ["guild_id", "occurred_at"],
    )
    op.create_index(
        "idx_member_lifecycle_retention",
        "member_lifecycle_events",
        ["retention_until"],
    )


def downgrade() -> None:
    op.drop_index("idx_member_lifecycle_retention", table_name="member_lifecycle_events")
    op.drop_index("idx_member_lifecycle_guild_occurred", table_name="member_lifecycle_events")
    op.drop_table("member_lifecycle_events")
