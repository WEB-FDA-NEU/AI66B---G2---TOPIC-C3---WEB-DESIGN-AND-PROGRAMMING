from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import schemas
from ..database import get_db
from ..deps import get_admin
from ..host_service import cancel_host_role
from ..models import (
    Booking,
    Homestay,
    HostApplication,
    HostApplicationHistory,
    HostCancellation,
    User,
    utcnow,
)
from ..serializers import application_out, homestay_out, iso, user_out

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.post("/bookings/{booking_id}/payment-simulation")
def payment_simulation(
    booking_id: int,
    payload: schemas.PaymentSimulationIn,
    request: Request,
    actor: User = Depends(get_admin),
    db: Session = Depends(get_db),
):
    from ..payment_service import simulate

    return simulate(db, booking_id, payload.action, actor, request.app.state.settings, payload.reason)


@router.get("/overview")
def overview(
    start: date | None = Query(None, alias="from"),
    end: date | None = Query(None, alias="to"),
    user: User = Depends(get_admin),
    db: Session = Depends(get_db),
):
    from ..booking_service import business_today
    from ..reporting import admin_period, booking_kpis, payment_kpis

    end = end or business_today()
    start = start or end - timedelta(days=29)
    if not 0 <= (end - start).days <= 365:
        raise HTTPException(422, "Invalid reporting period")

    roles = dict(db.execute(select(User.role, func.count()).group_by(User.role)).all())
    active = dict(db.execute(select(User.is_active, func.count()).group_by(User.is_active)).all())
    apps = dict(
        db.execute(select(HostApplication.status, func.count()).group_by(HostApplication.status)).all()
    )
    stays = dict(db.execute(select(Homestay.status, func.count()).group_by(Homestay.status)).all())
    return {
        "users": [
            {"id": u.id, "createdAt": iso(u.created_at), "role": u.role}
            for u in db.scalars(select(User).order_by(User.id).limit(100))
        ],
        "bookings": [
            {
                "id": b.id,
                "itemId": b.homestay_id,
                "createdAt": iso(b.created_at),
                "status": b.status,
                "totalPrice": int(b.total_price),
            }
            for b in db.scalars(select(Booking).order_by(Booking.id).limit(100))
        ],
        "homestays": [
            {"id": h.id, "title": h.name, "location": h.location}
            for h in db.scalars(select(Homestay).order_by(Homestay.id).limit(100))
        ],
        "kpis": {
            "users": sum(roles.values()),
            "roles": roles,
            "activeUsers": active.get(True, 0),
            "inactiveUsers": active.get(False, 0),
            "applications": apps,
            "homestays": stays,
            **booking_kpis(db),
            "payments": payment_kpis(db),
        },
        "projectionLimit": 100,
        "period": admin_period(db, start, end),
        "definitions": {"platformRevenue": "unknown; booking value is not profit"},
    }


