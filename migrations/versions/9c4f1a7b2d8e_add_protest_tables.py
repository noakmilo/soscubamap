"""add protest tables

Revision ID: 9c4f1a7b2d8e
Revises: 7d9e2c4a1b3f
Create Date: 2026-03-15 03:30:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "9c4f1a7b2d8e"
down_revision = "7d9e2c4a1b3f"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "protest_ingestion_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("started_at_utc", sa.DateTime(), nullable=False),
        sa.Column("finished_at_utc", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("feed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fetched_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("parsed_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("stored_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("deduped_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("hidden_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_protest_ingestion_runs_started_at_utc",
        "protest_ingestion_runs",
        ["started_at_utc"],
        unique=False,
    )
    op.create_index(
        "ix_protest_ingestion_runs_finished_at_utc",
        "protest_ingestion_runs",
        ["finished_at_utc"],
        unique=False,
    )
    op.create_index(
        "ix_protest_ingestion_runs_status",
        "protest_ingestion_runs",
        ["status"],
        unique=False,
    )

    op.create_table(
        "protest_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_feed", sa.String(length=1000), nullable=False, server_default=""),
        sa.Column("source_name", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("source_guid", sa.String(length=1000), nullable=True),
        sa.Column("source_url", sa.String(length=2000), nullable=False, server_default=""),
        sa.Column("source_platform", sa.String(length=64), nullable=False, server_default="web"),
        sa.Column("source_author", sa.String(length=255), nullable=True),
        sa.Column("source_published_at_utc", sa.DateTime(), nullable=False),
        sa.Column("published_day_utc", sa.Date(), nullable=False),
        sa.Column("raw_title", sa.Text(), nullable=False, server_default=""),
        sa.Column("raw_description", sa.Text(), nullable=False, server_default=""),
        sa.Column("clean_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("detected_keywords_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("matched_place_text", sa.String(length=255), nullable=True),
        sa.Column("matched_feature_type", sa.String(length=32), nullable=True),
        sa.Column("matched_feature_name", sa.String(length=255), nullable=True),
        sa.Column("matched_province", sa.String(length=120), nullable=True),
        sa.Column("matched_municipality", sa.String(length=120), nullable=True),
        sa.Column("matched_locality", sa.String(length=160), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("location_precision", sa.String(length=64), nullable=False, server_default="unresolved"),
        sa.Column("confidence_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("event_type", sa.String(length=32), nullable=False, server_default="context_only"),
        sa.Column("review_status", sa.String(length=32), nullable=False, server_default="auto"),
        sa.Column("visible_on_map", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("dedupe_hash", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("related_group_hash", sa.String(length=64), nullable=True),
        sa.Column("transparency_note", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("source_feed", "source_guid", name="uq_protest_feed_guid"),
    )
    op.create_index("ix_protest_events_source_feed", "protest_events", ["source_feed"], unique=False)
    op.create_index("ix_protest_events_source_name", "protest_events", ["source_name"], unique=False)
    op.create_index("ix_protest_events_source_guid", "protest_events", ["source_guid"], unique=False)
    op.create_index("ix_protest_events_source_url", "protest_events", ["source_url"], unique=False)
    op.create_index("ix_protest_events_source_platform", "protest_events", ["source_platform"], unique=False)
    op.create_index(
        "ix_protest_events_source_published_at_utc",
        "protest_events",
        ["source_published_at_utc"],
        unique=False,
    )
    op.create_index("ix_protest_events_published_day_utc", "protest_events", ["published_day_utc"], unique=False)
    op.create_index(
        "ix_protest_events_matched_feature_type",
        "protest_events",
        ["matched_feature_type"],
        unique=False,
    )
    op.create_index("ix_protest_events_matched_province", "protest_events", ["matched_province"], unique=False)
    op.create_index(
        "ix_protest_events_matched_municipality",
        "protest_events",
        ["matched_municipality"],
        unique=False,
    )
    op.create_index("ix_protest_events_matched_locality", "protest_events", ["matched_locality"], unique=False)
    op.create_index("ix_protest_events_confidence_score", "protest_events", ["confidence_score"], unique=False)
    op.create_index("ix_protest_events_event_type", "protest_events", ["event_type"], unique=False)
    op.create_index("ix_protest_events_review_status", "protest_events", ["review_status"], unique=False)
    op.create_index("ix_protest_events_visible_on_map", "protest_events", ["visible_on_map"], unique=False)
    op.create_index("ix_protest_events_dedupe_hash", "protest_events", ["dedupe_hash"], unique=False)
    op.create_index("ix_protest_events_created_at", "protest_events", ["created_at"], unique=False)
    op.create_index("ix_protest_events_updated_at", "protest_events", ["updated_at"], unique=False)


def downgrade():
    op.drop_index("ix_protest_events_updated_at", table_name="protest_events")
    op.drop_index("ix_protest_events_created_at", table_name="protest_events")
    op.drop_index("ix_protest_events_dedupe_hash", table_name="protest_events")
    op.drop_index("ix_protest_events_visible_on_map", table_name="protest_events")
    op.drop_index("ix_protest_events_review_status", table_name="protest_events")
    op.drop_index("ix_protest_events_event_type", table_name="protest_events")
    op.drop_index("ix_protest_events_confidence_score", table_name="protest_events")
    op.drop_index("ix_protest_events_matched_locality", table_name="protest_events")
    op.drop_index("ix_protest_events_matched_municipality", table_name="protest_events")
    op.drop_index("ix_protest_events_matched_province", table_name="protest_events")
    op.drop_index("ix_protest_events_matched_feature_type", table_name="protest_events")
    op.drop_index("ix_protest_events_published_day_utc", table_name="protest_events")
    op.drop_index("ix_protest_events_source_published_at_utc", table_name="protest_events")
    op.drop_index("ix_protest_events_source_platform", table_name="protest_events")
    op.drop_index("ix_protest_events_source_url", table_name="protest_events")
    op.drop_index("ix_protest_events_source_guid", table_name="protest_events")
    op.drop_index("ix_protest_events_source_name", table_name="protest_events")
    op.drop_index("ix_protest_events_source_feed", table_name="protest_events")
    op.drop_table("protest_events")

    op.drop_index("ix_protest_ingestion_runs_status", table_name="protest_ingestion_runs")
    op.drop_index("ix_protest_ingestion_runs_finished_at_utc", table_name="protest_ingestion_runs")
    op.drop_index("ix_protest_ingestion_runs_started_at_utc", table_name="protest_ingestion_runs")
    op.drop_table("protest_ingestion_runs")
