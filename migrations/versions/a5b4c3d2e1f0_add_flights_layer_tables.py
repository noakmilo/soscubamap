"""add flights layer tables

Revision ID: a5b4c3d2e1f0
Revises: 6f2d1b8c9a7e
Create Date: 2026-04-17 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a5b4c3d2e1f0"
down_revision = "6f2d1b8c9a7e"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "flight_ingestion_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("scheduled_for_utc", sa.DateTime(), nullable=True),
        sa.Column("started_at_utc", sa.DateTime(), nullable=False),
        sa.Column("finished_at_utc", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("is_backfill", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("backfill_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("safe_mode", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("request_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estimated_credits", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("airports_synced", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("events_seen", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("events_stored", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("positions_stored", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_flight_ingestion_runs_scheduled_for_utc",
        "flight_ingestion_runs",
        ["scheduled_for_utc"],
        unique=False,
    )
    op.create_index(
        "ix_flight_ingestion_runs_started_at_utc",
        "flight_ingestion_runs",
        ["started_at_utc"],
        unique=False,
    )
    op.create_index(
        "ix_flight_ingestion_runs_finished_at_utc",
        "flight_ingestion_runs",
        ["finished_at_utc"],
        unique=False,
    )
    op.create_index(
        "ix_flight_ingestion_runs_status",
        "flight_ingestion_runs",
        ["status"],
        unique=False,
    )

    op.create_table(
        "flight_airports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code_key", sa.String(length=32), nullable=False),
        sa.Column("fr_airport_id", sa.String(length=64), nullable=True),
        sa.Column("airport_code_icao", sa.String(length=8), nullable=True),
        sa.Column("airport_code_iata", sa.String(length=8), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("province", sa.String(length=120), nullable=True),
        sa.Column("country_code", sa.String(length=8), nullable=True),
        sa.Column("country_name", sa.String(length=120), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("is_cuba", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("code_key", name="uq_flight_airports_code_key"),
    )
    op.create_index(
        "ix_flight_airports_code_key",
        "flight_airports",
        ["code_key"],
        unique=False,
    )
    op.create_index(
        "ix_flight_airports_fr_airport_id",
        "flight_airports",
        ["fr_airport_id"],
        unique=False,
    )
    op.create_index(
        "ix_flight_airports_airport_code_icao",
        "flight_airports",
        ["airport_code_icao"],
        unique=False,
    )
    op.create_index(
        "ix_flight_airports_airport_code_iata",
        "flight_airports",
        ["airport_code_iata"],
        unique=False,
    )
    op.create_index(
        "ix_flight_airports_country_code",
        "flight_airports",
        ["country_code"],
        unique=False,
    )
    op.create_index(
        "ix_flight_airports_latitude",
        "flight_airports",
        ["latitude"],
        unique=False,
    )
    op.create_index(
        "ix_flight_airports_longitude",
        "flight_airports",
        ["longitude"],
        unique=False,
    )
    op.create_index(
        "ix_flight_airports_is_cuba",
        "flight_airports",
        ["is_cuba"],
        unique=False,
    )
    op.create_index(
        "ix_flight_airports_updated_at",
        "flight_airports",
        ["updated_at"],
        unique=False,
    )

    op.create_table(
        "flight_aircraft",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("identity_key", sa.String(length=255), nullable=False),
        sa.Column("call_sign", sa.String(length=64), nullable=True),
        sa.Column("model", sa.String(length=120), nullable=True),
        sa.Column("registration", sa.String(length=64), nullable=True),
        sa.Column("hex_code", sa.String(length=32), nullable=True),
        sa.Column("operator_name", sa.String(length=255), nullable=True),
        sa.Column("manufacturer", sa.String(length=120), nullable=True),
        sa.Column("photo_api_url", sa.String(length=1000), nullable=True),
        sa.Column("photo_manual_url", sa.String(length=1000), nullable=True),
        sa.Column("photo_updated_at_utc", sa.DateTime(), nullable=True),
        sa.Column("first_seen_at_utc", sa.DateTime(), nullable=True),
        sa.Column("last_seen_at_utc", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("identity_key", name="uq_flight_aircraft_identity_key"),
    )
    op.create_index(
        "ix_flight_aircraft_identity_key",
        "flight_aircraft",
        ["identity_key"],
        unique=False,
    )
    op.create_index("ix_flight_aircraft_call_sign", "flight_aircraft", ["call_sign"], unique=False)
    op.create_index("ix_flight_aircraft_model", "flight_aircraft", ["model"], unique=False)
    op.create_index(
        "ix_flight_aircraft_registration",
        "flight_aircraft",
        ["registration"],
        unique=False,
    )
    op.create_index("ix_flight_aircraft_hex_code", "flight_aircraft", ["hex_code"], unique=False)
    op.create_index(
        "ix_flight_aircraft_first_seen_at_utc",
        "flight_aircraft",
        ["first_seen_at_utc"],
        unique=False,
    )
    op.create_index(
        "ix_flight_aircraft_last_seen_at_utc",
        "flight_aircraft",
        ["last_seen_at_utc"],
        unique=False,
    )
    op.create_index("ix_flight_aircraft_updated_at", "flight_aircraft", ["updated_at"], unique=False)

    op.create_table(
        "flight_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_key", sa.String(length=255), nullable=False),
        sa.Column("external_flight_id", sa.String(length=128), nullable=True),
        sa.Column("aircraft_id", sa.Integer(), nullable=False),
        sa.Column("destination_airport_id", sa.Integer(), nullable=True),
        sa.Column("ingestion_run_id", sa.Integer(), nullable=True),
        sa.Column("identity_key", sa.String(length=255), nullable=True),
        sa.Column("call_sign", sa.String(length=64), nullable=True),
        sa.Column("model", sa.String(length=120), nullable=True),
        sa.Column("registration", sa.String(length=64), nullable=True),
        sa.Column("origin_airport_icao", sa.String(length=8), nullable=True),
        sa.Column("origin_airport_iata", sa.String(length=8), nullable=True),
        sa.Column("origin_airport_name", sa.String(length=255), nullable=True),
        sa.Column("origin_country", sa.String(length=120), nullable=True),
        sa.Column("destination_airport_icao", sa.String(length=8), nullable=True),
        sa.Column("destination_airport_iata", sa.String(length=8), nullable=True),
        sa.Column("destination_airport_name", sa.String(length=255), nullable=True),
        sa.Column("destination_country", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=True),
        sa.Column("departure_at_utc", sa.DateTime(), nullable=True),
        sa.Column("arrival_at_utc", sa.DateTime(), nullable=True),
        sa.Column("first_seen_at_utc", sa.DateTime(), nullable=True),
        sa.Column("last_seen_at_utc", sa.DateTime(), nullable=True),
        sa.Column("latest_latitude", sa.Float(), nullable=True),
        sa.Column("latest_longitude", sa.Float(), nullable=True),
        sa.Column("latest_altitude", sa.Float(), nullable=True),
        sa.Column("latest_speed", sa.Float(), nullable=True),
        sa.Column("latest_heading", sa.Float(), nullable=True),
        sa.Column("last_source_kind", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["aircraft_id"], ["flight_aircraft.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["destination_airport_id"],
            ["flight_airports.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["ingestion_run_id"], ["flight_ingestion_runs.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("event_key", name="uq_flight_events_event_key"),
    )
    op.create_index("ix_flight_events_event_key", "flight_events", ["event_key"], unique=False)
    op.create_index(
        "ix_flight_events_external_flight_id",
        "flight_events",
        ["external_flight_id"],
        unique=False,
    )
    op.create_index("ix_flight_events_aircraft_id", "flight_events", ["aircraft_id"], unique=False)
    op.create_index(
        "ix_flight_events_destination_airport_id",
        "flight_events",
        ["destination_airport_id"],
        unique=False,
    )
    op.create_index(
        "ix_flight_events_ingestion_run_id",
        "flight_events",
        ["ingestion_run_id"],
        unique=False,
    )
    op.create_index("ix_flight_events_identity_key", "flight_events", ["identity_key"], unique=False)
    op.create_index("ix_flight_events_call_sign", "flight_events", ["call_sign"], unique=False)
    op.create_index("ix_flight_events_model", "flight_events", ["model"], unique=False)
    op.create_index("ix_flight_events_registration", "flight_events", ["registration"], unique=False)
    op.create_index(
        "ix_flight_events_origin_airport_icao",
        "flight_events",
        ["origin_airport_icao"],
        unique=False,
    )
    op.create_index(
        "ix_flight_events_origin_airport_iata",
        "flight_events",
        ["origin_airport_iata"],
        unique=False,
    )
    op.create_index(
        "ix_flight_events_destination_airport_icao",
        "flight_events",
        ["destination_airport_icao"],
        unique=False,
    )
    op.create_index(
        "ix_flight_events_destination_airport_iata",
        "flight_events",
        ["destination_airport_iata"],
        unique=False,
    )
    op.create_index(
        "ix_flight_events_destination_airport_name",
        "flight_events",
        ["destination_airport_name"],
        unique=False,
    )
    op.create_index(
        "ix_flight_events_destination_country",
        "flight_events",
        ["destination_country"],
        unique=False,
    )
    op.create_index("ix_flight_events_status", "flight_events", ["status"], unique=False)
    op.create_index(
        "ix_flight_events_departure_at_utc",
        "flight_events",
        ["departure_at_utc"],
        unique=False,
    )
    op.create_index(
        "ix_flight_events_arrival_at_utc",
        "flight_events",
        ["arrival_at_utc"],
        unique=False,
    )
    op.create_index(
        "ix_flight_events_first_seen_at_utc",
        "flight_events",
        ["first_seen_at_utc"],
        unique=False,
    )
    op.create_index(
        "ix_flight_events_last_seen_at_utc",
        "flight_events",
        ["last_seen_at_utc"],
        unique=False,
    )
    op.create_index(
        "ix_flight_events_latest_latitude",
        "flight_events",
        ["latest_latitude"],
        unique=False,
    )
    op.create_index(
        "ix_flight_events_latest_longitude",
        "flight_events",
        ["latest_longitude"],
        unique=False,
    )
    op.create_index(
        "ix_flight_events_last_source_kind",
        "flight_events",
        ["last_source_kind"],
        unique=False,
    )
    op.create_index("ix_flight_events_updated_at", "flight_events", ["updated_at"], unique=False)

    op.create_table(
        "flight_positions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("observed_at_utc", sa.DateTime(), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("altitude", sa.Float(), nullable=True),
        sa.Column("speed", sa.Float(), nullable=True),
        sa.Column("heading", sa.Float(), nullable=True),
        sa.Column("source_kind", sa.String(length=64), nullable=False, server_default="live"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["flight_events.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "event_id",
            "observed_at_utc",
            "source_kind",
            name="uq_flight_positions_event_observed_source",
        ),
    )
    op.create_index("ix_flight_positions_event_id", "flight_positions", ["event_id"], unique=False)
    op.create_index(
        "ix_flight_positions_observed_at_utc",
        "flight_positions",
        ["observed_at_utc"],
        unique=False,
    )
    op.create_index("ix_flight_positions_latitude", "flight_positions", ["latitude"], unique=False)
    op.create_index("ix_flight_positions_longitude", "flight_positions", ["longitude"], unique=False)
    op.create_index(
        "ix_flight_positions_source_kind",
        "flight_positions",
        ["source_kind"],
        unique=False,
    )

    op.create_table(
        "flight_layer_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("window_hours", sa.Integer(), nullable=False),
        sa.Column("generated_at_utc", sa.DateTime(), nullable=False),
        sa.Column("stale_after_seconds", sa.Integer(), nullable=False, server_default="3600"),
        sa.Column("points_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("summary_json", sa.Text(), nullable=True),
        sa.Column("points_json", sa.Text(), nullable=True),
        sa.Column("ingestion_run_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["ingestion_run_id"], ["flight_ingestion_runs.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("window_hours", name="uq_flight_layer_snapshots_window_hours"),
    )
    op.create_index(
        "ix_flight_layer_snapshots_window_hours",
        "flight_layer_snapshots",
        ["window_hours"],
        unique=False,
    )
    op.create_index(
        "ix_flight_layer_snapshots_generated_at_utc",
        "flight_layer_snapshots",
        ["generated_at_utc"],
        unique=False,
    )
    op.create_index(
        "ix_flight_layer_snapshots_ingestion_run_id",
        "flight_layer_snapshots",
        ["ingestion_run_id"],
        unique=False,
    )
    op.create_index(
        "ix_flight_layer_snapshots_updated_at",
        "flight_layer_snapshots",
        ["updated_at"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_flight_layer_snapshots_updated_at", table_name="flight_layer_snapshots")
    op.drop_index("ix_flight_layer_snapshots_ingestion_run_id", table_name="flight_layer_snapshots")
    op.drop_index("ix_flight_layer_snapshots_generated_at_utc", table_name="flight_layer_snapshots")
    op.drop_index("ix_flight_layer_snapshots_window_hours", table_name="flight_layer_snapshots")
    op.drop_table("flight_layer_snapshots")

    op.drop_index("ix_flight_positions_source_kind", table_name="flight_positions")
    op.drop_index("ix_flight_positions_longitude", table_name="flight_positions")
    op.drop_index("ix_flight_positions_latitude", table_name="flight_positions")
    op.drop_index("ix_flight_positions_observed_at_utc", table_name="flight_positions")
    op.drop_index("ix_flight_positions_event_id", table_name="flight_positions")
    op.drop_table("flight_positions")

    op.drop_index("ix_flight_events_updated_at", table_name="flight_events")
    op.drop_index("ix_flight_events_last_source_kind", table_name="flight_events")
    op.drop_index("ix_flight_events_latest_longitude", table_name="flight_events")
    op.drop_index("ix_flight_events_latest_latitude", table_name="flight_events")
    op.drop_index("ix_flight_events_last_seen_at_utc", table_name="flight_events")
    op.drop_index("ix_flight_events_first_seen_at_utc", table_name="flight_events")
    op.drop_index("ix_flight_events_arrival_at_utc", table_name="flight_events")
    op.drop_index("ix_flight_events_departure_at_utc", table_name="flight_events")
    op.drop_index("ix_flight_events_status", table_name="flight_events")
    op.drop_index("ix_flight_events_destination_country", table_name="flight_events")
    op.drop_index("ix_flight_events_destination_airport_name", table_name="flight_events")
    op.drop_index("ix_flight_events_destination_airport_iata", table_name="flight_events")
    op.drop_index("ix_flight_events_destination_airport_icao", table_name="flight_events")
    op.drop_index("ix_flight_events_origin_airport_iata", table_name="flight_events")
    op.drop_index("ix_flight_events_origin_airport_icao", table_name="flight_events")
    op.drop_index("ix_flight_events_registration", table_name="flight_events")
    op.drop_index("ix_flight_events_model", table_name="flight_events")
    op.drop_index("ix_flight_events_call_sign", table_name="flight_events")
    op.drop_index("ix_flight_events_identity_key", table_name="flight_events")
    op.drop_index("ix_flight_events_ingestion_run_id", table_name="flight_events")
    op.drop_index("ix_flight_events_destination_airport_id", table_name="flight_events")
    op.drop_index("ix_flight_events_aircraft_id", table_name="flight_events")
    op.drop_index("ix_flight_events_external_flight_id", table_name="flight_events")
    op.drop_index("ix_flight_events_event_key", table_name="flight_events")
    op.drop_table("flight_events")

    op.drop_index("ix_flight_aircraft_updated_at", table_name="flight_aircraft")
    op.drop_index("ix_flight_aircraft_last_seen_at_utc", table_name="flight_aircraft")
    op.drop_index("ix_flight_aircraft_first_seen_at_utc", table_name="flight_aircraft")
    op.drop_index("ix_flight_aircraft_hex_code", table_name="flight_aircraft")
    op.drop_index("ix_flight_aircraft_registration", table_name="flight_aircraft")
    op.drop_index("ix_flight_aircraft_model", table_name="flight_aircraft")
    op.drop_index("ix_flight_aircraft_call_sign", table_name="flight_aircraft")
    op.drop_index("ix_flight_aircraft_identity_key", table_name="flight_aircraft")
    op.drop_table("flight_aircraft")

    op.drop_index("ix_flight_airports_updated_at", table_name="flight_airports")
    op.drop_index("ix_flight_airports_is_cuba", table_name="flight_airports")
    op.drop_index("ix_flight_airports_longitude", table_name="flight_airports")
    op.drop_index("ix_flight_airports_latitude", table_name="flight_airports")
    op.drop_index("ix_flight_airports_country_code", table_name="flight_airports")
    op.drop_index("ix_flight_airports_airport_code_iata", table_name="flight_airports")
    op.drop_index("ix_flight_airports_airport_code_icao", table_name="flight_airports")
    op.drop_index("ix_flight_airports_fr_airport_id", table_name="flight_airports")
    op.drop_index("ix_flight_airports_code_key", table_name="flight_airports")
    op.drop_table("flight_airports")

    op.drop_index("ix_flight_ingestion_runs_status", table_name="flight_ingestion_runs")
    op.drop_index("ix_flight_ingestion_runs_finished_at_utc", table_name="flight_ingestion_runs")
    op.drop_index("ix_flight_ingestion_runs_started_at_utc", table_name="flight_ingestion_runs")
    op.drop_index("ix_flight_ingestion_runs_scheduled_for_utc", table_name="flight_ingestion_runs")
    op.drop_table("flight_ingestion_runs")
