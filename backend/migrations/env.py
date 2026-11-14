from alembic import context

from backend import models  # noqa: F401
from backend.config import Settings
from backend.database import Base, UTCDateTime, make_engine

config = context.config
target_metadata = Base.metadata


def render_item(kind, obj, autogen_context):
    if kind == "type" and isinstance(obj, UTCDateTime):
        return "sa.DateTime(timezone=True)"
    return False


def run(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=connection.dialect.name == "sqlite",
        compare_type=True,
        render_item=render_item,
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    raise RuntimeError(
        "Offline migrations are disabled: the legacy baseline must inspect existing tables safely"
    )
elif config.attributes.get("connection") is not None:
    run(config.attributes["connection"])
else:
    url = config.get_main_option("sqlalchemy.url") or Settings.from_env().database_url
    engine = make_engine(url)
    try:
        with engine.connect() as connection:
            run(connection)
    finally:
        engine.dispose()
