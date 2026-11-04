import enum
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Enum,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    event,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.triggers import install as install_triggers
from app.models.mixins import CreatedAtMixin, UTCDateTime


class ModelVersion(CreatedAtMixin, Base):
    __tablename__ = "model_versions"
    __table_args__ = (UniqueConstraint("name", "version", name="uq_model_versions_name_version"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))  # poisson, elo, logreg, xgboost...
    version: Mapped[str] = mapped_column(String(40))
    params: Mapped[dict | None] = mapped_column(JSON)
    metrics: Mapped[dict | None] = mapped_column(JSON)  # brier, log_loss mesurés
    trained_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)


class Prediction(CreatedAtMixin, Base):
    """Prédiction horodatée et IMMUABLE (voir garde ci-dessous)."""

    __tablename__ = "predictions"
    __table_args__ = (
        Index("ix_predictions_match", "match_id"),
        Index(
            "uq_predictions_slot",
            "match_id",
            "model_version_id",
            "market",
            "selection",
            func.coalesce(text("line"), -1),
            unique=True,
        ),
        CheckConstraint("probability BETWEEN 0 AND 1", name="probability_range"),
        CheckConstraint("observed_odds IS NULL OR observed_odds > 1", name="observed_odds_gt_1"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"))
    model_version_id: Mapped[int] = mapped_column(ForeignKey("model_versions.id"))
    market: Mapped[str] = mapped_column(String(40))
    selection: Mapped[str] = mapped_column(String(40))
    line: Mapped[float | None] = mapped_column(Float)
    probability: Mapped[float] = mapped_column(Float)
    observed_odds: Mapped[float | None] = mapped_column(Float)
    limitations: Mapped[str | None] = mapped_column(
        Text
    )  # limites du modèle, affichées à l'utilisateur


class PredictionOutcome(str, enum.Enum):
    WIN = "win"
    LOSS = "loss"
    VOID = "void"


class PredictionResult(CreatedAtMixin, Base):
    __tablename__ = "prediction_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    prediction_id: Mapped[int] = mapped_column(ForeignKey("predictions.id"), unique=True)
    outcome: Mapped[PredictionOutcome] = mapped_column(Enum(PredictionOutcome, native_enum=False))
    settled_at: Mapped[datetime] = mapped_column(UTCDateTime)


class AnalysisHistory(CreatedAtMixin, Base):
    __tablename__ = "analysis_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    match_id: Mapped[int | None] = mapped_column(ForeignKey("matches.id"))
    kind: Mapped[str] = mapped_column(String(40))  # match_analysis | chat | combo
    query: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict | None] = mapped_column(JSON)


@event.listens_for(Prediction, "before_update")
def _predictions_are_immutable(mapper, connection, target):
    raise ValueError("Une prédiction enregistrée ne peut pas être modifiée.")


@event.listens_for(Prediction, "before_delete")
@event.listens_for(PredictionResult, "before_update")
@event.listens_for(PredictionResult, "before_delete")
def _append_only(mapper, connection, target):
    raise ValueError("Enregistrement en ajout seul : modification et suppression interdites.")


install_triggers(Prediction.__table__)
install_triggers(PredictionResult.__table__)
