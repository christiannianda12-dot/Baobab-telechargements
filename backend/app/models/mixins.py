import enum
from datetime import UTC, datetime

from sqlalchemy import DateTime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TypeDecorator


class UTCDateTime(TypeDecorator):
    """DateTime toujours en UTC (SQLite perd le fuseau ; PostgreSQL le conserve)."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC) if value is not None else None

    def process_result_value(self, value, dialect):
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value


def utcnow() -> datetime:
    return datetime.now(UTC)


class CreatedAtMixin:
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)


class DataSource(str, enum.Enum):
    """Provenance d'une donnée : jamais ambiguë."""

    MANUAL = "manual"
    DEMO = "demo"  # fictive, ne jamais présenter comme réelle
    API = "api"
