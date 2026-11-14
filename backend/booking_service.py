"""Server-authoritative quote, atomic inventory allocation, status transitions."""

import hashlib
import json
import secrets
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import delete, select

from .models import (
    Booking,
    BookingLine,
    BookingStatusHistory,
    Homestay,
    Payment,
    Room,
    RoomBlock,
    RoomNight,
    User,
    utcnow,
)

ACTIVE = ("pending", "confirmed", "checked_in")
IDEMPOTENCY_WINDOW = timedelta(hours=24)


def business_today():
    return datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date()


def validate_stay(checkin, checkout):
    if checkin < business_today() or not 0 < (checkout - checkin).days <= 365:
        raise HTTPException(422, "Ngày lưu trú không hợp lệ; tối đa 365 đêm, không đặt ngày quá khứ.")


def nights(start, end):
    return [start + timedelta(days=index) for index in range((end - start).days)]


def free_units(db, room, checkin, checkout):
    used = set(
        db.scalars(
            select(RoomNight.unit).where(
                RoomNight.room_id == room.id, RoomNight.night >= checkin, RoomNight.night < checkout
            )
        )
    )
    return [unit for unit in range(1, room.inventory + 1) if unit not in used]


def calculate_quote(db, payload, lock=False):
    validate_stay(payload.check_in, payload.check_out)
    stay_query = (
        select(Homestay)
        .join(User, User.id == Homestay.host_id)
        .where(
            Homestay.id == payload.homestay_id,
            Homestay.status == "active",
            User.is_active.is_(True),
            User.role == "host",
        )
    )
    homestay = db.scalar(
        stay_query.with_for_update(of=Homestay).execution_options(populate_existing=True)
        if lock
        else stay_query
    )
    if not homestay:
        raise HTTPException(404, "Không tìm thấy homestay đang hoạt động.")
    query = (
        select(Room)
        .where(Room.homestay_id == homestay.id, Room.status == "active", Room.price_per_night > 0)
        .order_by(Room.id)
    )
    rooms = db.scalars(
        query.with_for_update().execution_options(populate_existing=True) if lock else query
    ).all()
    selected = []
    seen = set()
    for selection in payload.rooms:
        room = (
            next((room for room in rooms if room.id == selection.room_id), None)
            if selection.room_id
            else next((room for room in rooms if room.key == selection.key), None)
        )
        if not room or (selection.key and selection.key != room.key):
            raise HTTPException(422, "Loại phòng không thuộc homestay hoặc đã ngừng hoạt động.")
        if room.id in seen:
            raise HTTPException(422, "Không được gửi lặp một loại phòng.")
        seen.add(room.id)
        units = free_units(db, room, payload.check_in, payload.check_out)
        if len(units) < selection.qty:
            raise HTTPException(409, "Phòng không còn đủ cho toàn bộ thời gian lưu trú.")
        selected.append((room, selection.qty, units[: selection.qty]))
    count_nights = (payload.check_out - payload.check_in).days
    capacity = sum(room.capacity * qty for room, qty, _ in selected)
    if capacity < payload.adults + payload.children:
        raise HTTPException(422, "Số khách vượt sức chứa các phòng đã chọn.")
    subtotal = sum((room.price_per_night * qty * count_nights for room, qty, _ in selected), Decimal(0))
    fee = (subtotal * Decimal("0.05")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    if subtotal + fee > Decimal("99999999999999"):
        raise HTTPException(422, "Giá trị đặt phòng quá lớn.")
    quote = {
        "nights": count_nights,
        "roomCount": sum(qty for _, qty, _ in selected),
        "capacity": capacity,
        "roomSubtotal": int(subtotal),
        "serviceFee": int(fee),
        "total": int(subtotal + fee),
        "lines": [
            {
                "key": room.key,
                "roomId": str(room.id),
                "name": room.name,
                "qty": qty,
                "pricePerNight": int(room.price_per_night),
                "capacity": room.capacity,
                "subtotal": int(room.price_per_night * qty * count_nights),
            }
            for room, qty, _ in selected
        ],
    }
    return homestay, selected, quote


def create_booking(db, payload, user, idempotency_key=None):
    token_version = user.token_version
    user = db.scalar(
        select(User).where(User.id == user.id).with_for_update().execution_options(populate_existing=True)
    )
    if not user or not user.is_active or user.token_version != token_version:
        raise HTTPException(401, "Account session is no longer valid.")
    if user.role != "user":
        raise HTTPException(403, "Chỉ tài khoản khách hàng được tạo đặt phòng.")
    fingerprint = hashlib.sha256(
        json.dumps(payload.model_dump(mode="json"), sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    # Serializing per customer also closes the same-key race on PostgreSQL.
    if idempotency_key:
        old = db.scalar(
            select(Booking).where(Booking.customer_id == user.id, Booking.idempotency_key == idempotency_key)
        )
        if old:
            if utcnow() - old.created_at > IDEMPOTENCY_WINDOW:
                raise HTTPException(
                    409,
                    "Idempotency-Key replay window expired; reconcile the original booking before using a new key.",
                )
            if old.request_hash != fingerprint:
                raise HTTPException(409, "Idempotency-Key đã được dùng cho yêu cầu khác.")
            return old, False
    homestay, selected, quote = calculate_quote(db, payload, lock=True)
    host = db.get(User, homestay.host_id)
    if not host or not host.is_active or host.role != "host":
        raise HTTPException(409, "Chủ homestay hiện không nhận đặt phòng.")
    booking = Booking(
        code="BK" + secrets.token_hex(8).upper(),
        customer_id=user.id,
        homestay_id=homestay.id,
        check_in=payload.check_in,
        check_out=payload.check_out,
        adults=payload.adults,
        children=payload.children,
        guest_name=payload.guest_name,
        guest_email=str(payload.guest_email),
        customer_phone=user.phone,
        room_subtotal=quote["roomSubtotal"],
        service_fee=quote["serviceFee"],
        total_price=quote["total"],
        homestay_name=homestay.name,
        homestay_image=homestay.images[0] if homestay.images else "img/placeholder.svg",
        host_address=homestay.address,
        host_phone=host.phone,
        idempotency_key=idempotency_key,
        request_hash=fingerprint,
    )
    db.add(booking)
    db.flush()
    for room, qty, units in selected:
        db.add(
            BookingLine(
                booking_id=booking.id,
                room_id=room.id,
                room_name=room.name,
                room_key=room.key,
                quantity=qty,
                capacity=room.capacity,
                price_per_night=room.price_per_night,
            )
        )
        for unit in units:
            for night in nights(payload.check_in, payload.check_out):
                db.add(RoomNight(room_id=room.id, unit=unit, night=night, booking_id=booking.id))
    db.add(
        BookingStatusHistory(booking_id=booking.id, old_status=None, new_status="pending", changed_by=user.id)
    )
    payment = Payment(booking_id=booking.id, amount=booking.total_price)
    db.add(payment)
    db.flush()
    from .payment_service import record_event

    record_event(db, payment, None, user, "booking")
    db.commit()
    return booking, True


def change_status(db, booking, status, actor, reason=""):
    if booking.status == status:
        if status == "cancelled" and actor.id == booking.customer_id:
            return booking
        raise HTTPException(409, "Booking already has this status.")
    allowed = {
        "pending": {"confirmed", "cancelled", "rejected"},
        "confirmed": {"checked_in", "cancelled"},
        "checked_in": {"completed"},
    }
    if status not in allowed.get(booking.status, set()):
        raise HTTPException(409, "Không thể chuyển trạng thái đặt phòng như yêu cầu.")
    reason = reason.strip()
    if status == "rejected" and len(reason) < 3:
        raise HTTPException(422, "Vui lòng nhập lý do từ chối (ít nhất 3 ký tự).")
    today = business_today()
    if status == "confirmed" and today >= booking.check_out:
        raise HTTPException(409, "Không thể xác nhận đặt phòng đã hết thời gian lưu trú.")
    if status == "checked_in" and not booking.check_in <= today < booking.check_out:
        raise HTTPException(409, "Nhận phòng chỉ được thực hiện trong ngày lưu trú.")
    if status == "completed" and today < booking.check_out:
        raise HTTPException(409, "Chưa đến ngày trả phòng.")
    db.add(
        BookingStatusHistory(
            booking_id=booking.id,
            old_status=booking.status,
            new_status=status,
            changed_by=actor.id,
            reason=reason,
        )
    )
    booking.status = status
    if status == "rejected":
        booking.reject_reason = reason
    if status in {"cancelled", "rejected"}:
        db.execute(delete(RoomNight).where(RoomNight.booking_id == booking.id))
        payment = db.scalar(select(Payment).where(Payment.booking_id == booking.id).with_for_update())
        if payment and payment.amount != booking.total_price:
            raise HTTPException(409, "Payment amount is inconsistent with booking.")
        old_payment_status = payment.status if payment else None
        refundable = status == "rejected" or (booking.check_in - today).days >= 3
        if payment and payment.status == "paid":
            booking.refund_due = booking.total_price if refundable else 0
            if refundable:
                payment.status = "refund_pending"
        elif payment and payment.status == "pending":
            payment.status = "cancelled"
        if payment and payment.status != old_payment_status:
            from .payment_service import record_event

            record_event(db, payment, old_payment_status, actor, "booking_" + status, booking.refund_due)
    db.commit()
    return booking


def add_block(db, room, start, end, reason, actor, unit=None, existing=None):
    if not 0 < (end - start).days <= 365:
        raise HTTPException(422, "Khoảng ngày chặn không hợp lệ.")
    if unit is not None and not 1 <= unit <= room.inventory:
        raise HTTPException(422, "Unit exceeds room inventory.")
    conflict = select(RoomNight.id).where(
        RoomNight.room_id == room.id, RoomNight.night >= start, RoomNight.night < end
    )
    if unit is not None:
        conflict = conflict.where(RoomNight.unit == unit)
    if db.scalar(conflict.limit(1)):
        raise HTTPException(409, "Lịch chặn trùng với đặt phòng hoặc lịch chặn hiện có.")
    block = existing or RoomBlock(room_id=room.id, created_by=actor.id)
    block.start_date, block.end_date, block.reason, block.unit = start, end, reason, unit
    if existing is None:
        db.add(block)
    db.flush()
    for night in nights(start, end):
        for reserved_unit in [unit] if unit is not None else range(1, room.inventory + 1):
            db.add(RoomNight(room_id=room.id, unit=reserved_unit, night=night, block_id=block.id))
    db.flush()
    return block
