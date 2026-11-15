"""Add expiring inventory holds for in-progress checkouts."""

import sqlalchemy as sa
from alembic import op

revision = "0007_booking_holds"
down_revision = "0006_host_cancellations"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "booking_holds",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("homestay_id", sa.Integer(), sa.ForeignKey("homestays.id"), nullable=False),
        sa.Column("check_in", sa.Date(), nullable=False),
        sa.Column("check_out", sa.Date(), nullable=False),
        sa.Column("selections", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("customer_id", name=op.f("uq_booking_holds_customer_id")),
        sa.CheckConstraint("check_out > check_in", name=op.f("ck_booking_holds_date_order")),
    )
    op.create_index("ix_booking_holds_customer_id", "booking_holds", ["customer_id"])
    op.create_index("ix_booking_holds_homestay_id", "booking_holds", ["homestay_id"])
    op.create_index("ix_booking_holds_expires_at", "booking_holds", ["expires_at"])
    op.create_table(
        "booking_hold_nights",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("hold_id", sa.Integer(), sa.ForeignKey("booking_holds.id"), nullable=False),
        sa.Column("room_id", sa.Integer(), sa.ForeignKey("rooms.id"), nullable=False),
        sa.Column("unit", sa.Integer(), nullable=False),
        sa.Column("night", sa.Date(), nullable=False),
        sa.UniqueConstraint("room_id", "unit", "night", name=op.f("uq_booking_hold_nights_room_id")),
        sa.CheckConstraint("unit >= 1", name=op.f("ck_booking_hold_nights_positive_unit")),
    )
    op.create_index("ix_booking_hold_nights_hold_id", "booking_hold_nights", ["hold_id"])
    op.create_index("ix_booking_hold_nights_lookup", "booking_hold_nights", ["room_id", "night"])


def downgrade():
    raise RuntimeError("Destructive downgrade disabled; restore a verified backup instead")
