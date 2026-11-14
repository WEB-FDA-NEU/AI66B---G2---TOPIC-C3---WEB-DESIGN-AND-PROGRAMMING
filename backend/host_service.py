from fastapi import HTTPException
from sqlalchemy import select

from .booking_service import ACTIVE
from .models import Booking, Homestay, HostCancellation, User


def cancel_host_role(db, host: User, actor: User, source: str, reason: str = ""):
    if host.role != "host":
        raise HTTPException(409, "Tài khoản này hiện không có quyền Host.")

    stays = list(db.scalars(select(Homestay).where(Homestay.host_id == host.id).with_for_update()))
    stay_ids = [stay.id for stay in stays]
    if stay_ids and db.scalar(
        select(Booking.id).where(Booking.homestay_id.in_(stay_ids), Booking.status.in_(ACTIVE)).limit(1)
    ):
        raise HTTPException(
            409,
            "Không thể hủy quyền Host khi homestay còn booking đang chờ, đã xác nhận hoặc đang lưu trú.",
        )

    for stay in stays:
        if stay.status == "active":
            stay.status = "inactive"
    host.role = "user"
    host.token_version += 1
    db.add(
        HostCancellation(
            host_id=host.id,
            actor_id=actor.id,
            source=source,
            reason=reason,
        )
    )
    db.commit()
