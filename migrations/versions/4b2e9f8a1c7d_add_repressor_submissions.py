"""add repressor submissions

Revision ID: 4b2e9f8a1c7d
Revises: 3e7a1c9b4d2f
Create Date: 2026-03-24 11:45:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "4b2e9f8a1c7d"
down_revision = "3e7a1c9b4d2f"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "repressor_submissions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("submitter_id", sa.Integer(), nullable=True),
        sa.Column("reviewer_id", sa.Integer(), nullable=True),
        sa.Column("repressor_id", sa.Integer(), nullable=True),
        sa.Column("photo_url", sa.String(length=1000), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("lastname", sa.String(length=200), nullable=True),
        sa.Column("nickname", sa.String(length=160), nullable=True),
        sa.Column("institution_name", sa.String(length=200), nullable=True),
        sa.Column("campus_name", sa.String(length=200), nullable=True),
        sa.Column("province_name", sa.String(length=120), nullable=True),
        sa.Column("municipality_name", sa.String(length=120), nullable=True),
        sa.Column("crimes_json", sa.Text(), nullable=False),
        sa.Column("types_json", sa.Text(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["repressor_id"], ["repressors.id"], ),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"], ),
        sa.ForeignKeyConstraint(["submitter_id"], ["users.id"], ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_repressor_submissions_status"),
        "repressor_submissions",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_repressor_submissions_submitter_id"),
        "repressor_submissions",
        ["submitter_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_repressor_submissions_reviewer_id"),
        "repressor_submissions",
        ["reviewer_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_repressor_submissions_repressor_id"),
        "repressor_submissions",
        ["repressor_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_repressor_submissions_province_name"),
        "repressor_submissions",
        ["province_name"],
        unique=False,
    )
    op.create_index(
        op.f("ix_repressor_submissions_municipality_name"),
        "repressor_submissions",
        ["municipality_name"],
        unique=False,
    )
    op.create_index(
        op.f("ix_repressor_submissions_reviewed_at"),
        "repressor_submissions",
        ["reviewed_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_repressor_submissions_created_at"),
        "repressor_submissions",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_repressor_submissions_updated_at"),
        "repressor_submissions",
        ["updated_at"],
        unique=False,
    )


def downgrade():
    op.drop_index(op.f("ix_repressor_submissions_updated_at"), table_name="repressor_submissions")
    op.drop_index(op.f("ix_repressor_submissions_created_at"), table_name="repressor_submissions")
    op.drop_index(op.f("ix_repressor_submissions_reviewed_at"), table_name="repressor_submissions")
    op.drop_index(op.f("ix_repressor_submissions_municipality_name"), table_name="repressor_submissions")
    op.drop_index(op.f("ix_repressor_submissions_province_name"), table_name="repressor_submissions")
    op.drop_index(op.f("ix_repressor_submissions_repressor_id"), table_name="repressor_submissions")
    op.drop_index(op.f("ix_repressor_submissions_reviewer_id"), table_name="repressor_submissions")
    op.drop_index(op.f("ix_repressor_submissions_submitter_id"), table_name="repressor_submissions")
    op.drop_index(op.f("ix_repressor_submissions_status"), table_name="repressor_submissions")
    op.drop_table("repressor_submissions")
