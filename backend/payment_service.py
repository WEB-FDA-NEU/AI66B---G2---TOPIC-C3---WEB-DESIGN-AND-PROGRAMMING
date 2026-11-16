"""Audited payment transitions. Simulation is admin and development/test only."""

import secrets

from fastapi import HTTPException
from sqlalchemy import select

from .models import Booking, Payment, PaymentEvent
from .serializers import iso


def record_event(db, payment, old_status, actor, source, refund_amount=0, note=""):
    db.add(
        PaymentEvent(
            payment_id=payment.id,
            old_status=old_status,
            new_status=payment.status,
            amount=payment.amount,
            refund_amount=refund_amount,
            changed_by=actor.id,
            source=source,
            note=note,
        )
    )


def payment_out(db, payment):
    events = db.scalars(
        select(PaymentEvent).where(PaymentEvent.payment_id == payment.id).order_by(PaymentEvent.id)
    )
    return {
        "id": payment.id,
        "amount": int(payment.amount),
        "method": payment.method,
        "status": payment.status,
        "transactionReference": payment.transaction_reference,
        "createdAt": iso(payment.created_at),
        "simulated": bool(payment.transaction_reference and payment.transaction_reference.startswith("SIM-")),
        "history": [
            {
                "oldStatus": e.old_status,
                "newStatus": e.new_status,
                "amount": int(e.amount),
                "refundAmount": int(e.refund_amount),
                "source": e.source,
                "note": e.note,
                "createdAt": iso(e.created_at),
            }
            for e in events
        ],
    }


def simulate(db, booking_id, action, actor, settings, note):
    if settings.environment not in {"development", "test"} or actor.role != "admin" or not actor.is_active:
        raise HTTPException(403, "Payment simulation is restricted to development/test admins.")
    # Same order as cancellation/rejection; simulation never changes RoomNight.
    booking = db.scalar(
        select(Booking)
        .where(Booking.id == booking_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if not booking:
        raise HTTPException(404, "Booking not found.")
    payment = db.scalar(
        select(Payment)
        .where(Payment.booking_id == booking.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if not payment:
        raise HTTPException(409, "Payment missing.")
    if payment.amount != booking.total_price or not 0 <= booking.refund_due <= payment.amount:
        raise HTTPException(409, "Payment amount is inconsistent with booking.")
    if action == "paid":
        if booking.status in {"cancelled", "rejected"}:
            raise HTTPException(409, "Booking cannot accept payment.")
        if payment.status == "paid":
            return payment_out(db, payment)
        if payment.status != "pending":
            raise HTTPException(409, "Invalid payment transition.")
    elif action == "refunded":
        if payment.status == "refunded":
            return payment_out(db, payment)
        if (
            payment.status != "refund_pending"
            or booking.status not in {"cancelled", "rejected"}
            or booking.refund_due <= 0
        ):
            raise HTTPException(409, "No eligible refund is pending.")
    else:
        raise HTTPException(422, "Invalid simulation action.")
    old = payment.status
    payment.status = action
    if action == "paid":
        payment.transaction_reference = "SIM-" + secrets.token_hex(16)
    record_event(
        db, payment, old, actor, "simulation", booking.refund_due if action == "refunded" else 0, note
    )
    db.commit()
    return payment_out(db, payment)
