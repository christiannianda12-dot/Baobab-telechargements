"""Construction d'une prédiction pour un match (modèle de Poisson), partagée par l'API, les combinés et l'assistant."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ml import poisson
from app.ml.data import load_finished
from app.models import Match, Odds
from app.services import odds as calc
from app.services.odds_analysis import latest_per_selection


def value_block(est: dict, odds_rows: list[Odds]) -> list[dict]:
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


def build_prediction(db: Session, m: Match) -> dict:
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
        "lambdas": (lh, la),
        "value": value_block(est, odds_rows),
        "value_note": "Valeur espérée calculée uniquement sur les cotes saisies. Un écart positif n'indique pas un pari gagnant : "
        "il dépend de la qualité du modèle (voir le backtest).",
    }
