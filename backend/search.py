"""Tìm kiếm không phân biệt hoa/thường và dấu tiếng Việt cho các danh sách host/admin.

SQL ILIKE không bỏ dấu được nếu không cài extension (unaccent), nên ta lấy các cột chữ
cần tìm (nhẹ, chỉ id + vài cột text), lọc trong Python rồi mới phân trang.
Mỗi từ trong ô tìm kiếm phải xuất hiện ở đâu đó trong các trường: "ha dalat" khớp
"Nguyễn Thu Hà — Đà Lạt Pine Cabin".
"""

import unicodedata

MAX_QUERY_LENGTH = 100


def fold(value) -> str:
    text = unicodedata.normalize("NFD", str(value or "")).replace("đ", "d").replace("Đ", "D")
    return "".join(ch for ch in text if not unicodedata.combining(ch)).casefold()


def tokens(query: str | None) -> list[str]:
    return fold((query or "")[:MAX_QUERY_LENGTH]).split()


def matches(needles: list[str], *fields) -> bool:
    haystack = fold(" ".join(str(f or "") for f in fields))
    return all(token in haystack for token in needles)


def page_slice(ids: list, page: int, page_size: int) -> list:
    start = (page - 1) * page_size
    return ids[start : start + page_size]
