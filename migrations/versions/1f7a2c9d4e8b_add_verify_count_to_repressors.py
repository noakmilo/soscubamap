"""add verify count to repressors

Revision ID: 1f7a2c9d4e8b
Revises: 8c1d3a7f6b2e
Create Date: 2026-03-27 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "1f7a2c9d4e8b"
down_revision = "8c1d3a7f6b2e"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "repressors",
        sa.Column(
            "verify_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.alter_column("repressors", "verify_count", server_default=None)


def downgrade():
    op.drop_column("repressors", "verify_count")
