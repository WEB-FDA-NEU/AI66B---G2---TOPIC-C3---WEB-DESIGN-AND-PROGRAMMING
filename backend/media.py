"""Only validated raster images; never trust Content-Type or a file extension."""

import base64
import binascii
import io
import re
import secrets
import warnings
from urllib.parse import urlsplit

from fastapi import HTTPException
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_IMAGE = 5 * 1024 * 1024


def save_image(raw, settings):
    if not raw or len(raw) > MAX_IMAGE:
        raise HTTPException(413, "Ảnh phải có dung lượng từ 1 byte đến 5MB.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as image:
                if image.format not in {"JPEG", "PNG", "WEBP"} or image.width * image.height > 16000000:
                    raise HTTPException(415, "Chỉ chấp nhận ảnh JPEG, PNG hoặc WebP hợp lệ, tối đa 16MP.")
                image.load()
                image = ImageOps.exif_transpose(image).convert("RGB")
                image.thumbnail((1920, 1920))
                output = io.BytesIO()
                image.save(output, format="JPEG", quality=88)
        settings.upload_dir.mkdir(parents=True, exist_ok=True)
        name = secrets.token_hex(20) + ".jpg"
        (settings.upload_dir / name).write_bytes(output.getvalue())
        return "/uploads/" + name
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ):
        raise HTTPException(415, "Nội dung ảnh không hợp lệ.")


def normalize_image(value, settings):
    if value == "img/placeholder.svg":
        return value
    if re.fullmatch(r"/uploads/[a-f0-9]{40}\.jpg", value):
        if not (settings.upload_dir / value.rsplit("/", 1)[1]).is_file():
            raise HTTPException(422, "Ảnh tải lên không tồn tại.")
        return value
    if value.startswith("data:"):
        match = re.fullmatch(r"data:image/(?:jpeg|png|webp);base64,([A-Za-z0-9+/=]+)", value)
        if not match or len(value) > MAX_IMAGE * 4 // 3 + 100:
            raise HTTPException(415, "Ảnh data URI không hợp lệ.")
        try:
            raw = base64.b64decode(match[1], validate=True)
        except binascii.Error:
            raise HTTPException(415, "Dữ liệu ảnh không hợp lệ.")
        return save_image(raw, settings)
    try:
        url = urlsplit(value)
        _ = url.port
    except ValueError:
        raise HTTPException(422, "Invalid image URL.") from None
    if (
        url.scheme not in {"https", "http"}
        or not url.hostname
        or url.username
        or url.password
        or len(value) > 2048
    ):
        raise HTTPException(422, "URL ảnh không hợp lệ.")
    # We never fetch remote URLs on the server (no SSRF).
    return value
