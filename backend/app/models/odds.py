from datetime import datetime

from sqlalchemy import CheckConstraint, Enum, Float, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import CreatedAtMixin, DataSource, UTCDateTime, utcnow


class Odds(CreatedAtMixin, Base):
    """Cote saisie ou récupérée. Une cote absente de cette table n'existe pas pour l'application."""

    __tablename__ = "odds"
    __table_args__ = (
        Index("ix_odds_match_market", "match_id", "market"),
        CheckConstraint("price > 1", name="price_gt_1"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"))
    bookmaker: Mapped[str] = mapped_column(String(80))
    market: Mapped[str] = mapped_column(String(40))  # 1X2, OU, BTTS...
    selection: Mapped[str] = mapped_column(String(40))  # home, draw, away, over, under...
    line: Mapped[float | None] = mapped_column(Float)  # ex: 2.5
    price: Mapped[float] = mapped_column(Float)  # cote décimale (> 1)
    recorded_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    source: Mapped[DataSource] = mapped_column(
        Enum(DataSource, native_enum=False), default=DataSource.MANUAL
    )
    provider_id: Mapped[int | None] = mapped_column(ForeignKey("api_providers.id"))
