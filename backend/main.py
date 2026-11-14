"""App factory. Startup never creates, drops or migrates tables."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError
from starlette.exceptions import HTTPException as StarletteHTTPException

from .config import Settings
from .database import make_engine, make_session_factory
from .routers import admin, auth, bookings, host, items, uploads


class BodyLimitMiddleware:
    def __init__(self, app, max_bytes):
        self.app, self.max_bytes = app, max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        size = 0
        chunks = []
        # Bound both declared and chunked bodies before FastAPI parses JSON/multipart.
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > self.max_bytes:
                response = JSONResponse(
                    {"detail": "Nội dung yêu cầu quá lớn.", "code": "body_too_large"}, status_code=413
                )
                return await response(scope, receive, send)
            chunks.append(chunk)
            if not message.get("more_body", False):
                break
        replayed = False

        async def replay():
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": b"".join(chunks), "more_body": False}
            return await receive()

        async def headers(message):
            if message["type"] == "http.response.start":
                extra = [(b"x-content-type-options", b"nosniff"), (b"referrer-policy", b"same-origin")]
                if scope["path"].startswith("/api/"):
                    extra.append((b"cache-control", b"no-store"))
                message["headers"] = list(message.get("headers", [])) + extra
            await send(message)

        return await self.app(scope, replay, headers)


def create_app(settings=None, engine=None):
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(application):
        try:
            yield
        finally:
            if engine is None:
                application.state.engine.dispose()

    app = FastAPI(
        title="LuxStay API",
        version="2.0.0",
        description="Homestay catalog, revocable authentication and transactional bookings.",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.engine = engine or make_engine(settings.database_url)
    app.state.session_factory = make_session_factory(app.state.engine)
    app.add_middleware(BodyLimitMiddleware, max_bytes=settings.max_body_bytes)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
        expose_headers=["Retry-After"],
    )

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request, error):
        return JSONResponse(
            {"detail": error.detail, "code": f"http_{error.status_code}"},
            status_code=error.status_code,
            headers=error.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, error):
        errors = [
            {"loc": list(item["loc"]), "type": item["type"], "msg": item["msg"]} for item in error.errors()
        ]
        return JSONResponse(
            {"detail": "Dữ liệu yêu cầu không hợp lệ.", "code": "validation_error", "errors": errors},
            status_code=422,
        )

    @app.exception_handler(IntegrityError)
    async def conflict(request, error):
        return JSONResponse(
            {"detail": "Dữ liệu xung đột. Vui lòng tải lại và thử lại.", "code": "conflict"}, status_code=409
        )

    @app.exception_handler(OperationalError)
    async def database_unavailable(request, error):
        return JSONResponse(
            {"detail": "Dịch vụ dữ liệu chưa sẵn sàng.", "code": "database_unavailable"}, status_code=503
        )

    @app.exception_handler(Exception)
    async def unexpected(request, error):
        # Do not serialize exception repr/SQL parameters/request bodies into responses or logs.
        return JSONResponse(
            {"detail": "Có lỗi máy chủ. Vui lòng thử lại sau.", "code": "internal_error"}, status_code=500
        )

    for router in [auth.router, items.router, bookings.router, host.router, admin.router, uploads.router]:
        app.include_router(router)

    @app.get("/api/health", tags=["ops"])
    def health():
        return {"status": "ok"}

    @app.get("/api/ready", tags=["ops"])
    def ready():
        try:
            with app.state.engine.connect() as connection:
                revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
                if revision != "0005_pay_events":
                    raise HTTPException(503, "Database cần được nâng cấp migration.")
                connection.execute(text("SELECT id FROM users LIMIT 1"))
        except OperationalError:
            raise HTTPException(503, "Database chưa sẵn sàng hoặc chưa migrate.")
        return {"status": "ready", "revision": revision}

    @app.api_route(
        "/api/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], include_in_schema=False
    )
    def missing_api(path: str):
        raise HTTPException(404, "API không tồn tại.")

    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")
    frontend = Path(__file__).resolve().parents[1] / "frontend"
    if settings.serve_frontend:
        app.mount("/", StaticFiles(directory=frontend, html=True), name="frontend")
    return app


app = create_app()
