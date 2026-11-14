"""Preserve application decisions; existing history cannot be reconstructed."""

import sqlalchemy as sa
from alembic import op

revision = "0004_app_history"
down_revision = "0003_block_unit"
branch_labels = depends_on = None


def upgrade():
    op.create_table(
        "host_application_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("application_id", sa.Integer(), sa.ForeignKey("host_applications.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("application_data", sa.JSON(), nullable=False),
        sa.Column("reject_reason", sa.Text(), nullable=False),
        sa.Column("reviewed_by", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_host_application_history_application_id", "host_application_history", ["application_id"]
    )
    op.execute(
        "INSERT INTO host_application_history (application_id,status,application_data,reject_reason,reviewed_by,reviewed_at) SELECT id,status,application_data,reject_reason,reviewed_by,reviewed_at FROM host_applications WHERE reviewed_at IS NOT NULL"
    )


def downgrade():
    raise RuntimeError("Destructive downgrade disabled")
