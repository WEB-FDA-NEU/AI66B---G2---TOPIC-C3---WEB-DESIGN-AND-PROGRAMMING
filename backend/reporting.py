"""SQL reporting. Booking cohorts are not a cash-flow statement."""

from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import case, func, select

from .models import Booking, Homestay, Payment, User

STATES = ("pending", "confirmed", "checked_in", "completed", "cancelled", "rejected")
VALUE_STATES = ("confirmed", "checked_in", "completed")


def admin_period(db, start, end):
    """Aggregate the complete cohort; never derive charts from limited DTO projections."""
    lower, upper = utc_window(start, end)

    def daily(model):
        day = (
            func.date(model.created_at, "+7 hours")
            if db.bind.dialect.name == "sqlite"
            else func.date(func.timezone("Asia/Ho_Chi_Minh", model.created_at))
        )
        return {
            str(d): count
            for d, count in db.execute(
                select(day, func.count())
                .where(model.created_at >= lower, model.created_at < upper)
                .group_by(day)
            )
        }

    users, bookings = daily(User), daily(Booking)
    provinces = [
        {"name": name or "Khác", "bookings": count}
        for name, count in db.execute(
            select(Homestay.city, func.count(Booking.id))
            .join(Booking, Booking.homestay_id == Homestay.id)
            .where(Booking.created_at >= lower, Booking.created_at < upper)
            .group_by(Homestay.city)
            .order_by(func.count(Booking.id).desc(), Homestay.city)
        )
    ]
    return {
        "from": start.isoformat(),
        "to": end.isoformat(),
        "newUsers": sum(users.values()),
        "newBookings": sum(bookings.values()),
        "provinces": provinces,
        "series": [
            {
                "date": (start + timedelta(days=n)).isoformat(),
                "users": users.get((start + timedelta(days=n)).isoformat(), 0),
                "bookings": bookings.get((start + timedelta(days=n)).isoformat(), 0),
            }
            for n in range((end - start).days + 1)
        ],
    }


def utc_window(start, end):
    zone = ZoneInfo("Asia/Ho_Chi_Minh")
    return (
        datetime.combine(start, time.min, zone).astimezone(timezone.utc),
        datetime.combine(end + timedelta(days=1), time.min, zone).astimezone(timezone.utc),
    )


def booking_kpis(db, host_id=None, start=None, end=None):
    query = select(Booking.status, func.count(), func.sum(Booking.total_price)).join(Homestay)
    if host_id is not None:
        query = query.where(Homestay.host_id == host_id)
    if start:
        lower, upper = utc_window(start, end)
        query = query.where(Booking.created_at >= lower, Booking.created_at < upper)
    rows = list(db.execute(query.group_by(Booking.status)))
    counts = {s: 0 for s in STATES}
    values = {s: 0 for s in STATES}
    for status, count, value in rows:
        counts[status], values[status] = count, int(value or 0)
    return {
        "bookingCount": sum(counts.values()),
        "statusCounts": counts,
        "bookingValue": sum(values[s] for s in VALUE_STATES),
        "allBookingValue": sum(values.values()),
        "confirmedRevenue": sum(values[s] for s in VALUE_STATES),
        "completedRevenue": values["completed"],
        "valueByStatus": values,
    }


def payment_kpis(db, host_id=None, start=None, end=None):
    captured = Payment.status.in_(("paid", "refund_pending", "refunded"))
    simulated_payment = func.coalesce(Payment.transaction_reference.like("SIM-%"), False)
    query = (
        select(
            func.coalesce(func.sum(case((captured & ~simulated_payment, Payment.amount), else_=0)), 0),
            func.coalesce(
                func.sum(
                    case(
                        ((Payment.status == "refund_pending") & ~simulated_payment, Booking.refund_due),
                        else_=0,
                    )
                ),
                0,
            ),
            func.coalesce(
                func.sum(
                    case(((Payment.status == "refunded") & ~simulated_payment, Booking.refund_due), else_=0)
                ),
                0,
            ),
            func.coalesce(
                func.sum(case((captured & simulated_payment, Payment.amount), else_=0)),
                0,
            ),
            func.coalesce(
                func.sum(
                    case(
                        ((Payment.status == "refund_pending") & simulated_payment, Booking.refund_due),
                        else_=0,
                    )
                ),
                0,
            ),
            func.coalesce(
                func.sum(
                    case(((Payment.status == "refunded") & simulated_payment, Booking.refund_due), else_=0)
                ),
                0,
            ),
        )
        .select_from(Payment)
        .join(Booking)
        .join(Homestay)
    )
    if host_id is not None:
        query = query.where(Homestay.host_id == host_id)
    if start:
        lower, upper = utc_window(start, end)
        query = query.where(Booking.created_at >= lower, Booking.created_at < upper)
    gross, pending, refunded, simulated, sim_pending, sim_refunded = [int(x) for x in db.execute(query).one()]
    return {
        "grossCaptured": gross,
        "paidRevenue": gross - refunded,
        "refundPending": pending,
        "refunded": refunded,
        "platformRevenue": None,
        "simulatedCaptured": simulated,
        "simulatedRefundPending": sim_pending,
        "simulatedRefunded": sim_refunded,
        "simulatedNet": simulated - sim_refunded,
        "containsSimulation": bool(simulated),
        "basis": "current payment state of bookings created in period; not payment event cashflow",
    }
