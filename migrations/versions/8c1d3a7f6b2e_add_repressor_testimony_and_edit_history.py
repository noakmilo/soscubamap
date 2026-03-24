"""add repressor testimony and edit history

Revision ID: 8c1d3a7f6b2e
Revises: 4b2e9f8a1c7d
Create Date: 2026-03-24 15:35:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "8c1d3a7f6b2e"
down_revision = "4b2e9f8a1c7d"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("repressors", sa.Column("testimony", sa.Text(), nullable=True))
    op.add_column("repressor_submissions", sa.Column("testimony", sa.Text(), nullable=True))

    op.create_table(
        "repressor_edit_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("repressor_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("edit_kind", sa.String(length=20), nullable=False),
        sa.Column("editor_id", sa.Integer(), nullable=True),
        sa.Column("reviewer_id", sa.Integer(), nullable=True),
        sa.Column("editor_label", sa.String(length=120), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("lastname", sa.String(length=200), nullable=True),
        sa.Column("nickname", sa.String(length=160), nullable=True),
        sa.Column("institution_name", sa.String(length=200), nullable=True),
        sa.Column("campus_name", sa.String(length=200), nullable=True),
        sa.Column("province_name", sa.String(length=120), nullable=True),
        sa.Column("municipality_name", sa.String(length=120), nullable=True),
        sa.Column("testimony", sa.Text(), nullable=True),
        sa.Column("image_url", sa.String(length=1000), nullable=True),
        sa.Column("crimes_json", sa.Text(), nullable=False),
        sa.Column("types_json", sa.Text(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["editor_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["repressor_id"], ["repressors.id"]),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_repressor_edit_requests_repressor_id"),
        "repressor_edit_requests",
        ["repressor_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_repressor_edit_requests_status"),
        "repressor_edit_requests",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_repressor_edit_requests_edit_kind"),
        "repressor_edit_requests",
        ["edit_kind"],
        unique=False,
    )
    op.create_index(
        op.f("ix_repressor_edit_requests_editor_id"),
        "repressor_edit_requests",
        ["editor_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_repressor_edit_requests_reviewer_id"),
        "repressor_edit_requests",
        ["reviewer_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_repressor_edit_requests_province_name"),
        "repressor_edit_requests",
        ["province_name"],
        unique=False,
    )
    op.create_index(
        op.f("ix_repressor_edit_requests_municipality_name"),
        "repressor_edit_requests",
        ["municipality_name"],
        unique=False,
    )
    op.create_index(
        op.f("ix_repressor_edit_requests_reviewed_at"),
        "repressor_edit_requests",
        ["reviewed_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_repressor_edit_requests_created_at"),
        "repressor_edit_requests",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_repressor_edit_requests_updated_at"),
        "repressor_edit_requests",
        ["updated_at"],
        unique=False,
    )

    op.create_table(
        "repressor_revisions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("repressor_id", sa.Integer(), nullable=False),
        sa.Column("editor_id", sa.Integer(), nullable=True),
        sa.Column("editor_label", sa.String(length=120), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("lastname", sa.String(length=200), nullable=True),
        sa.Column("nickname", sa.String(length=160), nullable=True),
        sa.Column("institution_name", sa.String(length=200), nullable=True),
        sa.Column("campus_name", sa.String(length=200), nullable=True),
        sa.Column("province_name", sa.String(length=120), nullable=True),
        sa.Column("municipality_name", sa.String(length=120), nullable=True),
        sa.Column("testimony", sa.Text(), nullable=True),
        sa.Column("image_url", sa.String(length=1000), nullable=True),
        sa.Column("crimes_json", sa.Text(), nullable=False),
        sa.Column("types_json", sa.Text(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["editor_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["repressor_id"], ["repressors.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_repressor_revisions_repressor_id"),
        "repressor_revisions",
        ["repressor_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_repressor_revisions_editor_id"),
        "repressor_revisions",
        ["editor_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_repressor_revisions_province_name"),
        "repressor_revisions",
        ["province_name"],
        unique=False,
    )
    op.create_index(
        op.f("ix_repressor_revisions_municipality_name"),
        "repressor_revisions",
        ["municipality_name"],
        unique=False,
    )
    op.create_index(
        op.f("ix_repressor_revisions_created_at"),
        "repressor_revisions",
        ["created_at"],
        unique=False,
    )


def downgrade():
    op.drop_index(op.f("ix_repressor_revisions_created_at"), table_name="repressor_revisions")
    op.drop_index(op.f("ix_repressor_revisions_municipality_name"), table_name="repressor_revisions")
    op.drop_index(op.f("ix_repressor_revisions_province_name"), table_name="repressor_revisions")
    op.drop_index(op.f("ix_repressor_revisions_editor_id"), table_name="repressor_revisions")
    op.drop_index(op.f("ix_repressor_revisions_repressor_id"), table_name="repressor_revisions")
    op.drop_table("repressor_revisions")

    op.drop_index(op.f("ix_repressor_edit_requests_updated_at"), table_name="repressor_edit_requests")
    op.drop_index(op.f("ix_repressor_edit_requests_created_at"), table_name="repressor_edit_requests")
    op.drop_index(op.f("ix_repressor_edit_requests_reviewed_at"), table_name="repressor_edit_requests")
    op.drop_index(op.f("ix_repressor_edit_requests_municipality_name"), table_name="repressor_edit_requests")
    op.drop_index(op.f("ix_repressor_edit_requests_province_name"), table_name="repressor_edit_requests")
    op.drop_index(op.f("ix_repressor_edit_requests_reviewer_id"), table_name="repressor_edit_requests")
    op.drop_index(op.f("ix_repressor_edit_requests_editor_id"), table_name="repressor_edit_requests")
    op.drop_index(op.f("ix_repressor_edit_requests_edit_kind"), table_name="repressor_edit_requests")
    op.drop_index(op.f("ix_repressor_edit_requests_status"), table_name="repressor_edit_requests")
    op.drop_index(op.f("ix_repressor_edit_requests_repressor_id"), table_name="repressor_edit_requests")
    op.drop_table("repressor_edit_requests")

    op.drop_column("repressor_submissions", "testimony")
    op.drop_column("repressors", "testimony")
