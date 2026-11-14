"""Bounded key retention; schedule daily after backing up the database.

Only request deduplication keys expire. Booking snapshots/history never expire here.
The CLI defaults to a dry run and never prints keys, bodies or credentials.
"""

import argparse
from datetime import timedelta

from sqlalchemy import func, select, update

from .models import Booking, utcnow

KEY_RETENTION = timedelta(days=30)


def expire_keys(db, *, apply=False):
    query = (Booking.idempotency_key.is_not(None), Booking.created_at < utcnow() - KEY_RETENTION)
    if not apply:
        return db.scalar(select(func.count()).select_from(Booking).where(*query))
    # One atomic conditional UPDATE: never lock a booking then its customer/room.
    count = db.execute(
        update(Booking).where(*query).values(idempotency_key=None, updated_at=Booking.updated_at)
    ).rowcount
    db.commit()
    return count


def main():
    from .config import Settings
    from .database import make_engine, make_session_factory

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Expire keys older than 30 days")
    args = parser.parse_args()
    engine = make_engine(Settings.from_env().database_url)
    try:
        with make_session_factory(engine)() as db:
            count = expire_keys(db, apply=args.apply)
            print({"apply": args.apply, "keys": count})
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
