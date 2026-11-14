"""Canonical relational data; compatibility JSON is produced by serializers."""

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base, UTCDateTime


def utcnow():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("role IN ('user','host','admin')", name="valid_role"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(80))
    phone: Mapped[str] = mapped_column(String(20), default="")
    role: Mapped[str] = mapped_column(String(20), default="user", index=True)
    avatar: Mapped[str] = mapped_column(Text, default="img/placeholder.svg")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    token_version: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)


class Item(Base):
    """Retained legacy template table; never silently deleted or used as a second catalog."""

    __tablename__ = "items"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(160), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    price: Mapped[int] = mapped_column(default=0)
    cover_url: Mapped[str] = mapped_column(String(255), default="img/placeholder.svg")
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    revoked: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class HostApplication(Base):
    __tablename__ = "host_applications"
    __table_args__ = (CheckConstraint("status IN ('pending','approved','rejected')", name="valid_status"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    application_data: Mapped[dict] = mapped_column(JSON, default=dict)
    reject_reason: Mapped[str] = mapped_column(Text, default="")
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class HostApplicationHistory(Base):
    __tablename__ = "host_application_history"
    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("host_applications.id"), index=True)
    status: Mapped[str] = mapped_column(String(20))
    application_data: Mapped[dict] = mapped_column(JSON)
    reject_reason: Mapped[str] = mapped_column(Text, default="")
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime] = mapped_column(UTCDateTime())


