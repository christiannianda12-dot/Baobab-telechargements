from alembic import context
from sqlalchemy import engine_from_config, pool

import app.models  # noqa: F401  (enregistre les tables)
from app.core.config import get_settings
from app.db.base import Base

config = context.config
config.set_main_option("sqlalchemy.url", get_settings().database_url.replace("%", "%%"))
target_metadata = Base.metadata


def render_item(type_, obj, autogen_context):
    """Les migrations n'importent pas le code applicatif : UTCDateTime -> DateTime(timezone)."""
    if type_ == "type" and obj.__class__.__name__ == "UTCDateTime":
        return "sa.DateTime(timezone=True)"
    return False


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        render_as_batch=True,
        render_item=render_item,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with engine.connect() as conn:
        # render_as_batch : ALTER TABLE compatible SQLite, sans effet gênant sur PostgreSQL
        context.configure(
            connection=conn,
            target_metadata=target_metadata,
            render_as_batch=True,
            compare_type=True,
            render_item=render_item,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
