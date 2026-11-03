"""Tables d'exploitation des données : championnats suivis, alias d'équipes, lots d'import (traçabilité/annulation)."""

from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import CreatedAtMixin, UTCDateTime


class FollowedLeague(CreatedAtMixin, Base):
    __tablename__ = "followed_leagues"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(10), unique=True)  # ex. E0, SP1, BRA
    last_update_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    last_status: Mapped[str | None] = mapped_column(Text)


class TeamAlias(CreatedAtMixin, Base):
    """Nom alternatif d'une équipe (clé normalisée) : l'import le résout vers l'équipe officielle."""

    __tablename__ = "team_aliases"

    id: Mapped[int] = mapped_column(primary_key=True)
    alias_key: Mapped[str] = mapped_column(String(160), unique=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))


class ImportBatch(CreatedAtMixin, Base):
    __tablename__ = "import_batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    source: Mapped[str] = mapped_column(String(20))  # upload | download | fixtures
    label: Mapped[str] = mapped_column(String(255))
    rows: Mapped[int] = mapped_column(Integer, default=0)
    created_matches: Mapped[int] = mapped_column(Integer, default=0)
    updated_matches: Mapped[int] = mapped_column(Integer, default=0)
    skipped: Mapped[int] = mapped_column(Integer, default=0)
    created_teams: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active | rolled_back
    rolled_back_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
