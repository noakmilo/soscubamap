"""add repressors catalog and residence reports

Revision ID: 3e7a1c9b4d2f
Revises: f6e1a4b9c2d3
Create Date: 2026-03-24 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "3e7a1c9b4d2f"
down_revision = "f6e1a4b9c2d3"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "repressors",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("external_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("lastname", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("nickname", sa.String(length=160), nullable=True),
        sa.Column("institution_name", sa.String(length=200), nullable=True),
        sa.Column("campus_name", sa.String(length=200), nullable=True),
        sa.Column("province_name", sa.String(length=120), nullable=True),
        sa.Column("municipality_name", sa.String(length=120), nullable=True),
        sa.Column("country_name", sa.String(length=120), nullable=True),
        sa.Column("image_source_url", sa.String(length=1000), nullable=True),
        sa.Column("image_cached_url", sa.String(length=1000), nullable=True),
        sa.Column("source_detail_url", sa.String(length=500), nullable=True),
        sa.Column("source_created_at", sa.DateTime(), nullable=True),
        sa.Column("source_updated_at", sa.DateTime(), nullable=True),
        sa.Column("source_status", sa.Integer(), nullable=True),
        sa.Column("source_is_identifies", sa.String(length=60), nullable=True),
        sa.Column("source_payload_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("first_seen_at", sa.DateTime(), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("external_id", name="uq_repressors_external_id"),
    )
    op.create_index("ix_repressors_external_id", "repressors", ["external_id"], unique=True)
    op.create_index("ix_repressors_province_name", "repressors", ["province_name"], unique=False)
    op.create_index(
        "ix_repressors_municipality_name",
        "repressors",
        ["municipality_name"],
        unique=False,
    )
    op.create_index("ix_repressors_last_synced_at", "repressors", ["last_synced_at"], unique=False)
    op.create_index("ix_repressors_updated_at", "repressors", ["updated_at"], unique=False)

    op.create_table(
        "repressor_crimes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("repressor_id", sa.Integer(), nullable=False),
        sa.Column("source_crime_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=500), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["repressor_id"], ["repressors.id"]),
        sa.UniqueConstraint("repressor_id", "name", name="uq_repressor_crime_name"),
    )
    op.create_index("ix_repressor_crimes_repressor_id", "repressor_crimes", ["repressor_id"], unique=False)
    op.create_index("ix_repressor_crimes_source_crime_id", "repressor_crimes", ["source_crime_id"], unique=False)

    op.create_table(
        "repressor_types",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("repressor_id", sa.Integer(), nullable=False),
        sa.Column("source_type_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["repressor_id"], ["repressors.id"]),
        sa.UniqueConstraint("repressor_id", "name", name="uq_repressor_type_name"),
    )
    op.create_index("ix_repressor_types_repressor_id", "repressor_types", ["repressor_id"], unique=False)
    op.create_index("ix_repressor_types_source_type_id", "repressor_types", ["source_type_id"], unique=False)

    op.create_table(
        "repressor_ingestion_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("started_at_utc", sa.DateTime(), nullable=False),
        sa.Column("finished_at_utc", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("scan_start_id", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("scan_end_id", sa.Integer(), nullable=False, server_default="3000"),
        sa.Column("scanned_ids", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("stored_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unchanged_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("missing_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("errors_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_repressor_ingestion_runs_started_at_utc",
        "repressor_ingestion_runs",
        ["started_at_utc"],
        unique=False,
    )
    op.create_index(
        "ix_repressor_ingestion_runs_finished_at_utc",
        "repressor_ingestion_runs",
        ["finished_at_utc"],
        unique=False,
    )
    op.create_index(
        "ix_repressor_ingestion_runs_status",
        "repressor_ingestion_runs",
        ["status"],
        unique=False,
    )

    op.add_column("posts", sa.Column("repressor_id", sa.Integer(), nullable=True))
    op.create_index("ix_posts_repressor_id", "posts", ["repressor_id"], unique=False)
    op.create_foreign_key(
        "fk_posts_repressor_id_repressors",
        "posts",
        "repressors",
        ["repressor_id"],
        ["id"],
    )

    op.create_table(
        "repressor_residence_reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("repressor_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("reporter_id", sa.Integer(), nullable=True),
        sa.Column("reviewer_id", sa.Integer(), nullable=True),
        sa.Column("latitude", sa.Numeric(precision=9, scale=6), nullable=False),
        sa.Column("longitude", sa.Numeric(precision=9, scale=6), nullable=False),
        sa.Column("address", sa.String(length=255), nullable=True),
        sa.Column("province", sa.String(length=120), nullable=True),
        sa.Column("municipality", sa.String(length=120), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("evidence_links_json", sa.Text(), nullable=True),
        sa.Column("source_image_url", sa.String(length=1000), nullable=True),
        sa.Column("created_post_id", sa.Integer(), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["repressor_id"], ["repressors.id"]),
        sa.ForeignKeyConstraint(["reporter_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["created_post_id"], ["posts.id"]),
    )
    op.create_index(
        "ix_repressor_residence_reports_repressor_id",
        "repressor_residence_reports",
        ["repressor_id"],
        unique=False,
    )
    op.create_index(
        "ix_repressor_residence_reports_status",
        "repressor_residence_reports",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_repressor_residence_reports_reporter_id",
        "repressor_residence_reports",
        ["reporter_id"],
        unique=False,
    )
    op.create_index(
        "ix_repressor_residence_reports_reviewer_id",
        "repressor_residence_reports",
        ["reviewer_id"],
        unique=False,
    )
    op.create_index(
        "ix_repressor_residence_reports_created_post_id",
        "repressor_residence_reports",
        ["created_post_id"],
        unique=False,
    )
    op.create_index(
        "ix_repressor_residence_reports_province",
        "repressor_residence_reports",
        ["province"],
        unique=False,
    )
    op.create_index(
        "ix_repressor_residence_reports_municipality",
        "repressor_residence_reports",
        ["municipality"],
        unique=False,
    )
    op.create_index(
        "ix_repressor_residence_reports_reviewed_at",
        "repressor_residence_reports",
        ["reviewed_at"],
        unique=False,
    )
    op.create_index(
        "ix_repressor_residence_reports_created_at",
        "repressor_residence_reports",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_repressor_residence_reports_updated_at",
        "repressor_residence_reports",
        ["updated_at"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_repressor_residence_reports_updated_at", table_name="repressor_residence_reports")
    op.drop_index("ix_repressor_residence_reports_created_at", table_name="repressor_residence_reports")
    op.drop_index("ix_repressor_residence_reports_reviewed_at", table_name="repressor_residence_reports")
    op.drop_index("ix_repressor_residence_reports_municipality", table_name="repressor_residence_reports")
    op.drop_index("ix_repressor_residence_reports_province", table_name="repressor_residence_reports")
    op.drop_index("ix_repressor_residence_reports_created_post_id", table_name="repressor_residence_reports")
    op.drop_index("ix_repressor_residence_reports_reviewer_id", table_name="repressor_residence_reports")
    op.drop_index("ix_repressor_residence_reports_reporter_id", table_name="repressor_residence_reports")
    op.drop_index("ix_repressor_residence_reports_status", table_name="repressor_residence_reports")
    op.drop_index("ix_repressor_residence_reports_repressor_id", table_name="repressor_residence_reports")
    op.drop_table("repressor_residence_reports")

    op.drop_constraint("fk_posts_repressor_id_repressors", "posts", type_="foreignkey")
    op.drop_index("ix_posts_repressor_id", table_name="posts")
    op.drop_column("posts", "repressor_id")

    op.drop_index("ix_repressor_ingestion_runs_status", table_name="repressor_ingestion_runs")
    op.drop_index("ix_repressor_ingestion_runs_finished_at_utc", table_name="repressor_ingestion_runs")
    op.drop_index("ix_repressor_ingestion_runs_started_at_utc", table_name="repressor_ingestion_runs")
    op.drop_table("repressor_ingestion_runs")

    op.drop_index("ix_repressor_types_source_type_id", table_name="repressor_types")
    op.drop_index("ix_repressor_types_repressor_id", table_name="repressor_types")
    op.drop_table("repressor_types")

    op.drop_index("ix_repressor_crimes_source_crime_id", table_name="repressor_crimes")
    op.drop_index("ix_repressor_crimes_repressor_id", table_name="repressor_crimes")
    op.drop_table("repressor_crimes")

    op.drop_index("ix_repressors_updated_at", table_name="repressors")
    op.drop_index("ix_repressors_last_synced_at", table_name="repressors")
    op.drop_index("ix_repressors_municipality_name", table_name="repressors")
    op.drop_index("ix_repressors_province_name", table_name="repressors")
    op.drop_index("ix_repressors_external_id", table_name="repressors")
    op.drop_table("repressors")
