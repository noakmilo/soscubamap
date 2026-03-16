"""site_settings value column String(255) -> Text

Revision ID: a3f1b2c4d5e6
Revises: 5f3c2a8d6c1b
Create Date: 2026-03-16 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "a3f1b2c4d5e6"
down_revision = "5f3c2a8d6c1b"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("site_settings", schema=None) as batch_op:
        batch_op.alter_column(
            "value",
            existing_type=sa.String(255),
            type_=sa.Text(),
            existing_nullable=False,
        )


def downgrade():
    with op.batch_alter_table("site_settings", schema=None) as batch_op:
        batch_op.alter_column(
            "value",
            existing_type=sa.Text(),
            type_=sa.String(255),
            existing_nullable=False,
        )
