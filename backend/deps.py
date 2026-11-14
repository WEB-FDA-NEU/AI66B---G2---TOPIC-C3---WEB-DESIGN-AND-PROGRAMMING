from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .database import get_db
from .models import AuthSession, Homestay, Room, User, utcnow
from .security import decode_token, session_id

bearer = HTTPBearer(auto_error=False)


def get_current_user(
    request: Request,
    cred: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
):
    if not cred or cred.scheme.lower() != "bearer":
        raise HTTPException(401, "Bạn cần đăng nhập.", headers={"WWW-Authenticate": "Bearer"})
    claims = decode_token(cred.credentials, request.app.state.settings)
    if claims:
        user = db.get(User, int(claims["sub"]))
        session = db.get(AuthSession, session_id(claims["jti"]))
        if (
            user
            and user.is_active
            and user.token_version == claims["ver"]
            and session
            and session.user_id == user.id
            and not session.revoked
            and session.expires_at > utcnow()
        ):
            request.state.auth_session = session
            return user
    raise HTTPException(
        401, "Phiên đăng nhập không hợp lệ hoặc đã hết hạn.", headers={"WWW-Authenticate": "Bearer"}
    )


def get_host(user: User = Depends(get_current_user)):
    if user.role != "host":
        raise HTTPException(403, "Chỉ host được phép truy cập.")
    return user


def get_admin(user: User = Depends(get_current_user)):
    if user.role != "admin":
        raise HTTPException(403, "Chỉ quản trị viên được phép truy cập.")
    return user


def owned_homestay(db, homestay_id, user, lock=False):
    from sqlalchemy import select

    query = select(Homestay).where(
        Homestay.id == homestay_id, Homestay.host_id == user.id, Homestay.status != "deleted"
    )
    item = db.scalar(query.with_for_update().execution_options(populate_existing=True) if lock else query)
    if item is None:
        raise HTTPException(404, "Không tìm thấy homestay.")
    return item


def owned_room(db, room_id, user, lock=False):
    from sqlalchemy import select

    query = (
        select(Room)
        .join(Homestay)
        .where(
            Room.id == room_id,
            Homestay.host_id == user.id,
            Homestay.status != "deleted",
            Room.status != "deleted",
        )
    )
    if lock:
        homestay_id = db.scalar(query.with_only_columns(Room.homestay_id))
        if homestay_id is None:
            raise HTTPException(404, "Không tìm thấy phòng.")
        # Match booking allocation lock order: homestay first, then room.
        owned_homestay(db, homestay_id, user, lock=True)
    item = db.scalar(
        query.with_for_update(of=Room).execution_options(populate_existing=True) if lock else query
    )
    if item is None:
        raise HTTPException(404, "Không tìm thấy phòng.")
    return item
