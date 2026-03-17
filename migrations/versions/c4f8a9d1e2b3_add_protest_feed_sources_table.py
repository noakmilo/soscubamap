"""add protest feed sources table

Revision ID: c4f8a9d1e2b3
Revises: 9c4f1a7b2d8e
Create Date: 2026-03-17 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c4f8a9d1e2b3"
down_revision = "9c4f1a7b2d8e"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "protest_feed_sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("feed_url", sa.String(length=1000), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_protest_feed_sources_feed_url",
        "protest_feed_sources",
        ["feed_url"],
        unique=True,
    )
    op.create_index(
        "ix_protest_feed_sources_sort_order",
        "protest_feed_sources",
        ["sort_order"],
        unique=False,
    )
    op.create_index(
        "ix_protest_feed_sources_created_at",
        "protest_feed_sources",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_protest_feed_sources_updated_at",
        "protest_feed_sources",
        ["updated_at"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_protest_feed_sources_updated_at", table_name="protest_feed_sources")
    op.drop_index("ix_protest_feed_sources_created_at", table_name="protest_feed_sources")
    op.drop_index("ix_protest_feed_sources_sort_order", table_name="protest_feed_sources")
    op.drop_index("ix_protest_feed_sources_feed_url", table_name="protest_feed_sources")
    op.drop_table("protest_feed_sources")
