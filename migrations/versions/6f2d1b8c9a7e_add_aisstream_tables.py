"""add aisstream tables

Revision ID: 6f2d1b8c9a7e
Revises: f91c3e7a4b5d
Create Date: 2026-03-27 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "6f2d1b8c9a7e"
down_revision = "f91c3e7a4b5d"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ais_ingestion_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("scheduled_for_utc", sa.DateTime(), nullable=True),
        sa.Column("started_at_utc", sa.DateTime(), nullable=False),
        sa.Column("finished_at_utc", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("total_messages", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("position_messages", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("static_messages", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("matched_messages", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("matched_vessels", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("stale_removed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_ais_ingestion_runs_scheduled_for_utc",
        "ais_ingestion_runs",
        ["scheduled_for_utc"],
        unique=False,
    )
    op.create_index(
        "ix_ais_ingestion_runs_started_at_utc",
        "ais_ingestion_runs",
        ["started_at_utc"],
        unique=False,
    )
    op.create_index(
        "ix_ais_ingestion_runs_finished_at_utc",
        "ais_ingestion_runs",
        ["finished_at_utc"],
        unique=False,
    )
    op.create_index(
        "ix_ais_ingestion_runs_status",
        "ais_ingestion_runs",
        ["status"],
        unique=False,
    )

    op.create_table(
        "ais_cuba_target_vessels",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("mmsi", sa.String(length=32), nullable=False),
        sa.Column("ship_name", sa.String(length=255), nullable=True),
        sa.Column("imo", sa.String(length=32), nullable=True),
        sa.Column("call_sign", sa.String(length=64), nullable=True),
        sa.Column("vessel_type", sa.String(length=80), nullable=True),
        sa.Column("destination_raw", sa.String(length=255), nullable=True),
        sa.Column("destination_normalized", sa.String(length=255), nullable=True),
        sa.Column("matched_port_key", sa.String(length=64), nullable=True),
        sa.Column("matched_port_name", sa.String(length=128), nullable=True),
        sa.Column("match_confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("match_reason", sa.String(length=120), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("sog", sa.Float(), nullable=True),
        sa.Column("cog", sa.Float(), nullable=True),
        sa.Column("heading", sa.Float(), nullable=True),
        sa.Column("navigational_status", sa.String(length=64), nullable=True),
        sa.Column("source_message_type", sa.String(length=64), nullable=True),
        sa.Column("last_seen_at_utc", sa.DateTime(), nullable=True),
        sa.Column("last_position_at_utc", sa.DateTime(), nullable=True),
        sa.Column("last_static_at_utc", sa.DateTime(), nullable=True),
        sa.Column(
            "ingestion_run_id",
            sa.Integer(),
            sa.ForeignKey("ais_ingestion_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("mmsi", name="uq_ais_cuba_target_vessels_mmsi"),
    )
    op.create_index(
        "ix_ais_cuba_target_vessels_mmsi",
        "ais_cuba_target_vessels",
        ["mmsi"],
        unique=False,
    )
    op.create_index(
        "ix_ais_cuba_target_vessels_destination_normalized",
        "ais_cuba_target_vessels",
        ["destination_normalized"],
        unique=False,
    )
    op.create_index(
        "ix_ais_cuba_target_vessels_matched_port_key",
        "ais_cuba_target_vessels",
        ["matched_port_key"],
        unique=False,
    )
    op.create_index(
        "ix_ais_cuba_target_vessels_latitude",
        "ais_cuba_target_vessels",
        ["latitude"],
        unique=False,
    )
    op.create_index(
        "ix_ais_cuba_target_vessels_longitude",
        "ais_cuba_target_vessels",
        ["longitude"],
        unique=False,
    )
    op.create_index(
        "ix_ais_cuba_target_vessels_last_seen_at_utc",
        "ais_cuba_target_vessels",
        ["last_seen_at_utc"],
        unique=False,
    )
    op.create_index(
        "ix_ais_cuba_target_vessels_ingestion_run_id",
        "ais_cuba_target_vessels",
        ["ingestion_run_id"],
        unique=False,
    )
    op.create_index(
        "ix_ais_cuba_target_vessels_updated_at",
        "ais_cuba_target_vessels",
        ["updated_at"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        "ix_ais_cuba_target_vessels_updated_at",
        table_name="ais_cuba_target_vessels",
    )
    op.drop_index(
        "ix_ais_cuba_target_vessels_ingestion_run_id",
        table_name="ais_cuba_target_vessels",
    )
    op.drop_index(
        "ix_ais_cuba_target_vessels_last_seen_at_utc",
        table_name="ais_cuba_target_vessels",
    )
    op.drop_index(
        "ix_ais_cuba_target_vessels_longitude",
        table_name="ais_cuba_target_vessels",
    )
    op.drop_index(
        "ix_ais_cuba_target_vessels_latitude",
        table_name="ais_cuba_target_vessels",
    )
    op.drop_index(
        "ix_ais_cuba_target_vessels_matched_port_key",
        table_name="ais_cuba_target_vessels",
    )
    op.drop_index(
        "ix_ais_cuba_target_vessels_destination_normalized",
        table_name="ais_cuba_target_vessels",
    )
    op.drop_index(
        "ix_ais_cuba_target_vessels_mmsi",
        table_name="ais_cuba_target_vessels",
    )
    op.drop_table("ais_cuba_target_vessels")

    op.drop_index(
        "ix_ais_ingestion_runs_status",
        table_name="ais_ingestion_runs",
    )
    op.drop_index(
        "ix_ais_ingestion_runs_finished_at_utc",
        table_name="ais_ingestion_runs",
    )
    op.drop_index(
        "ix_ais_ingestion_runs_started_at_utc",
        table_name="ais_ingestion_runs",
    )
    op.drop_index(
        "ix_ais_ingestion_runs_scheduled_for_utc",
        table_name="ais_ingestion_runs",
    )
    op.drop_table("ais_ingestion_runs")
