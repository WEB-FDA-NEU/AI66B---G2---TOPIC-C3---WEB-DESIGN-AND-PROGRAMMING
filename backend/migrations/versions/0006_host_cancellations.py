"""Record host role cancellations and self-cancellation reasons."""

import sqlalchemy as sa
from alembic import op

revision = "0006_host_cancellations"
down_revision = "0005_pay_events"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "host_cancellations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("host_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("source IN ('host','admin')", name=op.f("ck_host_cancellations_valid_source")),
    )
    op.create_index("ix_host_cancellations_host_id", "host_cancellations", ["host_id"])
    op.create_index("ix_host_cancellations_created_at", "host_cancellations", ["created_at"])


def downgrade():
    raise RuntimeError("Destructive downgrade disabled; restore a verified backup instead")
