from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import schemas
from ..database import get_db
from ..deps import get_current_user
from ..media import normalize_image
from ..models import HostApplication, User, utcnow
from ..rate_limit import check_auth_limit
from ..security import DUMMY_HASH, hash_password, issue_token, verify_password
from ..serializers import application_out, user_out

router = APIRouter(prefix="/api", tags=["accounts"])


def session_response(db, user, settings):
    token = issue_token(db, user, settings)
    db.commit()
    return {"access_token": token, "token_type": "bearer", "user": user_out(user)}


@router.post("/auth/register", response_model=schemas.TokenOut, status_code=201)
def register(payload: schemas.RegisterIn, request: Request, db: Session = Depends(get_db)):
    check_auth_limit(request, db, str(payload.email))
    if db.scalar(select(User.id).where(User.email == str(payload.email))):
        raise HTTPException(409, "Email đã được đăng ký.")
    avatar = (
        normalize_image(payload.avatar, request.app.state.settings)
        if payload.avatar
        else "img/placeholder.svg"
    )
    user = User(
        email=str(payload.email),
        display_name=payload.display_name,
        phone=payload.phone,
        password_hash=hash_password(payload.password.get_secret_value()),
        role="user",
        avatar=avatar,
    )
    db.add(user)
    db.flush()
    if payload.role == "host":
        db.add(
            HostApplication(
                user_id=user.id, application_data={"display_name": user.display_name, "phone": user.phone}
            )
        )
    return session_response(db, user, request.app.state.settings)


@router.post("/auth/login", response_model=schemas.TokenOut)
def login(payload: schemas.LoginIn, request: Request, db: Session = Depends(get_db)):
    check_auth_limit(request, db, str(payload.email))
    user = db.scalar(select(User).where(User.email == str(payload.email)).with_for_update())
    correct = verify_password(payload.password.get_secret_value(), user.password_hash if user else DUMMY_HASH)
    if not user or not correct or not user.is_active:
        raise HTTPException(401, "Email hoặc mật khẩu không đúng.", headers={"WWW-Authenticate": "Bearer"})
    if not user.password_hash.startswith("$argon2id$"):
        user.password_hash = hash_password(payload.password.get_secret_value())
    return session_response(db, user, request.app.state.settings)


@router.get("/me", response_model=schemas.UserOut)
@router.get("/me/profile", response_model=schemas.UserOut)
def me(user: User = Depends(get_current_user)):
    return user_out(user)


@router.put("/me/profile", response_model=schemas.UserOut)
def update_profile(
    payload: schemas.ProfileIn,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = db.scalar(
        select(User).where(User.id == user.id).with_for_update().execution_options(populate_existing=True)
    )
    if db.scalar(select(User.id).where(User.email == str(payload.email), User.id != user.id)):
        raise HTTPException(409, "Email đã được đăng ký.")
    user.display_name, user.email, user.phone = payload.display_name, str(payload.email), payload.phone
    if payload.avatar is not None:
        user.avatar = normalize_image(payload.avatar, request.app.state.settings)
    db.commit()
    return user_out(user)


@router.patch("/me/profile", response_model=schemas.UserOut)
def patch_profile(
    payload: schemas.ProfilePatch,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = db.scalar(
        select(User).where(User.id == user.id).with_for_update().execution_options(populate_existing=True)
    )
    values = {
        "display_name": user.display_name,
        "email": user.email,
        "phone": user.phone,
    }
    values.update(payload.model_dump(exclude_unset=True))
    return update_profile(schemas.ProfileIn.model_validate(values), request, user, db)


@router.post("/me/password", status_code=204)
def change_password(
    payload: schemas.PasswordIn,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    check_auth_limit(request, db, f"password:{user.id}")
    user = db.scalar(
        select(User).where(User.id == user.id).with_for_update().execution_options(populate_existing=True)
    )
    current, new = payload.current_password.get_secret_value(), payload.new_password.get_secret_value()
    if not verify_password(current, user.password_hash):
        raise HTTPException(400, "Mật khẩu hiện tại không đúng.")
    if current == new:
        raise HTTPException(422, "Mật khẩu mới phải khác mật khẩu hiện tại.")
    user.password_hash = hash_password(new)
    user.token_version += 1
    user.updated_at = utcnow()
    db.commit()
    return Response(status_code=204)


@router.post("/auth/logout", status_code=204)
def logout(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    request.state.auth_session.revoked = True
    db.commit()
    return Response(status_code=204)


@router.post("/host/apply", status_code=201)
def apply_host(
    payload: schemas.ApplicationIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    user = db.scalar(
        select(User).where(User.id == user.id).with_for_update().execution_options(populate_existing=True)
    )
    if not user.is_active:
        raise HTTPException(403, "Inactive account.")
    application = db.scalar(
        select(HostApplication)
        .where(HostApplication.user_id == user.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if application and application.status != "rejected":
        raise HTTPException(409, "Bạn đã có đơn đăng ký host.")
    if user.role != "user":
        raise HTTPException(403, "Chỉ khách hàng có thể gửi đơn đăng ký host.")
    if application:
        application.status = "pending"
        application.reject_reason = ""
        application.reviewed_by = None
        application.reviewed_at = None
        application.application_data = payload.application_data
    else:
        application = HostApplication(user_id=user.id, application_data=payload.application_data)
        db.add(application)
    db.commit()
    return application_out(db, application)


@router.get("/me/host-application")
def my_application(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    application = db.scalar(select(HostApplication).where(HostApplication.user_id == user.id))
    if not application:
        raise HTTPException(404, "Bạn chưa gửi đơn đăng ký host.")
    return application_out(db, application)
