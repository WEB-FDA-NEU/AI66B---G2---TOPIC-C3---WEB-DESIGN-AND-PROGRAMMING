import secrets
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import case, delete, func, select
from sqlalchemy.orm import Session

from .. import schemas
from ..booking_service import ACTIVE, add_block, business_today, change_status, nights
from ..database import get_db
from ..deps import get_host, owned_homestay, owned_room
from ..media import normalize_image
from ..models import Booking, BookingLine, Homestay, Room, RoomBlock, RoomNight, User
from ..serializers import booking_list_out, booking_out, homestay_out, room_out

router = APIRouter(prefix="/api/host", tags=["host"])


@router.get("/homestays")
def homestays(
    user: User = Depends(get_host),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=100),
):
    return [
        homestay_out(db, item)
        for item in db.scalars(
            select(Homestay)
            .where(Homestay.host_id == user.id, Homestay.status != "deleted")
            .order_by(Homestay.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ]


def save_homestay(payload, request, db, user, item=None):
    if (
        item
        and item.status == "inactive"
        and item.moderation_reason
        and payload.status == "active"
        and "status" in payload.model_fields_set
    ):
        raise HTTPException(409, "Homestay is under admin moderation.")
    data = payload.model_dump(exclude={"id"})
    if item and "status" not in payload.model_fields_set:
        data.pop("status")
    data["images"] = [normalize_image(value, request.app.state.settings) for value in payload.images]
    data["location"] = payload.location or payload.address
    data["city"] = payload.city or data["location"].rsplit(",", 1)[-1].strip()
    if item:
        for key, value in data.items():
            setattr(item, key, value)
    else:
        item = Homestay(**data, host_id=user.id)
        db.add(item)
    db.commit()
    return homestay_out(db, item)


@router.post("/homestays", status_code=201)
def create_homestay(
    payload: schemas.HomestayIn,
    request: Request,
    user: User = Depends(get_host),
    db: Session = Depends(get_db),
):
    return save_homestay(payload, request, db, user)


@router.get("/homestays/{item_id}")
def get_homestay(item_id: int, user: User = Depends(get_host), db: Session = Depends(get_db)):
    return homestay_out(db, owned_homestay(db, item_id, user))


@router.put("/homestays/{item_id}")
def update_homestay(
    item_id: int,
    payload: schemas.HomestayIn,
    request: Request,
    user: User = Depends(get_host),
    db: Session = Depends(get_db),
):
    return save_homestay(payload, request, db, user, owned_homestay(db, item_id, user, lock=True))


@router.delete("/homestays/{item_id}", status_code=204)
def delete_homestay(item_id: int, user: User = Depends(get_host), db: Session = Depends(get_db)):
    item = owned_homestay(db, item_id, user, lock=True)
    if db.scalar(
        select(Booking.id).where(Booking.homestay_id == item_id, Booking.status.in_(ACTIVE)).limit(1)
    ):
        raise HTTPException(409, "Homestay còn đặt phòng đang hoạt động.")
    item.status = "deleted"
    db.commit()
    return Response(status_code=204)


@router.get("/rooms")
def rooms(
    homestay_id: int | None = None,
    user: User = Depends(get_host),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=100),
):
    query = (
        select(Room)
        .join(Homestay)
        .where(Homestay.host_id == user.id, Homestay.status != "deleted", Room.status != "deleted")
    )
    if homestay_id:
        owned_homestay(db, homestay_id, user)
        query = query.where(Room.homestay_id == homestay_id)
    rows = list(db.scalars(query.order_by(Room.id).offset((page - 1) * page_size).limit(page_size)))
    blocks = {}
    for block in db.scalars(select(RoomBlock).where(RoomBlock.room_id.in_([r.id for r in rows]))):
        blocks.setdefault(block.room_id, []).append(block)
    return [room_out(db, r, blocks.get(r.id, [])) for r in rows]


def save_room(payload, request, db, user, room=None):
    owned_homestay(db, payload.homestay_id, user, lock=True)
    if room and room.homestay_id != payload.homestay_id:
        raise HTTPException(422, "Không thể chuyển phòng sang homestay khác.")
    if room:
        if db.scalar(
            select(RoomBlock.id)
            .where(RoomBlock.room_id == room.id, RoomBlock.unit > payload.inventory)
            .limit(1)
        ):
            raise HTTPException(409, "Inventory cannot remove an explicitly blocked unit.")
        if payload.capacity < room.capacity and db.scalar(
            select(Booking.id)
            .join(BookingLine)
            .where(BookingLine.room_id == room.id, Booking.status.in_(ACTIVE))
            .limit(1)
        ):
            raise HTTPException(409, "Không thể giảm sức chứa phòng có đặt phòng đang hoạt động.")
        occupied_unit = (
            db.scalar(
                select(func.max(RoomNight.unit)).where(
                    RoomNight.room_id == room.id, RoomNight.night >= business_today()
                )
            )
            or 0
        )
        if payload.inventory < occupied_unit:
            raise HTTPException(409, "Không thể giảm tồn phòng đang được giữ/chặn.")
    data = payload.model_dump(exclude={"id", "blocked_dates"})
    if room and "status" not in payload.model_fields_set:
        data.pop("status")
    data["images"] = [normalize_image(value, request.app.state.settings) for value in payload.images]
    if room:
        for key, value in data.items():
            setattr(room, key, value)
    else:
        room = Room(**data, key="room-" + secrets.token_hex(8))
        db.add(room)
    db.flush()
    if payload.blocked_dates is not None:
        # Replacement is atomic. Existing bookings stay protected by RoomNight uniqueness.
        block_ids = select(RoomBlock.id).where(RoomBlock.room_id == room.id, RoomBlock.unit.is_(None))
        db.execute(delete(RoomNight).where(RoomNight.block_id.in_(block_ids)))
        db.execute(delete(RoomBlock).where(RoomBlock.room_id == room.id, RoomBlock.unit.is_(None)))
        for day in sorted(set(payload.blocked_dates)):
            add_block(db, room, day, day + timedelta(days=1), "Host blocked date", user)
    elif room:
        # Increasing inventory must also extend existing all-unit maintenance blocks.
        blocks = db.scalars(select(RoomBlock).where(RoomBlock.room_id == room.id)).all()
        for block in blocks:
            db.execute(delete(RoomNight).where(RoomNight.block_id == block.id))
            for day in nights(block.start_date, block.end_date):
                for unit in [block.unit] if block.unit is not None else range(1, room.inventory + 1):
                    db.add(RoomNight(room_id=room.id, unit=unit, night=day, block_id=block.id))
    db.commit()
    return room_out(db, room)


@router.post("/rooms", status_code=201)
def create_room(
    payload: schemas.RoomIn, request: Request, user: User = Depends(get_host), db: Session = Depends(get_db)
):
    return save_room(payload, request, db, user)


@router.get("/rooms/{room_id}")
def get_room(room_id: int, user: User = Depends(get_host), db: Session = Depends(get_db)):
    return room_out(db, owned_room(db, room_id, user))


@router.put("/rooms/{room_id}")
def update_room(
    room_id: int,
    payload: schemas.RoomIn,
    request: Request,
    user: User = Depends(get_host),
    db: Session = Depends(get_db),
):
    return save_room(payload, request, db, user, owned_room(db, room_id, user, lock=True))


@router.delete("/rooms/{room_id}", status_code=204)
def delete_room(room_id: int, user: User = Depends(get_host), db: Session = Depends(get_db)):
    room = owned_room(db, room_id, user, lock=True)
    if db.scalar(
        select(Booking.id)
        .join(BookingLine)
        .where(BookingLine.room_id == room_id, Booking.status.in_(ACTIVE))
        .limit(1)
    ):
        raise HTTPException(409, "Phòng còn đặt phòng đang hoạt động.")
    room.status = "deleted"
    db.commit()
    return Response(status_code=204)


def block_out(block):
    return {
        "unit": block.unit,
        "scope": "unit" if block.unit is not None else "all",
        "id": block.id,
        "roomId": str(block.room_id),
        "start_date": block.start_date.isoformat(),
        "end_date": block.end_date.isoformat(),
        "reason": block.reason,
    }


@router.get("/rooms/{room_id}/blocks")
def blocks(room_id: int, user: User = Depends(get_host), db: Session = Depends(get_db)):
    owned_room(db, room_id, user)
    return [
        block_out(block)
        for block in db.scalars(
            select(RoomBlock).where(RoomBlock.room_id == room_id).order_by(RoomBlock.start_date)
        )
    ]


@router.post("/rooms/{room_id}/blocks", status_code=201)
def block(
    room_id: int, payload: schemas.BlockIn, user: User = Depends(get_host), db: Session = Depends(get_db)
):
    room = owned_room(db, room_id, user, lock=True)
    block = add_block(db, room, payload.start_date, payload.end_date, payload.reason, user, unit=payload.unit)
    db.commit()
    return block_out(block)


@router.put("/rooms/{room_id}/blocks/{block_id}")
def update_block(
    room_id: int,
    block_id: int,
    payload: schemas.BlockIn,
    user: User = Depends(get_host),
    db: Session = Depends(get_db),
):
    room = owned_room(db, room_id, user, lock=True)
    block = db.scalar(select(RoomBlock).where(RoomBlock.id == block_id, RoomBlock.room_id == room_id))
    if not block:
        raise HTTPException(404, "Block not found.")
    db.execute(delete(RoomNight).where(RoomNight.block_id == block.id))
    db.flush()
    add_block(
        db,
        room,
        payload.start_date,
        payload.end_date,
        payload.reason,
        user,
        unit=payload.unit,
        existing=block,
    )
    db.commit()
    return block_out(block)


@router.delete("/rooms/{room_id}/blocks/{block_id}", status_code=204)
def unblock(room_id: int, block_id: int, user: User = Depends(get_host), db: Session = Depends(get_db)):
    owned_room(db, room_id, user, lock=True)
    block = db.scalar(select(RoomBlock).where(RoomBlock.id == block_id, RoomBlock.room_id == room_id))
    if not block:
        raise HTTPException(404, "Không tìm thấy lịch chặn.")
    db.execute(delete(RoomNight).where(RoomNight.block_id == block.id))
    db.delete(block)
    db.commit()
    return Response(status_code=204)


@router.get("/bookings")
def bookings(
    page: int | None = Query(1, ge=1, le=100000),
    page_size: int = Query(20, ge=1, le=100),
    status: schemas.BookingState | None = None,
    user: User = Depends(get_host),
    db: Session = Depends(get_db),
):
    query = (
        select(Booking)
        .join(Homestay)
        .where(Homestay.host_id == user.id)
        .order_by(Booking.created_at.desc(), Booking.id.desc())
    )
    if status:
        query = query.where(Booking.status == status)
    if page is not None:
        query = query.offset((page - 1) * page_size).limit(page_size)
    return booking_list_out(db, db.scalars(query), host=True)


def owned_host_booking(db, booking_id, user, lock=False):
    query = select(Booking).join(Homestay).where(Booking.id == booking_id, Homestay.host_id == user.id)
    booking = db.scalar(
        query.with_for_update(of=Booking).execution_options(populate_existing=True) if lock else query
    )
    if not booking:
        raise HTTPException(404, "Booking not found.")
    return booking


@router.get("/bookings/{booking_id}")
def booking_detail(booking_id: int, user: User = Depends(get_host), db: Session = Depends(get_db)):
    return booking_out(db, owned_host_booking(db, booking_id, user), host=True)


@router.patch("/bookings/{booking_id}/status")
def booking_status(
    booking_id: int, payload: schemas.StatusIn, user: User = Depends(get_host), db: Session = Depends(get_db)
):
    booking = owned_host_booking(db, booking_id, user, lock=True)
    return booking_out(db, change_status(db, booking, payload.status, user, payload.reason), host=True)


@router.get("/dashboard")
def dashboard(
    start: date | None = Query(None, alias="from"),
    end: date | None = Query(None, alias="to"),
    user: User = Depends(get_host),
    db: Session = Depends(get_db),
):
    from ..reporting import VALUE_STATES, booking_kpis, payment_kpis, utc_window
    from ..serializers import booking_list_out

    end = end or business_today()
    start = start or end - timedelta(days=29)
    if not 0 <= (end - start).days <= 365:
        raise HTTPException(422, "Invalid reporting period")
    all_kpi = booking_kpis(db, user.id)
    period = booking_kpis(db, user.id, start, end)
    stay_query = select(Homestay).where(Homestay.host_id == user.id, Homestay.status != "deleted")
    stay_counts = dict(
        db.execute(
            select(Homestay.status, func.count()).where(Homestay.host_id == user.id).group_by(Homestay.status)
        ).all()
    )
    room_query = (
        select(Room)
        .join(Homestay)
        .where(Homestay.host_id == user.id, Homestay.status != "deleted", Room.status != "deleted")
    )
    room_count, inventory = db.execute(
        select(func.count(Room.id), func.coalesce(func.sum(Room.inventory), 0))
        .join(Homestay)
        .where(Homestay.host_id == user.id, Homestay.status != "deleted", Room.status != "deleted")
    ).one()
    stays = list(db.scalars(stay_query.order_by(Homestay.id).limit(100)))
    room_rows = list(db.scalars(room_query.order_by(Room.id).limit(100)))
    block_map = {}
    for block in db.scalars(select(RoomBlock).where(RoomBlock.room_id.in_([r.id for r in room_rows]))):
        block_map.setdefault(block.room_id, []).append(block)
    recent = list(
        db.scalars(
            select(Booking)
            .join(Homestay)
            .where(Homestay.host_id == user.id)
            .order_by(Booking.created_at.desc(), Booking.id.desc())
            .limit(10)
        )
    )
    lower, upper = utc_window(start, end)
    local_day = (
        func.date(Booking.created_at, "+7 hours")
        if db.bind.dialect.name == "sqlite"
        else func.date(func.timezone("Asia/Ho_Chi_Minh", Booking.created_at))
    )
    daily = {
        str(day): (count, int(value or 0))
        for day, count, value in db.execute(
            select(
                local_day,
                func.count(),
                func.sum(case((Booking.status.in_(VALUE_STATES), Booking.total_price), else_=0)),
            )
            .join(Homestay)
            .where(Homestay.host_id == user.id, Booking.created_at >= lower, Booking.created_at < upper)
            .group_by(local_day)
        )
    }
    occupancy = []
    # Ledger unit-nights prevent line joins from multiplying bookings or occupancy.
    active = (
        select(Room.id)
        .join(Homestay)
        .where(Homestay.host_id == user.id, Room.status == "active", Homestay.status != "deleted")
    )
    projected = dict(
        db.execute(
            select(Booking.homestay_id, func.count(RoomNight.id))
            .join(RoomNight, RoomNight.booking_id == Booking.id)
            .where(
                RoomNight.room_id.in_(active),
                RoomNight.night >= start,
                RoomNight.night <= end,
                Booking.status.in_(VALUE_STATES),
            )
            .group_by(Booking.homestay_id)
        ).all()
    )
    actual = dict(
        db.execute(
            select(Booking.homestay_id, func.count(RoomNight.id))
            .join(RoomNight, RoomNight.booking_id == Booking.id)
            .where(
                RoomNight.room_id.in_(active),
                RoomNight.night >= start,
                RoomNight.night <= end,
                RoomNight.night < business_today(),
                Booking.status.in_(("checked_in", "completed")),
            )
            .group_by(Booking.homestay_id)
        ).all()
    )
    inv = dict(
        db.execute(
            select(Room.homestay_id, func.sum(Room.inventory))
            .where(Room.id.in_(active))
            .group_by(Room.homestay_id)
        ).all()
    )
    for stay in stays:
        units = int(inv.get(stay.id, 0))
        cap = units * ((end - start).days + 1)
        used = projected.get(stay.id, 0)
        occupancy.append(
            {
                "id": str(stay.id),
                "name": stay.name,
                "roomCount": units,
                "nights": used,
                "actualNights": actual.get(stay.id, 0),
                "capacity": cap,
                "occupancy": round(used / cap * 100, 2) if cap else 0,
            }
        )
    return {
        "homestays": [homestay_out(db, s) for s in stays],
        "rooms": [room_out(db, r, block_map.get(r.id, [])) for r in room_rows],
        "bookingCount": all_kpi["bookingCount"],
        "periodBookingCount": period["bookingCount"],
        "statusCounts": period["statusCounts"],
        "confirmedRevenue": period["confirmedRevenue"],
        "completedRevenue": period["completedRevenue"],
        "bookingValue": period["bookingValue"],
        "payments": payment_kpis(db, user.id, start, end),
        "recentBookings": booking_list_out(db, recent, host=True),
        "homestayCounts": stay_counts,
        "roomTypeCount": room_count,
        "inventoryCount": int(inventory),
        "from": start.isoformat(),
        "to": end.isoformat(),
        "occupancy": occupancy,
        "occupancySummary": {
            "nights": sum(projected.values()),
            "actualNights": sum(actual.values()),
            "capacity": sum(inv.values()) * ((end - start).days + 1),
            "occupancy": round(
                sum(projected.values()) / (sum(inv.values()) * ((end - start).days + 1)) * 100, 2
            )
            if sum(inv.values())
            else 0,
        },
        "series": [
            {
                "date": day.isoformat(),
                "bookings": daily.get(day.isoformat(), (0, 0))[0],
                "revenue": daily.get(day.isoformat(), (0, 0))[1],
                "bookingValue": daily.get(day.isoformat(), (0, 0))[1],
            }
            for day in nights(start, end + timedelta(days=1))
        ],
        "limits": {"homestays": 100, "rooms": 100, "recentBookings": 10},
        "definitions": {
            "revenue": "legacy booking value, NOT collected cash",
            "occupancy": "projected confirmed+checked_in+completed unit nights/current inventory; historical inventory unknown",
        },
    }
