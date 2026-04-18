"""add flight aircraft photo revisions

Revision ID: b2d9f6a4c1e7
Revises: a5b4c3d2e1f0
Create Date: 2026-04-18 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b2d9f6a4c1e7"
down_revision = "a5b4c3d2e1f0"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "flight_aircraft_photo_revisions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("aircraft_id", sa.Integer(), nullable=False),
        sa.Column("uploader_user_id", sa.Integer(), nullable=True),
        sa.Column("photo_url", sa.String(length=1000), nullable=False),
        sa.Column("photo_source", sa.String(length=32), nullable=False, server_default="manual"),
        sa.Column("uploader_anon_label", sa.String(length=80), nullable=False, server_default="Anon"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["aircraft_id"], ["flight_aircraft.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploader_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "ix_flight_aircraft_photo_revisions_aircraft_id",
        "flight_aircraft_photo_revisions",
        ["aircraft_id"],
        unique=False,
    )
    op.create_index(
        "ix_flight_aircraft_photo_revisions_uploader_user_id",
        "flight_aircraft_photo_revisions",
        ["uploader_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_flight_aircraft_photo_revisions_photo_source",
        "flight_aircraft_photo_revisions",
        ["photo_source"],
        unique=False,
    )
    op.create_index(
        "ix_flight_aircraft_photo_revisions_created_at",
        "flight_aircraft_photo_revisions",
        ["created_at"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        "ix_flight_aircraft_photo_revisions_created_at",
        table_name="flight_aircraft_photo_revisions",
    )
    op.drop_index(
        "ix_flight_aircraft_photo_revisions_photo_source",
        table_name="flight_aircraft_photo_revisions",
    )
    op.drop_index(
        "ix_flight_aircraft_photo_revisions_uploader_user_id",
        table_name="flight_aircraft_photo_revisions",
    )
    op.drop_index(
        "ix_flight_aircraft_photo_revisions_aircraft_id",
        table_name="flight_aircraft_photo_revisions",
    )
    op.drop_table("flight_aircraft_photo_revisions")