@router.get("/hosts")
def hosts(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=100),
    user: User = Depends(get_admin),
    db: Session = Depends(get_db),
):
    from ..models import Room
    from ..serializers import public_homestays

    rows = list(
        db.scalars(
            select(User)
            .where(User.role == "host")
            .order_by(User.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    ids = [u.id for u in rows]
    stays = list(
        db.scalars(
            select(Homestay)
            .where(Homestay.host_id.in_(ids), Homestay.status != "deleted")
            .order_by(Homestay.id)
            .limit(1000)
        )
    )
    eligible = select(Room.id).where(Room.status == "active", Room.price_per_night > 0).subquery()
    views = public_homestays(db, stays, eligible)
    by_host = {}
    for stay, view in zip(stays, views):
        by_host.setdefault(stay.host_id, []).append(view)
    counts = dict(
        db.execute(
            select(Homestay.host_id, func.count(Booking.id))
            .join(Booking, Booking.homestay_id == Homestay.id)
            .where(Homestay.host_id.in_(ids))
            .group_by(Homestay.host_id)
        ).all()
    )
    values = dict(
        db.execute(
            select(Homestay.host_id, func.sum(Booking.total_price))
            .join(Booking, Booking.homestay_id == Homestay.id)
            .where(Homestay.host_id.in_(ids), Booking.status == "completed")
            .group_by(Homestay.host_id)
        ).all()
    )
    return [
        {
            **user_out(u),
            "homestays": by_host.get(u.id, []),
            "bookingCount": counts.get(u.id, 0),
            "revenue": int(values.get(u.id, 0)),
            "revenueBasis": "legacy completed booking value, not cash",
            "homestayProjectionLimit": 1000,
        }
        for u in rows
    ]


@router.get("/host-applications")
def applications(
    status: Literal["pending", "approved", "rejected"] | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=100),
    user: User = Depends(get_admin),
    db: Session = Depends(get_db),
):
    query = select(HostApplication)
    if status:
        query = query.where(HostApplication.status == status)
    rows = list(
        db.scalars(
            query.order_by(HostApplication.created_at.desc(), HostApplication.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    owners = {u.id: u for u in db.scalars(select(User).where(User.id.in_([a.user_id for a in rows])))}
    histories = {}
    for h in db.scalars(
        select(HostApplicationHistory)
        .where(HostApplicationHistory.application_id.in_([a.id for a in rows]))
        .order_by(HostApplicationHistory.id)
    ):
        histories.setdefault(h.application_id, []).append(h)
    return [application_out(db, a, owner=owners[a.user_id], history=histories.get(a.id, [])) for a in rows]


def decide_application(db, application_id, actor, status, reason=""):
    # Read only the immutable owner before taking locks; every flow locks User first.
    applicant_id = db.scalar(select(HostApplication.user_id).where(HostApplication.id == application_id))
    if applicant_id is None:
        raise HTTPException(404, "Application not found.")
    applicant = db.scalar(
        select(User)
        .where(User.id == applicant_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    application = db.scalar(
        select(HostApplication)
        .where(HostApplication.id == application_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if not application:
        raise HTTPException(404, "Không tìm thấy đơn đăng ký.")
    if application.status != "pending":
        raise HTTPException(409, "Đơn đã được xử lý.")
    if not applicant.is_active or applicant.role != "user":
        raise HTTPException(409, "Tài khoản không đủ điều kiện xét duyệt.")
    application.status = status
    application.reviewed_by = actor.id
    application.reviewed_at = utcnow()
    application.reject_reason = reason
    db.add(
        HostApplicationHistory(
            application_id=application.id,
            status=status,
            application_data=dict(application.application_data),
            reject_reason=reason,
            reviewed_by=actor.id,
            reviewed_at=application.reviewed_at,
        )
    )
    if status == "approved":
        applicant.role = "host"
        applicant.token_version += 1  # User must sign in again to obtain the changed privileges.
    db.commit()
    return application_out(db, application)


@router.post("/host-applications/{application_id}/approve")
def approve(application_id: int, user: User = Depends(get_admin), db: Session = Depends(get_db)):
    return decide_application(db, application_id, user, "approved")


@router.post("/host-applications/{application_id}/reject")
def reject(
    application_id: int,
    payload: schemas.ReasonIn,
    user: User = Depends(get_admin),
    db: Session = Depends(get_db),
):
    return decide_application(db, application_id, user, "rejected", payload.reason)


@router.get("/users")
def users(
    role: Literal["user", "host", "admin"] | None = None,
    is_active: bool | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=100),
    sort: Literal["id", "newest", "email"] = "id",
    user: User = Depends(get_admin),
    db: Session = Depends(get_db),
):
    query = select(User)
    if role:
        query = query.where(User.role == role)
    if is_active is not None:
        query = query.where(User.is_active == is_active)
    order = {"id": User.id, "newest": User.created_at.desc(), "email": User.email}[sort]
    return [
        {**user_out(u), "is_active": u.is_active}
        for u in db.scalars(query.order_by(order, User.id).offset((page - 1) * page_size).limit(page_size))
    ]


@router.get("/host-cancellations")
def host_cancellations(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=100),
    user: User = Depends(get_admin),
    db: Session = Depends(get_db),
):
    rows = db.execute(
        select(HostCancellation, User)
        .join(User, User.id == HostCancellation.host_id)
        .where(HostCancellation.source == "host")
        .order_by(HostCancellation.created_at.desc(), HostCancellation.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return [
        {
            "id": cancellation.id,
            "host": user_out(host),
            "reason": cancellation.reason,
            "createdAt": iso(cancellation.created_at),
        }
        for cancellation, host in rows
    ]


@router.post("/users/{user_id}/cancel-host", status_code=204)
def cancel_host_by_admin(
    user_id: int,
    actor: User = Depends(get_admin),
    db: Session = Depends(get_db),
):
    host = db.scalar(
        select(User).where(User.id == user_id).with_for_update().execution_options(populate_existing=True)
    )
    if not host:
        raise HTTPException(404, "Không tìm thấy người dùng.")
    cancel_host_role(db, host, actor, "admin")
    return Response(status_code=204)


@router.patch("/users/{user_id}")
def update_user(
    user_id: int,
    payload: schemas.AdminUserIn,
    actor: User = Depends(get_admin),
    db: Session = Depends(get_db),
):
    # Consistent lock order protects the last-admin invariant with multiple workers.
    db.scalars(select(User).where(User.role == "admin").order_by(User.id).with_for_update()).all()
    user = db.scalar(
        select(User).where(User.id == user_id).with_for_update().execution_options(populate_existing=True)
    )
    if not user:
        raise HTTPException(404, "Không tìm thấy người dùng.")
    changes = payload.model_dump(exclude_none=True)
    if user.id == actor.id and (
        changes.get("is_active") is False or ("role" in changes and changes["role"] != user.role)
    ):
        raise HTTPException(409, "Không thể tự khóa hoặc hạ quyền tài khoản quản trị đang dùng.")
    if user.role == "admin" and (
        changes.get("is_active") is False or changes.get("role", "admin") != "admin"
    ):
        count = db.scalar(
            select(func.count()).select_from(User).where(User.role == "admin", User.is_active.is_(True))
        )
        if user.is_active and count <= 1:
            raise HTTPException(409, "Không thể loại bỏ quản trị viên hoạt động cuối cùng.")
    if "role" in changes and changes["role"] != user.role:
        if db.scalar(
            select(Homestay.id).where(Homestay.host_id == user.id, Homestay.status != "deleted").limit(1)
        ):
            raise HTTPException(409, "Cần xử lý homestay của host trước khi đổi vai trò.")
    if any(getattr(user, key) != value for key, value in changes.items()):
        for key, value in changes.items():
            setattr(user, key, value)
        user.token_version += 1
    db.commit()
    return {**user_out(user), "is_active": user.is_active}


@router.get("/homestays")
def homestays(
    status: Literal["active", "inactive", "deleted"] | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=100),
    user: User = Depends(get_admin),
    db: Session = Depends(get_db),
):
    query = select(Homestay)
    if status:
        query = query.where(Homestay.status == status)
    return [
        homestay_out(db, stay)
        for stay in db.scalars(query.order_by(Homestay.id).offset((page - 1) * page_size).limit(page_size))
    ]


@router.patch("/homestays/{item_id}/status")
def moderate(
    item_id: int,
    payload: schemas.ModerationIn,
    user: User = Depends(get_admin),
    db: Session = Depends(get_db),
):
    stay = db.scalar(
        select(Homestay).where(Homestay.id == item_id, Homestay.status != "deleted").with_for_update()
    )
    if not stay:
        raise HTTPException(404, "Không tìm thấy homestay.")
    stay.status = payload.status
    stay.moderation_reason = payload.reason
    db.commit()
    return homestay_out(db, stay)
