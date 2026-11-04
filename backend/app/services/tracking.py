"""Enregistrement immuable des prédictions, règlement des résultats, mesures de performance."""

import math
from collections import defaultdict
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ml import poisson
from app.ml.data import load_finished
from app.ml.metrics import EPS
from app.models import AnalysisHistory, Match, ModelVersion, Odds, Prediction, PredictionResult
from app.models.mixins import utcnow
from app.models.prediction import PredictionOutcome
from app.models.sports import MatchStatus
from app.services.odds_analysis import latest_per_selection

OU_LINE = 2.5
# (marché, sélection, ligne) enregistrés pour chaque match
SLOTS = (
    [("1X2", s, None) for s in ("home", "draw", "away")]
    + [("OU", s, OU_LINE) for s in ("over", "under")]
    + [("BTTS", s, None) for s in ("yes", "no")]
)


class RecordError(Exception):
    def __init__(self, status: int, message: str):
        self.status, self.message = status, message


def get_model_version(db: Session) -> ModelVersion:
    mv = db.scalar(
        select(ModelVersion).where(
            ModelVersion.name == poisson.MODEL_NAME, ModelVersion.version == poisson.MODEL_VERSION
        )
    )
    if mv is None:
        mv = ModelVersion(
            name=poisson.MODEL_NAME,
            version=poisson.MODEL_VERSION,
            is_active=True,
            params={"half_life_days": 365.0, "shrink": 5.0},
        )
        db.add(mv)
        db.flush()
    return mv


def _probability(est: dict, market: str, sel: str) -> float:
    return est["OU"][str(OU_LINE)][sel] if market == "OU" else est[market][sel]


def record(
    db: Session, match: Match, user_id: int | None, now: datetime | None = None
) -> tuple[list[Prediction], bool]:
    """Enregistre les prédictions d'un match à venir. Retourne (lignes, déjà_enregistrées)."""
    now = now or utcnow()
    mv = get_model_version(db)
    existing = list(
        db.scalars(
            select(Prediction).where(
                Prediction.match_id == match.id, Prediction.model_version_id == mv.id
            )
        )
    )
    if existing:
        return existing, True  # jamais de remplacement
    if now >= match.kickoff_at:
        raise RecordError(
            409, "Le match a commencé : aucune prédiction ne peut plus être enregistrée."
        )
    recs = load_finished(db, match.competition_id, before=match.kickoff_at)
    f = poisson.fit(recs, match.kickoff_at)
    reason = poisson.eligibility(f, match.home_team_id, match.away_team_id)
    if reason:
        raise RecordError(422, f"Prédiction non enregistrée : {reason}")
    est = poisson.markets(*poisson.expected_goals(f, match.home_team_id, match.away_team_id))
    odds = latest_per_selection(list(db.scalars(select(Odds).where(Odds.match_id == match.id))))
    rows = []
    for market, sel, line in SLOTS:
        prices = [o.price for (_, m, s, ln), o in odds.items() if (m, s, ln) == (market, sel, line)]
        rows.append(
            Prediction(
                match_id=match.id,
                model_version_id=mv.id,
                market=market,
                selection=sel,
                line=line,
                probability=_probability(est, market, sel),
                observed_odds=max(prices) if prices else None,  # meilleure cote saisie
                limitations=" | ".join(poisson.LIMITATIONS),
                created_at=now,
            )
        )
    db.add_all(rows)
    db.add(
        AnalysisHistory(
            user_id=user_id,
            match_id=match.id,
            kind="prediction_recorded",
            payload={"model": f"{mv.name}-{mv.version}", "training_matches": f.n_matches},
        )
    )
    db.commit()
    return rows, False


def outcome_of(market: str, sel: str, line: float | None, hg: int, ag: int) -> PredictionOutcome:
    if market == "1X2":
        won = {"home": hg > ag, "draw": hg == ag, "away": hg < ag}[sel]
    elif market == "OU":
        won = (hg + ag > line) if sel == "over" else (hg + ag < line)
    elif market == "BTTS":
        won = (hg > 0 and ag > 0) == (sel == "yes")
    else:
        raise ValueError(f"Marché non réglable : {market}")
    return PredictionOutcome.WIN if won else PredictionOutcome.LOSS


def settle_match(db: Session, match: Match, now: datetime | None = None) -> int:
    """Crée les résultats manquants d'un match terminé (ou annulé => void). Idempotent, jamais de remplacement."""
    if match.status == MatchStatus.CANCELLED:
        final = None
    elif (
        match.status == MatchStatus.FINISHED
        and match.home_score is not None
        and match.away_score is not None
    ):
        final = (match.home_score, match.away_score)
    else:
        return 0
    settled = {
        r.prediction_id
        for r in db.scalars(
            select(PredictionResult).join(Prediction).where(Prediction.match_id == match.id)
        )
    }
    n = 0
    for p in db.scalars(select(Prediction).where(Prediction.match_id == match.id)):
        if p.id in settled:
            continue
        oc = (
            PredictionOutcome.VOID
            if final is None
            else outcome_of(p.market, p.selection, p.line, *final)
        )
        db.add(PredictionResult(prediction_id=p.id, outcome=oc, settled_at=now or utcnow()))
        n += 1
    db.commit()
    return n


