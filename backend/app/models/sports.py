import enum
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import CreatedAtMixin, DataSource, UTCDateTime


class MatchStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    LIVE = "live"
    FINISHED = "finished"
    POSTPONED = "postponed"
    CANCELLED = "cancelled"


class _Sourced(CreatedAtMixin):
    source: Mapped[DataSource] = mapped_column(
        Enum(DataSource, native_enum=False), default=DataSource.MANUAL
    )
    provider_id: Mapped[int | None] = mapped_column(ForeignKey("api_providers.id"))
    external_id: Mapped[str | None] = mapped_column(String(100))


class Team(_Sourced, Base):
    __tablename__ = "teams"
    __table_args__ = (UniqueConstraint("name", "country", name="uq_teams_name_country"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    short_name: Mapped[str | None] = mapped_column(String(20))
    country: Mapped[str | None] = mapped_column(String(80))


class Competition(_Sourced, Base):
    __tablename__ = "competitions"
    __table_args__ = (UniqueConstraint("name", "season", name="uq_competitions_name_season"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150))
    country: Mapped[str | None] = mapped_column(String(80))
    season: Mapped[str | None] = mapped_column(String(20))  # ex: 2025-2026


class Match(_Sourced, Base):
    __tablename__ = "matches"
    __table_args__ = (
        Index("ix_matches_kickoff_at", "kickoff_at"),
        CheckConstraint("home_team_id <> away_team_id", name="distinct_teams"),
        CheckConstraint("home_score IS NULL OR home_score >= 0", name="home_score_pos"),
        CheckConstraint("away_score IS NULL OR away_score >= 0", name="away_score_pos"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    competition_id: Mapped[int] = mapped_column(ForeignKey("competitions.id"))
    home_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    away_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    kickoff_at: Mapped[datetime] = mapped_column(UTCDateTime)
    status: Mapped[MatchStatus] = mapped_column(
        Enum(MatchStatus, native_enum=False), default=MatchStatus.SCHEDULED
    )
    home_score: Mapped[int | None] = mapped_column(Integer)
    away_score: Mapped[int | None] = mapped_column(Integer)
    home_score_ht: Mapped[int | None] = mapped_column(Integer)
    away_score_ht: Mapped[int | None] = mapped_column(Integer)

    competition: Mapped[Competition] = relationship()
    home_team: Mapped[Team] = relationship(foreign_keys=[home_team_id])
    away_team: Mapped[Team] = relationship(foreign_keys=[away_team_id])


class MatchStatistics(CreatedAtMixin, Base):
    """Statistiques d'une équipe sur un match. Colonnes NULL = donnée absente (jamais inventée)."""

    __tablename__ = "match_statistics"
    __table_args__ = (
        UniqueConstraint("match_id", "team_id", name="uq_match_statistics_match_team"),
        CheckConstraint(
            "possession_pct IS NULL OR (possession_pct BETWEEN 0 AND 100)", name="possession_range"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"))
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    shots: Mapped[int | None] = mapped_column(Integer)
    shots_on_target: Mapped[int | None] = mapped_column(Integer)
    corners: Mapped[int | None] = mapped_column(Integer)
    possession_pct: Mapped[float | None] = mapped_column(Float)
    fouls: Mapped[int | None] = mapped_column(Integer)
    yellow_cards: Mapped[int | None] = mapped_column(Integer)
    red_cards: Mapped[int | None] = mapped_column(Integer)
    source: Mapped[DataSource] = mapped_column(
        Enum(DataSource, native_enum=False), default=DataSource.MANUAL
    )


class TeamForm(CreatedAtMixin, Base):
    """Instantané de forme calculé (cache dérivé des matchs ; recalculable)."""

    __tablename__ = "team_forms"
    __table_args__ = (
        UniqueConstraint("team_id", "as_of", "window", "venue", name="uq_team_forms_snapshot"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    as_of: Mapped[datetime] = mapped_column(UTCDateTime)
    window: Mapped[int] = mapped_column(Integer)  # nb de matchs pris en compte
    venue: Mapped[str] = mapped_column(String(10), default="all")  # all | home | away
    played: Mapped[int] = mapped_column(Integer)
    wins: Mapped[int] = mapped_column(Integer)
    draws: Mapped[int] = mapped_column(Integer)
    losses: Mapped[int] = mapped_column(Integer)
    goals_for: Mapped[int] = mapped_column(Integer)
    goals_against: Mapped[int] = mapped_column(Integer)
