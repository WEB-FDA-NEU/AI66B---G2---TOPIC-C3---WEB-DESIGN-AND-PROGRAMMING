FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_ENV=production \
    FRONTEND_MODE=shared \
    SERVE_FRONTEND=true \
    UPLOAD_DIR=/var/data/uploads

WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN python -m pip install --no-cache-dir -r backend/requirements.txt

COPY backend backend
COPY frontend frontend

EXPOSE 8000
# Migrations and first-admin bootstrap are explicit deployment/operator steps.
CMD ["sh", "-c", "exec python -m uvicorn backend.main:app --host 0.0.0.0 --port \"${PORT:-8000}\" --no-access-log --proxy-headers --forwarded-allow-ips \"${FORWARDED_ALLOW_IPS:-127.0.0.1}\""]
