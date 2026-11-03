from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbDep
from app.ml import backtest, elo, poisson
from app.ml.data import load_finished
from app.models import Competition, Match, Odds, Team
from app.services import odds as calc
from app.services.odds_analysis import latest_per_selection

router = APIRouter(tags=["moteur statistique"])


def _value_block(est: dict, odds_rows: list[Odds]) -> list[dict]:
    out = []
    for (bookmaker, market, sel, line), o in latest_per_selection(odds_rows).items():
        try:
            if market in ("1X2", "DC", "BTTS"):
                p = est[market][sel]
            elif market == "OU":
                p = est["OU"][str(line)][sel]
            else:
                continue  # corners : pas encore modélisés
        except KeyError:
            continue  # ligne non couverte par le modèle
        out.append(
            {
                "bookmaker": bookmaker,
                "market": market,
                "selection": sel,
                "line": line,
                "price": o.price,
                "estimated_probability": p,
                "implied_probability": calc.implied_probability(o.price),
                "edge": calc.edge(p, o.price),
                "expected_value": calc.expected_value(p, o.price),
            }
        )
    return out


@router.get("/matches/{match_id}/prediction")
def prediction(match_id: int, db: DbDep):
    """Probabilités du modèle de Poisson, calculées uniquement sur les matchs antérieurs au coup d'envoi.
    Refuse de prédire (available=false) quand l'historique est insuffisant."""
    m = db.get(Match, match_id)
    if not m:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Match introuvable.")
    recs = load_finished(db, m.competition_id, before=m.kickoff_at)
    f = poisson.fit(recs, m.kickoff_at)
    base = {
        "match_id": m.id,
        "as_of": m.kickoff_at.isoformat(),
        "model": {"name": poisson.MODEL_NAME, "version": poisson.MODEL_VERSION, "params": f.params},
        "limitations": poisson.LIMITATIONS,
        "training": {
            "matches": f.n_matches,
            "home_team_matches": f.games.get(m.home_team_id, 0),
            "away_team_matches": f.games.get(m.away_team_id, 0),
        },
    }
    reason = poisson.eligibility(f, m.home_team_id, m.away_team_id)
    if reason:
        return {**base, "available": False, "reason": reason}
    lh, la = poisson.expected_goals(f, m.home_team_id, m.away_team_id)
    est = poisson.markets(lh, la)
    odds_rows = list(db.scalars(select(Odds).where(Odds.match_id == m.id)))
    return {
        **base,
        "available": True,
        "expected_goals": {"home": lh, "away": la},
        "probabilities": est,
        "value": _value_block(est, odds_rows),
        "value_note": "Valeur espérée calculée uniquement sur les cotes saisies. Un écart positif n'indique pas un pari gagnant : "
        "il dépend de la qualité du modèle (voir le backtest).",
    }


@router.get("/competitions/{competition_id}/elo")
def competition_elo(competition_id: int, db: DbDep):
    if not db.get(Competition, competition_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Compétition introuvable.")
    recs = load_finished(db, competition_id)
    r = elo.ratings(recs)
    names = (
        {t.id: t.name for t in db.scalars(select(Team).where(Team.id.in_(list(r))))} if r else {}
    )
    ranking = sorted(
        ({"team_id": t, "team": names.get(t), "rating": v} for t, v in r.items()),
        key=lambda x: -x["rating"],
    )
    return {
        "competition_id": competition_id,
        "matches_used": len(recs),
        "ranking": ranking,
        "note": "Classement de force relative (Elo, départ à 1500). Fiable seulement avec plusieurs matchs par équipe.",
    }


@router.get("/competitions/{competition_id}/backtest")
def competition_backtest(competition_id: int, db: DbDep, _: CurrentUser):
    """Évalue le modèle en walk-forward sur l'historique enregistré (Brier, Log Loss, calibration)."""
    if not db.get(Competition, competition_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Compétition introuvable.")
    return backtest.run(load_finished(db, competition_id))
