"""Explicit output allowlists preserve frontend casing without exposing ORM secrets."""

from sqlalchemy import func, select

from .models import BookingLine, BookingStatusHistory, HostApplicationHistory, Review, Room, RoomBlock, User


def iso(value):
    return value.isoformat().replace("+00:00", "Z") if value else None


def user_out(user):
    return {
        "id": user.id,
        "display_name": user.display_name,
        "email": user.email,
        "phone": user.phone,
        "role": user.role,
        "avatar": user.avatar,
        "createdAt": iso(user.created_at),
    }


def room_out(db, room, blocks=None):
    if blocks is None:
        blocks = db.scalars(select(RoomBlock).where(RoomBlock.room_id == room.id)).all()
    from datetime import timedelta

    dates = set()
    for block in blocks:
        if block.unit is not None:
            continue  # Legacy blockedDates means all-unit closure, never a partial closure.
        current = block.start_date
        while current < block.end_date:
            dates.add(current.isoformat())
            current += timedelta(days=1)
    return {
        "id": str(room.id),
        "homestayId": str(room.homestay_id),
        "key": room.key,
        "name": room.name,
        "description": room.description,
        "pricePerNight": int(room.price_per_night),
        "capacity": room.capacity,
        "inventory": room.inventory,
        "images": room.images,
        "status": room.status,
        "blockedDates": sorted(dates),
        "blocks": [
            {
                "id": b.id,
                "start_date": b.start_date.isoformat(),
                "end_date": b.end_date.isoformat(),
                "unit": b.unit,
                "scope": "unit" if b.unit is not None else "all",
                "reason": b.reason,
            }
            for b in blocks
        ],
    }


def public_room(room):
    return {
        "id": str(room.id),
        "key": room.key,
        "name": room.name,
        "description": room.description,
        "price": int(room.price_per_night),
        "pricePerNight": int(room.price_per_night),
        "capacity": room.capacity,
        "inventory": room.inventory,
        "images": room.images,
        "image": room.images[0] if room.images else "img/placeholder.svg",
    }


def homestay_out(db, item, public=False, loaded=None):
    if not public:
        return {
            "id": str(item.id),
            "itemId": item.id,
            "hostId": str(item.host_id),
            "name": item.name,
            "address": item.address,
            "location": item.location,
            "city": item.city,
            "description": item.description,
            "amenities": item.amenities,
            "images": item.images,
            "status": item.status,
            "createdAt": iso(item.created_at),
        }
    if loaded is None:
        rooms = db.scalars(
            select(Room)
            .where(Room.homestay_id == item.id, Room.status == "active", Room.price_per_night > 0)
            .order_by(Room.price_per_night, Room.id)
        ).all()
        rating = db.scalar(select(func.avg(Review.rating)).where(Review.homestay_id == item.id))
        count = db.scalar(select(func.count()).select_from(Review).where(Review.homestay_id == item.id))
        host = db.get(User, item.host_id)
    else:
        rooms, rating, count, host = loaded
    return {
        "id": item.id,
        "title": item.name,
        "location": item.location,
        "meta": item.location,
        "description": item.description,
        "room_type": item.room_type,
        "amenities": item.amenities,
        "price": int(min(room.price_per_night for room in rooms)) if rooms else None,
        "rating": round(float(rating), 1) if rating is not None else None,
        "review_count": count,
        "cover_url": item.images[0] if item.images else "img/placeholder.svg",
        "images": item.images,
        "hostPhone": host.phone,
        "roomTypes": [public_room(room) for room in rooms],
        "status": item.status,
        "created_at": iso(item.created_at),
    }


def public_homestays(db, items, eligible):
    """Bounded batch loading for catalog pages; no query per result."""
    if not items:
        return []
    ids = [item.id for item in items]
    rooms = {}
    for room in db.scalars(
        select(Room)
        .join(eligible, eligible.c.id == Room.id)
        .where(Room.homestay_id.in_(ids))
        .order_by(Room.price_per_night, Room.id)
    ):
        rooms.setdefault(room.homestay_id, []).append(room)
    stats = {
        row[0]: (row[1], row[2])
        for row in db.execute(
            select(Review.homestay_id, func.avg(Review.rating), func.count())
            .where(Review.homestay_id.in_(ids))
            .group_by(Review.homestay_id)
        )
    }
    hosts = {
        user.id: user for user in db.scalars(select(User).where(User.id.in_({i.host_id for i in items})))
    }
    return [
        homestay_out(
            db,
            item,
            public=True,
            loaded=(rooms.get(item.id, []), *stats.get(item.id, (None, 0)), hosts[item.host_id]),
        )
        for item in items
    ]


