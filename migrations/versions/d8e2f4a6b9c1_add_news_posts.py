"""add news posts

Revision ID: d8e2f4a6b9c1
Revises: b2d9f6a4c1e7
Create Date: 2026-05-05 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "d8e2f4a6b9c1"
down_revision = "b2d9f6a4c1e7"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "news_posts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=220), nullable=False),
        sa.Column("slug", sa.String(length=240), nullable=False),
        sa.Column("author_name", sa.String(length=120), nullable=False),
        sa.Column("summary", sa.String(length=500), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("body_html", sa.Text(), nullable=False),
        sa.Column("images_json", sa.Text(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_news_posts_slug", "news_posts", ["slug"], unique=True)
    op.create_index("ix_news_posts_created_at", "news_posts", ["created_at"], unique=False)


def downgrade():
    op.drop_index("ix_news_posts_created_at", table_name="news_posts")
    op.drop_index("ix_news_posts_slug", table_name="news_posts")
    op.drop_table("news_posts")
