"""add rejection_reason to post_edit_requests

Revision ID: 5f3c2a8d6c1b
Revises: 93d267453bf0
Create Date: 2026-03-03 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "5f3c2a8d6c1b"
down_revision = "93d267453bf0"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("post_edit_requests", schema=None) as batch_op:
        batch_op.add_column(sa.Column("rejection_reason", sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table("post_edit_requests", schema=None) as batch_op:
        batch_op.drop_column("rejection_reason")
