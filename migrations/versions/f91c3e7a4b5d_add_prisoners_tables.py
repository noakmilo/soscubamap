"""add prisoners tables

Revision ID: f91c3e7a4b5d
Revises: 1f7a2c9d4e8b
Create Date: 2026-03-27 17:40:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f91c3e7a4b5d"
down_revision = "1f7a2c9d4e8b"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "prisoners",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("external_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("lastname", sa.String(length=200), nullable=False),
        sa.Column("gender_label", sa.String(length=120), nullable=True),
        sa.Column("detention_typology", sa.String(length=200), nullable=True),
        sa.Column("age_detention_label", sa.String(length=120), nullable=True),
        sa.Column("age_current_label", sa.String(length=120), nullable=True),
        sa.Column("province_name", sa.String(length=120), nullable=True),
        sa.Column("municipality_name", sa.String(length=120), nullable=True),
        sa.Column("prison_name", sa.String(length=200), nullable=True),
        sa.Column("prison_latitude", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("prison_longitude", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("prison_address", sa.String(length=255), nullable=True),
        sa.Column("detention_date", sa.String(length=50), nullable=True),
        sa.Column("offense_types", sa.Text(), nullable=True),
        sa.Column("sentence_text", sa.String(length=300), nullable=True),
        sa.Column("medical_status", sa.String(length=300), nullable=True),
        sa.Column("penal_status", sa.String(length=300), nullable=True),
        sa.Column("observations", sa.Text(), nullable=True),
        sa.Column("image_source_url", sa.String(length=1000), nullable=True),
        sa.Column("image_cached_url", sa.String(length=1000), nullable=True),
        sa.Column("source_detail_url", sa.String(length=500), nullable=True),
        sa.Column("source_created_at", sa.DateTime(), nullable=True),
        sa.Column("source_updated_at", sa.DateTime(), nullable=True),
        sa.Column("source_payload_json", sa.Text(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id"),
    )
    op.create_index(op.f("ix_prisoners_external_id"), "prisoners", ["external_id"], unique=True)
    op.create_index(op.f("ix_prisoners_province_name"), "prisoners", ["province_name"], unique=False)
    op.create_index(op.f("ix_prisoners_municipality_name"), "prisoners", ["municipality_name"], unique=False)
    op.create_index(op.f("ix_prisoners_prison_name"), "prisoners", ["prison_name"], unique=False)
    op.create_index(op.f("ix_prisoners_last_synced_at"), "prisoners", ["last_synced_at"], unique=False)
    op.create_index(op.f("ix_prisoners_updated_at"), "prisoners", ["updated_at"], unique=False)

    op.create_table(
        "prisoner_revisions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("prisoner_id", sa.Integer(), nullable=False),
        sa.Column("editor_id", sa.Integer(), nullable=True),
        sa.Column("editor_label", sa.String(length=120), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("lastname", sa.String(length=200), nullable=True),
        sa.Column("gender_label", sa.String(length=120), nullable=True),
        sa.Column("detention_typology", sa.String(length=200), nullable=True),
        sa.Column("age_detention_label", sa.String(length=120), nullable=True),
        sa.Column("age_current_label", sa.String(length=120), nullable=True),
        sa.Column("province_name", sa.String(length=120), nullable=True),
        sa.Column("municipality_name", sa.String(length=120), nullable=True),
        sa.Column("prison_name", sa.String(length=200), nullable=True),
        sa.Column("prison_latitude", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("prison_longitude", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("prison_address", sa.String(length=255), nullable=True),
        sa.Column("detention_date", sa.String(length=50), nullable=True),
        sa.Column("offense_types", sa.Text(), nullable=True),
        sa.Column("sentence_text", sa.String(length=300), nullable=True),
        sa.Column("medical_status", sa.String(length=300), nullable=True),
        sa.Column("penal_status", sa.String(length=300), nullable=True),
        sa.Column("observations", sa.Text(), nullable=True),
        sa.Column("image_url", sa.String(length=1000), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["editor_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["prisoner_id"], ["prisoners.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_prisoner_revisions_prisoner_id"),
        "prisoner_revisions",
        ["prisoner_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_prisoner_revisions_editor_id"),
        "prisoner_revisions",
        ["editor_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_prisoner_revisions_province_name"),
        "prisoner_revisions",
        ["province_name"],
        unique=False,
    )
    op.create_index(
        op.f("ix_prisoner_revisions_municipality_name"),
        "prisoner_revisions",
        ["municipality_name"],
        unique=False,
    )
    op.create_index(
        op.f("ix_prisoner_revisions_prison_name"),
        "prisoner_revisions",
        ["prison_name"],
        unique=False,
    )
    op.create_index(
        op.f("ix_prisoner_revisions_created_at"),
        "prisoner_revisions",
        ["created_at"],
        unique=False,
    )


def downgrade():
    op.drop_index(op.f("ix_prisoner_revisions_created_at"), table_name="prisoner_revisions")
    op.drop_index(op.f("ix_prisoner_revisions_prison_name"), table_name="prisoner_revisions")
    op.drop_index(
        op.f("ix_prisoner_revisions_municipality_name"),
        table_name="prisoner_revisions",
    )
    op.drop_index(op.f("ix_prisoner_revisions_province_name"), table_name="prisoner_revisions")
    op.drop_index(op.f("ix_prisoner_revisions_editor_id"), table_name="prisoner_revisions")
    op.drop_index(op.f("ix_prisoner_revisions_prisoner_id"), table_name="prisoner_revisions")
    op.drop_table("prisoner_revisions")

    op.drop_index(op.f("ix_prisoners_updated_at"), table_name="prisoners")
    op.drop_index(op.f("ix_prisoners_last_synced_at"), table_name="prisoners")
    op.drop_index(op.f("ix_prisoners_prison_name"), table_name="prisoners")
    op.drop_index(op.f("ix_prisoners_municipality_name"), table_name="prisoners")
    op.drop_index(op.f("ix_prisoners_province_name"), table_name="prisoners")
    op.drop_index(op.f("ix_prisoners_external_id"), table_name="prisoners")
    op.drop_table("prisoners")
