from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile

from ..deps import get_current_user
from ..media import MAX_IMAGE, save_image
from ..models import User

router = APIRouter(prefix="/api", tags=["media"])


@router.post("/uploads", status_code=201)
async def upload(request: Request, file: UploadFile = File(...), user: User = Depends(get_current_user)):
    try:
        if file.content_type not in {"image/jpeg", "image/png", "image/webp"}:
            raise HTTPException(415, "Chỉ chấp nhận JPEG, PNG hoặc WebP.")
        raw = await file.read(MAX_IMAGE + 1)
        return {"url": save_image(raw, request.app.state.settings)}
    finally:
        await file.close()
