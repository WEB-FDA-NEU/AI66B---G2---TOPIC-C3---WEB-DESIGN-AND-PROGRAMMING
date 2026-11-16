"""Append payment audit events; bootstrap only current state, not invented history."""

import sqlalchemy as sa
from alembic import op

revision = "0005_pay_events"
down_revision = "0004_app_history"
branch_labels = depends_on = None


def upgrade():
    op.create_table(
        "payment_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("payment_id", sa.Integer(), sa.ForeignKey("payments.id"), nullable=False),
        sa.Column("old_status", sa.String(20)),
        sa.Column("new_status", sa.String(20), nullable=False),
        sa.Column("amount", sa.Numeric(14, 0), nullable=False),
        sa.Column("refund_amount", sa.Numeric(14, 0), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("changed_by", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "amount >= 0 AND refund_amount >= 0 AND refund_amount <= amount",
            name=op.f("ck_payment_events_amount_range"),
        ),
    )
    op.create_index("ix_payment_events_payment_id", "payment_events", ["payment_id"])
    op.execute(
        "INSERT INTO payment_events (payment_id,new_status,amount,refund_amount,source,note,created_at) SELECT id,status,amount,0,'legacy_snapshot','Current state only; original transition time unknown',created_at FROM payments"
    )


def downgrade():
    raise RuntimeError("Destructive downgrade disabled")