class Homestay(Base):
    __tablename__ = "homestays"
    __table_args__ = (CheckConstraint("status IN ('active','inactive','deleted')", name="valid_status"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    host_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    address: Mapped[str] = mapped_column(String(500))
    city: Mapped[str] = mapped_column(String(120), index=True)
    location: Mapped[str] = mapped_column(String(500))
    amenities: Mapped[list] = mapped_column(JSON, default=list)
    images: Mapped[list] = mapped_column(JSON, default=list)
    room_type: Mapped[str] = mapped_column(String(80), default="Phòng riêng")
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    moderation_reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)


class Room(Base):
    __tablename__ = "rooms"
    __table_args__ = (
        UniqueConstraint("homestay_id", "key"),
        CheckConstraint("price_per_night >= 0 AND price_per_night <= 99999999999", name="price_range"),
        CheckConstraint("capacity >= 1 AND capacity <= 50", name="capacity_range"),
        CheckConstraint("inventory >= 1 AND inventory <= 100", name="inventory_range"),
        CheckConstraint("status IN ('active','inactive','deleted')", name="valid_status"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    homestay_id: Mapped[int] = mapped_column(ForeignKey("homestays.id"), index=True)
    key: Mapped[str] = mapped_column(String(80))
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    price_per_night: Mapped[Decimal] = mapped_column(Numeric(14, 0))
    capacity: Mapped[int] = mapped_column(default=2)
    inventory: Mapped[int] = mapped_column(default=1)
    images: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)


class Booking(Base):
    __tablename__ = "bookings"
    __table_args__ = (
        UniqueConstraint("customer_id", "idempotency_key"),
        CheckConstraint("check_out > check_in", name="date_order"),
        CheckConstraint("adults >= 1 AND children >= 0", name="guest_counts"),
        CheckConstraint("total_price >= 0 AND service_fee >= 0", name="positive_totals"),
        CheckConstraint(
            "status IN ('pending','confirmed','checked_in','completed','cancelled','rejected')",
            name="valid_status",
        ),
        Index("ix_booking_stay_status", "homestay_id", "check_in", "check_out", "status"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    homestay_id: Mapped[int] = mapped_column(ForeignKey("homestays.id"), index=True)
    check_in: Mapped[date] = mapped_column(Date)
    check_out: Mapped[date] = mapped_column(Date)
    adults: Mapped[int] = mapped_column()
    children: Mapped[int] = mapped_column(default=0)
    guest_name: Mapped[str] = mapped_column(String(160))
    guest_email: Mapped[str] = mapped_column(String(255))
    customer_phone: Mapped[str] = mapped_column(String(20), default="")
    room_subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 0))
    service_fee: Mapped[Decimal] = mapped_column(Numeric(14, 0))
    total_price: Mapped[Decimal] = mapped_column(Numeric(14, 0))
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    reject_reason: Mapped[str] = mapped_column(Text, default="")
    homestay_name: Mapped[str] = mapped_column(String(160))
    homestay_image: Mapped[str] = mapped_column(Text)
    host_address: Mapped[str] = mapped_column(String(500))
    host_phone: Mapped[str] = mapped_column(String(20))
    idempotency_key: Mapped[str | None] = mapped_column(String(128))
    request_hash: Mapped[str] = mapped_column(String(64), default="")
    refund_due: Mapped[Decimal] = mapped_column(Numeric(14, 0), default=0)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)


class BookingLine(Base):
    __tablename__ = "booking_lines"
    __table_args__ = (
        UniqueConstraint("booking_id", "room_id"),
        CheckConstraint("quantity >= 1 AND price_per_night >= 0", name="positive_quantity_price"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey("bookings.id"), index=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"), index=True)
    room_name: Mapped[str] = mapped_column(String(160))
    room_key: Mapped[str] = mapped_column(String(80))
    quantity: Mapped[int] = mapped_column()
    capacity: Mapped[int] = mapped_column()
    price_per_night: Mapped[Decimal] = mapped_column(Numeric(14, 0))


class RoomBlock(Base):
    __tablename__ = "room_blocks"
    __table_args__ = (
        CheckConstraint("end_date > start_date", name="date_order"),
        CheckConstraint("unit IS NULL OR (unit >= 1 AND unit <= 100)", name="unit_range"),
    )
    unit: Mapped[int | None] = mapped_column(nullable=True)
    id: Mapped[int] = mapped_column(primary_key=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"), index=True)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    reason: Mapped[str] = mapped_column(String(500), default="")
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class RoomNight(Base):
    __tablename__ = "room_nights"
    __table_args__ = (
        UniqueConstraint("room_id", "unit", "night"),
        CheckConstraint("unit >= 1", name="positive_unit"),
        CheckConstraint(
            "(booking_id IS NOT NULL AND block_id IS NULL) OR (booking_id IS NULL AND block_id IS NOT NULL)",
            name="single_reservation_owner",
        ),
        Index("ix_room_night_lookup", "room_id", "night"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"))
    unit: Mapped[int] = mapped_column()
    night: Mapped[date] = mapped_column(Date)
    booking_id: Mapped[int | None] = mapped_column(ForeignKey("bookings.id"), index=True)
    block_id: Mapped[int | None] = mapped_column(ForeignKey("room_blocks.id"), index=True)


class BookingStatusHistory(Base):
    __tablename__ = "booking_status_history"
    id: Mapped[int] = mapped_column(primary_key=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey("bookings.id"), index=True)
    old_status: Mapped[str | None] = mapped_column(String(20))
    new_status: Mapped[str] = mapped_column(String(20))
    changed_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    reason: Mapped[str] = mapped_column(Text, default="")
    changed_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (CheckConstraint("rating >= 1 AND rating <= 5", name="rating_range"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey("bookings.id"), unique=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    homestay_id: Mapped[int] = mapped_column(ForeignKey("homestays.id"), index=True)
    rating: Mapped[int] = mapped_column()
    comment: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("amount >= 0", name="positive_amount"),
        CheckConstraint(
            "status IN ('pending','paid','failed','refund_pending','refunded','cancelled')",
            name="valid_status",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey("bookings.id"), unique=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 0))
    method: Mapped[str] = mapped_column(String(30), default="pay_at_property")
    status: Mapped[str] = mapped_column(String(30), default="pending")
    transaction_reference: Mapped[str | None] = mapped_column(String(160), unique=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class PaymentEvent(Base):
    __tablename__ = "payment_events"
    __table_args__ = (
        CheckConstraint(
            "amount >= 0 AND refund_amount >= 0 AND refund_amount <= amount", name="amount_range"
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    payment_id: Mapped[int] = mapped_column(ForeignKey("payments.id"), index=True)
    old_status: Mapped[str | None] = mapped_column(String(20))
    new_status: Mapped[str] = mapped_column(String(20))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 0))
    refund_amount: Mapped[Decimal] = mapped_column(Numeric(14, 0), default=0)
    source: Mapped[str] = mapped_column(String(32))
    note: Mapped[str] = mapped_column(Text, default="")
    changed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class RateLimitBucket(Base):
    __tablename__ = "rate_limit_buckets"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    count: Mapped[int] = mapped_column(default=1)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
