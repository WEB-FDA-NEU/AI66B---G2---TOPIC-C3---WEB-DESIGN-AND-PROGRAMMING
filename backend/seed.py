"""Development-only, idempotent catalog seed; never imports fabricated dashboard bookings.

Run from root: python -m backend.seed (password requested without echo).
Migrations must already have been applied. Existing non-seed data is never overwritten.
"""

import getpass
import json
import os
from pathlib import Path

from sqlalchemy import func, select, text

from .config import Settings
from .database import make_engine, make_session_factory
from .models import Homestay, Room, User
from .security import hash_password


def seed_database(db, password, environment="development"):
    if environment not in {"development", "test"}:
        raise RuntimeError("Seeding is forbidden outside development/test")
    if db.scalar(select(func.count()).select_from(Homestay)):
        return {"seeded": False, "reason": "Catalog already exists; no data changed"}
    if db.scalar(select(func.count()).select_from(User)):
        raise RuntimeError(
            "Existing users found. Refusing to modify an existing database; use a separate development database"
        )
    root = Path(__file__).resolve().parents[1] / "frontend" / "mock"

    def read(name, key):
        return json.loads((root / name).read_text(encoding="utf-8"))[key]

    users = read("users.json", "users")
    source_homestays = read("host-homestays.json", "homestays")
    source_rooms = read("host-rooms.json", "rooms")
    items = {item["id"]: item for item in read("items.json", "items")}
    # A distinct salted Argon2 hash per seed account; password never printed or written as plaintext.
    user_ids = {}
    for source in users:
        user = User(
            email=source["email"].strip().lower(),
            display_name=source["display_name"],
            phone=source.get("phone", ""),
            role=source["role"],
            avatar="img/placeholder.svg",
            password_hash=hash_password(password),
        )
        db.add(user)
        db.flush()
        user_ids[source["id"]] = user.id
    first_host = user_ids[next(user["id"] for user in users if user["role"] == "host")]
    hosts = {}
    for i, legacy_id in enumerate(sorted({stay["hostId"] for stay in source_homestays})):
        if i == 0:
            hosts[legacy_id] = first_host
        else:
            user = User(
                email=f"{legacy_id}@seed.luxstay.example.com",
                display_name=f"Host development {i + 1}",
                phone="",
                role="host",
                password_hash=hash_password(password),
            )
            db.add(user)
            db.flush()
            hosts[legacy_id] = user.id
    stays = {}
    allocated_ids = set()
    reserved_ids = set(items) | {
        stay["itemId"] for stay in source_homestays if stay.get("itemId") is not None
    }
    next_id = max(reserved_ids, default=0) + 1
    for source in source_homestays:
        item_id = source.get("itemId")
        if item_id is None:
            matches = [item["id"] for item in items.values() if item["title"] == source["name"]]
            item_id = matches[0] if len(matches) == 1 else next_id
            if item_id == next_id:
                next_id += 1
        if item_id in allocated_ids:
            raise RuntimeError("Duplicate homestay identity in seed source; no data committed")
        allocated_ids.add(item_id)
        item = items.get(item_id, {})
        stay = Homestay(
            id=item_id,
            host_id=hosts[source["hostId"]],
            name=source["name"],
            address=source["address"],
            location=item.get("location", source["address"]),
            city=item.get("location", source["address"]).rsplit(",", 1)[-1].strip(),
            description=source.get("description", ""),
            amenities=source.get("amenities", []),
            images=source.get("images", []),
            room_type=item.get("room_type", "Phòng riêng"),
            status="active" if source["status"] == "active" else "inactive",
        )
        db.add(stay)
        stays[source["id"]] = stay.id
    db.flush()
    for source in source_rooms:
        room = Room(
            homestay_id=stays[source["homestayId"]],
            key=source.get("itemRoomId", source["id"]),
            name=source["name"],
            description=source.get("description", ""),
            capacity=source["capacity"],
            price_per_night=source["pricePerNight"],
            inventory=1,
            images=source.get("images", []),
        )
        db.add(room)
        db.flush()
        from datetime import date, timedelta

        from .booking_service import add_block

        actor = db.get(
            User,
            next(
                stay.host_id for stay in db.scalars(select(Homestay).where(Homestay.id == room.homestay_id))
            ),
        )
        for value in sorted(set(source.get("blockedDates", []))):
            day = date.fromisoformat(value)
            add_block(db, room, day, day + timedelta(days=1), "Development seed block", actor)
    if db.bind.dialect.name == "postgresql":
        db.execute(
            text("SELECT setval(pg_get_serial_sequence('homestays', 'id'), (SELECT MAX(id) FROM homestays))")
        )
    # No mock reviews without eligible bookings, no synthesized revenue or fake payment confirmations.
    db.commit()
    return {
        "seeded": True,
        "users": len(users) + len(hosts) - 1,
        "homestays": len(stays),
        "rooms": len(source_rooms),
    }


def main():
    settings = Settings.from_env()
    if settings.environment != "development":
        raise RuntimeError("CLI seed is development-only")
    password = os.getenv("SEED_PASSWORD") or getpass.getpass(
        "Development account password (8-128 characters, hidden): "
    )
    engine = make_engine(settings.database_url)
    try:
        with make_session_factory(engine)() as db:
            if db.execute(text("SELECT version_num FROM alembic_version")).scalar_one() != "0005_pay_events":
                raise RuntimeError("Run alembic upgrade head before seeding")
            print(seed_database(db, password, settings.environment))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
