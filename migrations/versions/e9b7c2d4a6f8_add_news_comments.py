"""add news comments

Revision ID: e9b7c2d4a6f8
Revises: d8e2f4a6b9c1
Create Date: 2026-05-05 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "e9b7c2d4a6f8"
down_revision = "d8e2f4a6b9c1"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "news_comments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("post_id", sa.Integer(), sa.ForeignKey("news_posts.id"), nullable=False),
        sa.Column("parent_id", sa.Integer(), sa.ForeignKey("news_comments.id", ondelete="CASCADE"), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("body_html", sa.Text(), nullable=False),
        sa.Column("author_label", sa.String(length=80), nullable=False),
        sa.Column("upvotes", sa.Integer(), nullable=True),
        sa.Column("downvotes", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )


def downgrade():
    op.drop_table("news_comments")