def settle_pending(db: Session) -> int:
    ids = db.scalars(select(Prediction.match_id).distinct())
    return sum(settle_match(db, m) for m in (db.get(Match, i) for i in list(ids)) if m)


# ---------- Performance ----------


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float] | None:
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def _summarise(items: list[dict]) -> dict:
    """items : une entrée par (match, marché) réglé — {probs:{sel:p}, winner:sel, odds:{sel:cote}}."""
    n = len(items)
    if n == 0:
        return {"settled": 0, "reliable": False}
    multi = [it for it in items if len(it["probs"]) == 3]
    brier = ll = None
    sq = 0.0
    logs = 0.0
    for it in items:
        for sel, p in it["probs"].items():
            sq += (p - (1.0 if sel == it["winner"] else 0.0)) ** 2
        logs += -math.log(max(it["probs"][it["winner"]], EPS))
    brier, ll = sq / n, logs / n
    hits = sum(max(it["probs"], key=it["probs"].get) == it["winner"] for it in items)
    bets = [
        (
            it["odds"].get(max(it["probs"], key=it["probs"].get)),
            max(it["probs"], key=it["probs"].get) == it["winner"],
        )
        for it in items
    ]
    bets = [(o, w) for o, w in bets if o]
    profit = sum((o - 1) if w else -1 for o, w in bets)
    value = [
        (o, s == it["winner"])
        for it in items
        for s, p in it["probs"].items()
        if (o := it["odds"].get(s)) and p * o - 1 > 0
    ]
    vprofit = sum((o - 1) if w else -1 for o, w in value)
    ci = wilson(hits, n)
    return {
        "settled": n,
        "reliable": n >= 100,
        "has_multiclass": bool(multi),
        "hit_rate": hits / n,
        "hit_rate_ci95": list(ci) if ci else None,
        "brier": brier,
        "log_loss": ll,
        "top_pick_bets": {
            "n": len(bets),
            "profit_units": profit,
            "roi": profit / len(bets) if bets else None,
        },
        "value_bets": {
            "n": len(value),
            "profit_units": vprofit,
            "roi": vprofit / len(value) if value else None,
        },
    }


def performance(db: Session, competition_id: int | None = None, market: str | None = None) -> dict:
    q = (
        select(Prediction, PredictionResult, Match)
        .join(PredictionResult, PredictionResult.prediction_id == Prediction.id)
        .join(Match, Match.id == Prediction.match_id)
    )
    if competition_id:
        q = q.where(Match.competition_id == competition_id)
    if market:
        q = q.where(Prediction.market == market)
    groups: dict[tuple, dict] = {}
    voids = 0
    for p, r, m in db.execute(q):
        if r.outcome == PredictionOutcome.VOID:
            voids += 1
            continue
        g = groups.setdefault(
            (m.id, p.model_version_id, p.market, p.line),
            {"probs": {}, "odds": {}, "winner": None, "comp": m.competition_id, "market": p.market},
        )
        g["probs"][p.selection] = p.probability
        if p.observed_odds:
            g["odds"][p.selection] = p.observed_odds
        if r.outcome == PredictionOutcome.WIN:
            g["winner"] = p.selection
    items = [g for g in groups.values() if g["winner"] and len(g["probs"]) >= 2]
    by_market, by_comp = defaultdict(list), defaultdict(list)
    for g in items:
        by_market[g["market"]].append(g)
        by_comp[g["comp"]].append(g)
    pending = (
        db.scalar(select(func.count()).select_from(Prediction))
        - sum(len(g["probs"]) for g in groups.values())
        - voids
    )
    return {
        "overall": _summarise(items),
        "voided": voids,
        "pending_predictions": max(pending, 0),
        "by_market": {k: _summarise(v) for k, v in sorted(by_market.items())},
        "by_competition": {str(k): _summarise(v) for k, v in sorted(by_comp.items())},
        "notes": [
            "Le Brier d'un marché à 3 issues (1X2) n'est pas comparable à celui d'un marché à 2 issues (OU, BTTS) : lire par marché.",
            "Taux de réussite = fréquence à laquelle l'issue la plus probable s'est réalisée (intervalle de Wilson à 95 %).",
            "ROI théorique = mise unitaire sur l'issue favorite du modèle, avec la meilleure cote saisie avant le match ; calculé uniquement sur les paris dont une cote existait.",
            "En dessous de 100 événements réglés, aucun de ces chiffres n'est statistiquement fiable.",
        ],
    }
