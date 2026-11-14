from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import schemas
from ..booking_service import calculate_quote, change_status, create_booking
from ..database import get_db
from ..deps import get_current_user
from ..models import Booking, Payment, User
from ..serializers import booking_list_out, booking_out

router = APIRouter(prefix="/api", tags=["bookings"])


@router.post("/bookings/quote")
def quote(payload: schemas.QuoteIn, db: Session = Depends(get_db)):
    return calculate_quote(db, payload)[2]


@router.post("/me/bookings", status_code=201)
def book(
    payload: schemas.BookingIn,
    response: Response,
    idempotency_key: Annotated[str | None, Header(max_length=128, min_length=1)] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    booking, created = create_booking(db, payload, user, idempotency_key)
    if not created:
        response.status_code = 200
    return booking_out(db, booking)


@router.get("/me/bookings")
def my_bookings(
    page: int | None = Query(1, ge=1, le=100000),
    page_size: int = Query(20, ge=1, le=100),
    status: schemas.BookingState | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = select(Booking).where(Booking.customer_id == user.id)
    if status:
        query = query.where(Booking.status == status)
    query = query.order_by(Booking.created_at.desc(), Booking.id.desc())
    if page is not None:
        query = query.offset((page - 1) * page_size).limit(page_size)
    return booking_list_out(db, db.scalars(query))


def owned_booking(db, booking_id, user, lock=False):
    query = select(Booking).where(Booking.id == booking_id, Booking.customer_id == user.id)
    booking = db.scalar(query.with_for_update().execution_options(populate_existing=True) if lock else query)
    if not booking:
        raise HTTPException(404, "Không tìm thấy đặt phòng.")
    return booking


@router.get("/me/bookings/{booking_id}")
def detail(booking_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return booking_out(db, owned_booking(db, booking_id, user))


@router.post("/me/bookings/{booking_id}/cancel")
def cancel(booking_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    booking = owned_booking(db, booking_id, user, lock=True)
    return booking_out(db, change_status(db, booking, "cancelled", user))


@router.get("/me/bookings/{booking_id}/payments")
def payments(booking_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    owned_booking(db, booking_id, user)
    from ..payment_service import payment_out

    return [payment_out(db, p) for p in db.scalars(select(Payment).where(Payment.booking_id == booking_id))]
