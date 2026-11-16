"""canonical LuxStay schema; retain legacy rows

Revision: 0002_luxstay
Revises: 0001_template
"""

import sqlalchemy as sa
from alembic import op

revision = "0002_luxstay"
down_revision = "0001_template"
branch_labels = None
depends_on = None


def upgrade():
    # Add columns without rebuilding users: existing items rows still reference it.
    op.add_column(
        "users", sa.Column("avatar", sa.Text(), nullable=False, server_default="img/placeholder.svg")
    )
    op.add_column("users", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("users", sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"))
    op.add_column(
        "users",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("'1970-01-01 00:00:00+00:00'"),
        ),
    )
    op.execute(sa.text("UPDATE users SET updated_at = created_at"))
    op.create_index("ix_users_role", "users", ["role"])
    bind = op.get_bind()
    invalid = bind.execute(
        sa.text("SELECT COUNT(*) FROM users WHERE role NOT IN ('user','host','admin')")
    ).scalar_one()
    if invalid:
        raise RuntimeError("Legacy users contain unsupported roles; prepare an explicit data migration")
    if bind.dialect.name == "sqlite":
        # SQLite cannot ADD CHECK without rebuilding the referenced users table.
        for event in ("INSERT", "UPDATE OF role"):
            suffix = "insert" if event == "INSERT" else "update"
            op.execute(
                sa.text(
                    f"CREATE TRIGGER ck_users_valid_role_{suffix} BEFORE {event} ON users WHEN NEW.role NOT IN ('user','host','admin') BEGIN SELECT RAISE(ABORT, 'invalid user role'); END"
                )
            )
    else:
        op.create_check_constraint("ck_users_valid_role", "users", "role IN ('user','host','admin')")

    op.create_table(
        "rate_limit_buckets",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rate_limit_buckets")),
    )
    with op.batch_alter_table("rate_limit_buckets", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_rate_limit_buckets_expires_at"), ["expires_at"], unique=False)

    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_auth_sessions_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auth_sessions")),
    )
    with op.batch_alter_table("auth_sessions", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_auth_sessions_expires_at"), ["expires_at"], unique=False)
        batch_op.create_index(batch_op.f("ix_auth_sessions_user_id"), ["user_id"], unique=False)

    op.create_table(
        "homestays",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("host_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("address", sa.String(length=500), nullable=False),
        sa.Column("city", sa.String(length=120), nullable=False),
        sa.Column("location", sa.String(length=500), nullable=False),
        sa.Column("amenities", sa.JSON(), nullable=False),
        sa.Column("images", sa.JSON(), nullable=False),
        sa.Column("room_type", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("moderation_reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('active','inactive','deleted')", name=op.f("ck_homestays_valid_status")
        ),
        sa.ForeignKeyConstraint(["host_id"], ["users.id"], name=op.f("fk_homestays_host_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_homestays")),
    )
    with op.batch_alter_table("homestays", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_homestays_city"), ["city"], unique=False)
        batch_op.create_index(batch_op.f("ix_homestays_created_at"), ["created_at"], unique=False)
        batch_op.create_index(batch_op.f("ix_homestays_host_id"), ["host_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_homestays_name"), ["name"], unique=False)
        batch_op.create_index(batch_op.f("ix_homestays_status"), ["status"], unique=False)

    op.create_table(
        "host_applications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("application_data", sa.JSON(), nullable=False),
        sa.Column("reject_reason", sa.Text(), nullable=False),
        sa.Column("reviewed_by", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending','approved','rejected')", name=op.f("ck_host_applications_valid_status")
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by"], ["users.id"], name=op.f("fk_host_applications_reviewed_by_users")
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_host_applications_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_host_applications")),
        sa.UniqueConstraint("user_id", name=op.f("uq_host_applications_user_id")),
    )
    with op.batch_alter_table("host_applications", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_host_applications_status"), ["status"], unique=False)

    op.create_table(
        "bookings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("homestay_id", sa.Integer(), nullable=False),
        sa.Column("check_in", sa.Date(), nullable=False),
        sa.Column("check_out", sa.Date(), nullable=False),
        sa.Column("adults", sa.Integer(), nullable=False),
        sa.Column("children", sa.Integer(), nullable=False),
        sa.Column("guest_name", sa.String(length=160), nullable=False),
        sa.Column("guest_email", sa.String(length=255), nullable=False),
        sa.Column("customer_phone", sa.String(length=20), nullable=False),
        sa.Column("room_subtotal", sa.Numeric(precision=14, scale=0), nullable=False),
        sa.Column("service_fee", sa.Numeric(precision=14, scale=0), nullable=False),
        sa.Column("total_price", sa.Numeric(precision=14, scale=0), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("reject_reason", sa.Text(), nullable=False),
        sa.Column("homestay_name", sa.String(length=160), nullable=False),
        sa.Column("homestay_image", sa.Text(), nullable=False),
        sa.Column("host_address", sa.String(length=500), nullable=False),
        sa.Column("host_phone", sa.String(length=20), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("refund_due", sa.Numeric(precision=14, scale=0), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending','confirmed','checked_in','completed','cancelled','rejected')",
            name=op.f("ck_bookings_valid_status"),
        ),
        sa.CheckConstraint("adults >= 1 AND children >= 0", name=op.f("ck_bookings_guest_counts")),
        sa.CheckConstraint("check_out > check_in", name=op.f("ck_bookings_date_order")),
        sa.CheckConstraint("total_price >= 0 AND service_fee >= 0", name=op.f("ck_bookings_positive_totals")),
        sa.ForeignKeyConstraint(["customer_id"], ["users.id"], name=op.f("fk_bookings_customer_id_users")),
        sa.ForeignKeyConstraint(
            ["homestay_id"], ["homestays.id"], name=op.f("fk_bookings_homestay_id_homestays")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_bookings")),
        sa.UniqueConstraint("code", name=op.f("uq_bookings_code")),
        sa.UniqueConstraint("customer_id", "idempotency_key", name=op.f("uq_bookings_customer_id")),
    )
    with op.batch_alter_table("bookings", schema=None) as batch_op:
        batch_op.create_index(
            "ix_booking_stay_status", ["homestay_id", "check_in", "check_out", "status"], unique=False
        )
        batch_op.create_index(batch_op.f("ix_bookings_created_at"), ["created_at"], unique=False)
        batch_op.create_index(batch_op.f("ix_bookings_customer_id"), ["customer_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_bookings_homestay_id"), ["homestay_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_bookings_status"), ["status"], unique=False)

    op.create_table(
        "rooms",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("homestay_id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("price_per_night", sa.Numeric(precision=14, scale=0), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("inventory", sa.Integer(), nullable=False),
        sa.Column("images", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('active','inactive','deleted')", name=op.f("ck_rooms_valid_status")),
        sa.CheckConstraint("capacity >= 1 AND capacity <= 50", name=op.f("ck_rooms_capacity_range")),
        sa.CheckConstraint("inventory >= 1 AND inventory <= 100", name=op.f("ck_rooms_inventory_range")),
        sa.CheckConstraint(
            "price_per_night >= 0 AND price_per_night <= 99999999999", name=op.f("ck_rooms_price_range")
        ),
        sa.ForeignKeyConstraint(
            ["homestay_id"], ["homestays.id"], name=op.f("fk_rooms_homestay_id_homestays")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rooms")),
        sa.UniqueConstraint("homestay_id", "key", name=op.f("uq_rooms_homestay_id")),
    )
    with op.batch_alter_table("rooms", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_rooms_homestay_id"), ["homestay_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_rooms_status"), ["status"], unique=False)

    op.create_table(
        "booking_lines",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("booking_id", sa.Integer(), nullable=False),
        sa.Column("room_id", sa.Integer(), nullable=False),
        sa.Column("room_name", sa.String(length=160), nullable=False),
        sa.Column("room_key", sa.String(length=80), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("price_per_night", sa.Numeric(precision=14, scale=0), nullable=False),
        sa.CheckConstraint(
            "quantity >= 1 AND price_per_night >= 0", name=op.f("ck_booking_lines_positive_quantity_price")
        ),
        sa.ForeignKeyConstraint(
            ["booking_id"], ["bookings.id"], name=op.f("fk_booking_lines_booking_id_bookings")
        ),
        sa.ForeignKeyConstraint(["room_id"], ["rooms.id"], name=op.f("fk_booking_lines_room_id_rooms")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_booking_lines")),
        sa.UniqueConstraint("booking_id", "room_id", name=op.f("uq_booking_lines_booking_id")),
    )
    with op.batch_alter_table("booking_lines", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_booking_lines_booking_id"), ["booking_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_booking_lines_room_id"), ["room_id"], unique=False)

    op.create_table(
        "booking_status_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("booking_id", sa.Integer(), nullable=False),
        sa.Column("old_status", sa.String(length=20), nullable=True),
        sa.Column("new_status", sa.String(length=20), nullable=False),
        sa.Column("changed_by", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["booking_id"], ["bookings.id"], name=op.f("fk_booking_status_history_booking_id_bookings")
        ),
        sa.ForeignKeyConstraint(
            ["changed_by"], ["users.id"], name=op.f("fk_booking_status_history_changed_by_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_booking_status_history")),
    )
    with op.batch_alter_table("booking_status_history", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_booking_status_history_booking_id"), ["booking_id"], unique=False
        )

    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("booking_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=14, scale=0), nullable=False),
        sa.Column("method", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("transaction_reference", sa.String(length=160), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending','paid','failed','refund_pending','refunded','cancelled')",
            name=op.f("ck_payments_valid_status"),
        ),
        sa.CheckConstraint("amount >= 0", name=op.f("ck_payments_positive_amount")),
        sa.ForeignKeyConstraint(
            ["booking_id"], ["bookings.id"], name=op.f("fk_payments_booking_id_bookings")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payments")),
        sa.UniqueConstraint("booking_id", name=op.f("uq_payments_booking_id")),
        sa.UniqueConstraint("transaction_reference", name=op.f("uq_payments_transaction_reference")),
    )
    op.create_table(
        "reviews",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("booking_id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("homestay_id", sa.Integer(), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("rating >= 1 AND rating <= 5", name=op.f("ck_reviews_rating_range")),
        sa.ForeignKeyConstraint(["booking_id"], ["bookings.id"], name=op.f("fk_reviews_booking_id_bookings")),
        sa.ForeignKeyConstraint(["customer_id"], ["users.id"], name=op.f("fk_reviews_customer_id_users")),
        sa.ForeignKeyConstraint(
            ["homestay_id"], ["homestays.id"], name=op.f("fk_reviews_homestay_id_homestays")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reviews")),
        sa.UniqueConstraint("booking_id", name=op.f("uq_reviews_booking_id")),
    )
    with op.batch_alter_table("reviews", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_reviews_customer_id"), ["customer_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_reviews_homestay_id"), ["homestay_id"], unique=False)

    op.create_table(
        "room_blocks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("room_id", sa.Integer(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("end_date > start_date", name=op.f("ck_room_blocks_date_order")),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name=op.f("fk_room_blocks_created_by_users")),
        sa.ForeignKeyConstraint(["room_id"], ["rooms.id"], name=op.f("fk_room_blocks_room_id_rooms")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_room_blocks")),
    )
    with op.batch_alter_table("room_blocks", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_room_blocks_room_id"), ["room_id"], unique=False)

    op.create_table(
        "room_nights",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("room_id", sa.Integer(), nullable=False),
        sa.Column("unit", sa.Integer(), nullable=False),
        sa.Column("night", sa.Date(), nullable=False),
        sa.Column("booking_id", sa.Integer(), nullable=True),
        sa.Column("block_id", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "(booking_id IS NOT NULL AND block_id IS NULL) OR (booking_id IS NULL AND block_id IS NOT NULL)",
            name=op.f("ck_room_nights_single_reservation_owner"),
        ),
        sa.CheckConstraint("unit >= 1", name=op.f("ck_room_nights_positive_unit")),
        sa.ForeignKeyConstraint(
            ["block_id"], ["room_blocks.id"], name=op.f("fk_room_nights_block_id_room_blocks")
        ),
        sa.ForeignKeyConstraint(
            ["booking_id"], ["bookings.id"], name=op.f("fk_room_nights_booking_id_bookings")
        ),
        sa.ForeignKeyConstraint(["room_id"], ["rooms.id"], name=op.f("fk_room_nights_room_id_rooms")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_room_nights")),
        sa.UniqueConstraint("room_id", "unit", "night", name=op.f("uq_room_nights_room_id")),
    )
    with op.batch_alter_table("room_nights", schema=None) as batch_op:
        batch_op.create_index("ix_room_night_lookup", ["room_id", "night"], unique=False)
        batch_op.create_index(batch_op.f("ix_room_nights_block_id"), ["block_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_room_nights_booking_id"), ["booking_id"], unique=False)

    # ### end Alembic commands ###


def downgrade():
    raise RuntimeError("Destructive downgrade is disabled; use an explicitly verified database backup")