def booking_out(db, booking, host=False, lines=None, history=None):
    lines = (
        lines
        if lines is not None
        else db.scalars(
            select(BookingLine).where(BookingLine.booking_id == booking.id).order_by(BookingLine.id)
        ).all()
    )
    nights = (booking.check_out - booking.check_in).days
    result = {
        "id": str(booking.id) if host else booking.id,
        "bookingId": booking.id,
        "code": booking.code,
        "userId": booking.customer_id,
        "homestayId": booking.homestay_id,
        "homestayName": booking.homestay_name,
        "homestayImage": booking.homestay_image,
        "homestayAddress": booking.host_address,
        "hostAddress": booking.host_address,
        "hostPhone": booking.host_phone,
        "roomId": str(lines[0].room_id) if lines else None,
        "roomIds": [str(line.room_id) for line in lines],
        "roomName": ", ".join(f"{line.quantity} × {line.room_name}" for line in lines),
        "rooms": [
            {
                "roomId": str(line.room_id),
                "key": line.room_key,
                "name": line.room_name,
                "qty": line.quantity,
                "pricePerNight": int(line.price_per_night),
            }
            for line in lines
        ],
        "checkIn": booking.check_in.isoformat(),
        "checkOut": booking.check_out.isoformat(),
        "nights": nights,
        "adults": booking.adults,
        "children": booking.children,
        "guests": booking.adults + booking.children,
        "guestName": booking.guest_name,
        "guestEmail": booking.guest_email,
        "customerName": booking.guest_name,
        "customerPhone": booking.customer_phone,
        "pricePerNight": int(booking.room_subtotal / nights),
        "roomSubtotal": int(booking.room_subtotal),
        "serviceFee": int(booking.service_fee),
        "totalPrice": int(booking.total_price),
        "status": booking.status,
        "rejectReason": booking.reject_reason,
        "refundDue": int(booking.refund_due),
        "createdAt": iso(booking.created_at),
        "updatedAt": iso(booking.updated_at),
    }
    if not host:
        history = (
            history
            if history is not None
            else db.scalars(
                select(BookingStatusHistory)
                .where(BookingStatusHistory.booking_id == booking.id)
                .order_by(BookingStatusHistory.id)
            ).all()
        )
        result["statusHistory"] = [
            {
                "oldStatus": entry.old_status,
                "newStatus": entry.new_status,
                "changedAt": iso(entry.changed_at),
                "reason": entry.reason,
            }
            for entry in history
        ]
    return result


def application_out(db, application, owner=None, history=None):
    if history is None:
        history = list(
            db.scalars(
                select(HostApplicationHistory)
                .where(HostApplicationHistory.application_id == application.id)
                .order_by(HostApplicationHistory.id)
            )
        )
    return {
        "history": [
            {
                "status": h.status,
                "application_data": h.application_data,
                "rejectReason": h.reject_reason,
                "reviewedBy": h.reviewed_by,
                "reviewedAt": iso(h.reviewed_at),
            }
            for h in history
        ],
        "id": application.id,
        "user": user_out(owner if owner is not None else db.get(User, application.user_id)),
        "status": application.status,
        "application_data": application.application_data,
        "rejectReason": application.reject_reason,
        "reviewedBy": application.reviewed_by,
        "reviewedAt": iso(application.reviewed_at),
        "createdAt": iso(application.created_at),
    }


def review_out(db, review, author=None):
    return {
        "id": review.id,
        "bookingId": review.booking_id,
        "name": (author if author is not None else db.get(User, review.customer_id)).display_name,
        "rating": review.rating,
        "comment": review.comment,
        "verified": True,
        "created_at": iso(review.created_at),
    }


def booking_list_out(db, bookings, host=False):
    bookings = list(bookings)
    ids = [b.id for b in bookings]
    if not ids:
        return []
    lines, history = {}, {}
    for row in db.scalars(
        select(BookingLine).where(BookingLine.booking_id.in_(ids)).order_by(BookingLine.id)
    ):
        lines.setdefault(row.booking_id, []).append(row)
    if not host:
        for row in db.scalars(
            select(BookingStatusHistory)
            .where(BookingStatusHistory.booking_id.in_(ids))
            .order_by(BookingStatusHistory.id)
        ):
            history.setdefault(row.booking_id, []).append(row)
    return [
        booking_out(db, b, host=host, lines=lines.get(b.id, []), history=history.get(b.id, []))
        for b in bookings
    ]
