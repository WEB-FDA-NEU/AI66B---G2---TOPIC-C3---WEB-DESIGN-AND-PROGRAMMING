from datetime import date
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .. import schemas
from ..booking_service import validate_stay
from ..database import get_db
from ..deps import get_current_user
from ..models import Booking, Homestay, Review, Room, RoomNight, User
from ..serializers import homestay_out, public_homestays, public_room, review_out

router = APIRouter(prefix="/api/items", tags=["catalog"])


def public_item(db, item_id):
    item = db.scalar(
        select(Homestay)
        .join(User, User.id == Homestay.host_id)
        .where(
            Homestay.id == item_id, Homestay.status == "active", User.is_active.is_(True), User.role == "host"
        )
    )
    if not item:
        raise HTTPException(404, "Không tìm thấy homestay.")
    return item


@router.get("")
def search_items(
    q: str = Query("", max_length=200),
    sort: Literal["newest", "price_asc", "price_desc", "rating_desc"] = "newest",
    page: int = Query(1, ge=1, le=100000),
    page_size: int = Query(20, ge=1, le=1000),
    min_price: Decimal | None = Query(None, ge=0),
    max_price: Decimal | None = Query(None, ge=0),
    room_type: list[str] = Query(default=[]),
    amenity: list[str] = Query(default=[]),
    rating: float | None = Query(None, ge=0, le=5),
    checkin: date | None = None,
    checkout: date | None = None,
    guests: int = Query(1, ge=1, le=16),
    children: int = Query(0, ge=0, le=6),
    category: str = Query("", max_length=80),
    db: Session = Depends(get_db),
):
    if bool(checkin) != bool(checkout):
        raise HTTPException(422, "Cần chọn cả ngày nhận và trả phòng.")
    if checkin:
        validate_stay(checkin, checkout)
    if min_price is not None and max_price is not None and min_price > max_price:
        raise HTTPException(422, "Khoảng giá không hợp lệ.")
    if len(room_type) > 20 or len(amenity) > 40 or any(len(value) > 100 for value in [*room_type, *amenity]):
        raise HTTPException(422, "Bộ lọc quá lớn.")
    # A unit must be free for the entire stay; do not sum daily free counts.
    eligible = select(
        Room.id, Room.homestay_id, Room.price_per_night, (Room.capacity * Room.inventory).label("capacity")
    ).where(Room.status == "active", Room.price_per_night > 0)
    if checkin:
        occupied = (
            select(RoomNight.room_id, func.count(func.distinct(RoomNight.unit)).label("used"))
            .where(RoomNight.night >= checkin, RoomNight.night < checkout)
            .group_by(RoomNight.room_id)
            .subquery()
        )
        free = Room.inventory - func.coalesce(occupied.c.used, 0)
        eligible = (
            select(Room.id, Room.homestay_id, Room.price_per_night, (Room.capacity * free).label("capacity"))
            .outerjoin(occupied, occupied.c.room_id == Room.id)
            .where(Room.status == "active", Room.price_per_night > 0, free > 0)
        )
    if min_price is not None:
        eligible = eligible.where(Room.price_per_night >= min_price)
    if max_price is not None:
        eligible = eligible.where(Room.price_per_night <= max_price)
    eligible = eligible.subquery()
    prices = (
        select(eligible.c.homestay_id, func.min(eligible.c.price_per_night).label("price"))
        .group_by(eligible.c.homestay_id)
        .having(func.sum(eligible.c.capacity) >= guests + children)
        .subquery()
    )
    ratings = (
        select(Review.homestay_id, func.avg(Review.rating).label("rating"))
        .group_by(Review.homestay_id)
        .subquery()
    )
    query = (
        select(Homestay)
        .join(User, User.id == Homestay.host_id)
        .join(prices, prices.c.homestay_id == Homestay.id)
        .outerjoin(ratings, ratings.c.homestay_id == Homestay.id)
        .where(Homestay.status == "active", User.is_active.is_(True), User.role == "host")
    )
    if q:
        query = query.where(
            or_(
                Homestay.name.ilike(f"%{q}%"),
                Homestay.location.ilike(f"%{q}%"),
                Homestay.city.ilike(f"%{q}%"),
            )
        )
    if room_type:
        query = query.where(Homestay.room_type.in_(room_type))
    if rating is not None:
        query = query.where(ratings.c.rating >= rating)
    for value in amenity:
        # JSON array membership, not substring matching; both databases bind the value.
        elements = (
            (
                func.json_each(Homestay.amenities)
                if db.bind.dialect.name == "sqlite"
                else func.json_array_elements_text(Homestay.amenities)
            )
            .table_valued("value")
            .alias()
        )
        query = query.where(select(1).select_from(elements).where(elements.c.value == value).exists())
    order = {
        "price_asc": prices.c.price.asc(),
        "price_desc": prices.c.price.desc(),
        "rating_desc": ratings.c.rating.desc().nulls_last(),
    }.get(sort, Homestay.created_at.desc())
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    items = list(
        db.scalars(query.order_by(order, Homestay.id).offset((page - 1) * page_size).limit(page_size))
    )
    return {
        "items": public_homestays(db, items, eligible),
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/{item_id}")
def detail(item_id: int, db: Session = Depends(get_db)):
    return homestay_out(db, public_item(db, item_id), public=True)


@router.get("/{item_id}/availability")
def availability(
    item_id: int,
    checkin: date,
    checkout: date,
    adults: int = Query(2, ge=1, le=10),
    children: int = Query(0, ge=0, le=6),
    db: Session = Depends(get_db),
):
    public_item(db, item_id)
    validate_stay(checkin, checkout)
    rooms = db.scalars(
        select(Room)
        .where(Room.homestay_id == item_id, Room.status == "active", Room.price_per_night > 0)
        .order_by(Room.price_per_night, Room.id)
    )
    rooms = list(rooms)
    occupied = {}
    for room_id, unit in db.execute(
        select(RoomNight.room_id, RoomNight.unit)
        .where(
            RoomNight.room_id.in_([r.id for r in rooms]),
            RoomNight.night >= checkin,
            RoomNight.night < checkout,
        )
        .distinct()
    ):
        occupied.setdefault(room_id, set()).add(unit)
    values = [
        {
            **public_room(room),
            "available": len(set(range(1, room.inventory + 1)) - occupied.get(room.id, set())),
        }
        for room in rooms
    ]
    return {
        "homestayId": item_id,
        "checkIn": checkin.isoformat(),
        "checkOut": checkout.isoformat(),
        "guests": adults + children,
        "rooms": values,
        "capacity": sum(room["available"] * room["capacity"] for room in values),
    }


@router.get("/{item_id}/reviews")
def reviews(
    item_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_db),
):
    public_item(db, item_id)
    rows = list(
        db.scalars(
            select(Review)
            .where(Review.homestay_id == item_id)
            .order_by(Review.created_at.desc(), Review.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    authors = {u.id: u for u in db.scalars(select(User).where(User.id.in_([r.customer_id for r in rows])))}
    return [review_out(db, r, authors[r.customer_id]) for r in rows]


@router.post("/{item_id}/reviews", status_code=201)
def add_review(
    item_id: int,
    payload: schemas.ReviewIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user.role != "user":
        raise HTTPException(403, "Only customers may submit reviews.")
    public_item(db, item_id)
    query = select(Booking).where(
        Booking.customer_id == user.id, Booking.homestay_id == item_id, Booking.status == "completed"
    )
    if payload.booking_id:
        query = query.where(Booking.id == payload.booking_id)
    query = query.where(~select(Review.id).where(Review.booking_id == Booking.id).exists())
    booking = db.scalar(query.order_by(Booking.id).with_for_update())
    if not booking:
        raise HTTPException(409, "Bạn cần đặt phòng đã hoàn tất và chưa đánh giá.")
    review = Review(
        booking_id=booking.id,
        customer_id=user.id,
        homestay_id=item_id,
        rating=payload.rating,
        comment=payload.comment,
    )
    db.add(review)
    db.commit()
    return review_out(db, review)
