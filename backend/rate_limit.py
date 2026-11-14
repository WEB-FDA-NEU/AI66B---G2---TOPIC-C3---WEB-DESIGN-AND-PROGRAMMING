"""Persistent fixed-window auth limits shared by workers; never store raw email/token."""

import hashlib
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from .models import RateLimitBucket, utcnow


def check_auth_limit(request, db, identity=""):
    settings = request.app.state.settings
    now = utcnow()
    window = settings.auth_rate_window
    bucket_number = int(now.timestamp()) // window
    client = request.client.host if request.client else "unknown"
    # Ignore untrusted X-Forwarded-For. Configure trusted proxy forwarding in the ASGI server.
    keys = (
        [
            (f"ip:{client}", settings.auth_rate_limit * 5),
            (f"account:{identity.lower()}", settings.auth_rate_limit),
        ]
        if identity
        else [(f"ip:{client}", settings.auth_rate_limit)]
    )
    insert = sqlite_insert if db.bind.dialect.name == "sqlite" else pg_insert
    db.execute(delete(RateLimitBucket).where(RateLimitBucket.expires_at < now))
    blocked = False
    for key, limit in keys:
        digest = hashlib.sha256(f"{bucket_number}:{key}".encode()).hexdigest()
        stmt = insert(RateLimitBucket).values(id=digest, count=1, expires_at=now + timedelta(seconds=window))
        stmt = stmt.on_conflict_do_update(
            index_elements=[RateLimitBucket.id], set_={"count": RateLimitBucket.count + 1}
        )
        db.execute(stmt)
        count = db.scalar(select(RateLimitBucket.count).where(RateLimitBucket.id == digest))
        blocked |= count > limit
    db.commit()  # Invalid credentials must still consume rate limit budget.
    if blocked:
        retry = window - int(now.timestamp()) % window
        raise HTTPException(
            429, "Quá nhiều yêu cầu. Vui lòng thử lại sau.", headers={"Retry-After": str(retry)}
        )
