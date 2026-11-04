"""Banc d'essai : le modèle contre le marché (cotes de clôture importées), sur EXACTEMENT les mêmes matchs.

Règle d'honnêteté : si le marché fait mieux que le modèle, la page le dit. Les paris « à valeur » simulés utilisent
les cotes de clôture (marge incluse) : ils mesurent si les écarts du modèle auraient été rentables, pas une promesse."""

import math
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ml import backtest, metrics, poisson
from app.ml.data import load_finished
from app.models import Odds
from app.services.csv_adapters import season_of
from app.services.csv_import import CLOSING_BOOKMAKER

SELS = ("home", "draw", "away")
THRESHOLDS = (0.0, 0.03, 0.05, 0.10)


def _market_probs(
    db: Session, match_ids: list[int]
) -> dict[int, tuple[tuple[float, float, float], tuple[float, float, float]]]:
    """match_id -> (probabilités sans marge, cotes) pour les cotes 1X2 de clôture complètes."""
    rows: dict[int, dict[str, float]] = defaultdict(dict)
    q = (
        select(Odds)
        .where(
            Odds.bookmaker == CLOSING_BOOKMAKER, Odds.market == "1X2", Odds.match_id.in_(match_ids)
        )
        .order_by(Odds.recorded_at, Odds.id)
    )
    for o in db.scalars(q):
        rows[o.match_id][o.selection] = o.price
    out = {}
    for mid, d in rows.items():
        if all(s in d for s in SELS):
            odds = tuple(d[s] for s in SELS)
            inv = [1 / x for x in odds]
            tot = sum(inv)
            out[mid] = (tuple(x / tot for x in inv), odds)
    return out


def _paired(diffs: list[float]) -> dict:
    n = len(diffs)
    mean = sum(diffs) / n
    sd = math.sqrt(sum((d - mean) ** 2 for d in diffs) / (n - 1)) if n > 1 else 0.0
    se = sd / math.sqrt(n) if n else 0.0
    return {"mean": mean, "se": se, "z": mean / se if se else 0.0}


def compute(db: Session, competition_id: int) -> dict:
    recs = load_finished(db, competition_id)
    ev = backtest.walk_forward(recs)
    base = {
        "model": f"{poisson.MODEL_NAME}-{poisson.MODEL_VERSION}",
        "history_matches": len(recs),
        "evaluated_by_model": len(ev),
    }
    if len(ev) < 20:
        return {
            **base,
            "available": False,
            "reason": "Moins de 20 matchs évaluables : aucune comparaison possible.",
        }
    mk = _market_probs(db, [e["rec"].match_id for e in ev])
    joint = [e for e in ev if e["rec"].match_id in mk]
    if len(joint) < 20:
        return {
            **base,
            "available": False,
            "market_matches": len(joint),
            "reason": "Pas assez de cotes de clôture importées pour comparer au marché (fichiers football-data.co.uk : colonnes AvgCH/AvgCD/AvgCA).",
        }

    outs = [e["outcome"] for e in joint]
    p_model, p_market, p_base = (
        [e["probs"] for e in joint],
        [mk[e["rec"].match_id][0] for e in joint],
        [e["base"] for e in joint],
    )
    uniform = [(1 / 3, 1 / 3, 1 / 3)] * len(joint)

    def row(p):
        return {"brier": metrics.brier(p, outs), "log_loss": metrics.log_loss(p, outs)}

    sq = lambda p, o: sum((p[i] - (1.0 if i == o else 0.0)) ** 2 for i in range(3))  # noqa: E731
    d_brier = [
        sq(a, o) - sq(b, o) for a, b, o in zip(p_model, p_market, outs, strict=True)
    ]  # >0 : le modèle est PIRE
    d_ll = [
        -math.log(max(a[o], 1e-12)) + math.log(max(b[o], 1e-12))
        for a, b, o in zip(p_model, p_market, outs, strict=True)
    ]
    pb, pl = _paired(d_brier), _paired(d_ll)

    by_season: dict[str, list[int]] = defaultdict(list)
    for i, e in enumerate(joint):
        by_season[season_of(e["rec"].when.date().isoformat())].append(i)
    seasons = []
    for ssn, idx in sorted(by_season.items()):
        o = [outs[i] for i in idx]
        seasons.append(
            {
                "season": ssn,
                "matches": len(idx),
                "model_brier": metrics.brier([p_model[i] for i in idx], o),
                "market_brier": metrics.brier([p_market[i] for i in idx], o),
                "baseline_brier": metrics.brier([p_base[i] for i in idx], o),
            }
        )

    value = []
    for thr in THRESHOLDS:
        bets = wins = 0
        profit = 0.0
        for e in joint:
            odds = mk[e["rec"].match_id][1]
            for k in range(3):
                if e["probs"][k] * odds[k] - 1 > thr:
                    bets += 1
                    if e["outcome"] == k:
                        wins += 1
                        profit += odds[k] - 1
                    else:
                        profit -= 1
        value.append(
            {
                "min_expected_value": thr,
                "bets": bets,
                "wins": wins,
                "profit_units": profit,
                "roi": profit / bets if bets else None,
            }
        )

    # Courbes pour les graphiques : calibration (victoire domicile) et cumuls dans le temps (sous-échantillonnés).
    hit_home = [o == 0 for o in outs]
    calib = {
        "model": metrics.calibration_bins([p[0] for p in p_model], hit_home),
        "market": metrics.calibration_bins([p[0] for p in p_market], hit_home),
    }
    cum_b = cum_p = 0.0
    series = []
    for e, d in zip(joint, d_brier, strict=True):
        cum_b += d
        odds = mk[e["rec"].match_id][1]
        for k in range(3):
            if e["probs"][k] * odds[k] - 1 > 0:
                cum_p += (odds[k] - 1) if e["outcome"] == k else -1
        series.append(
            {"date": e["rec"].when.date().isoformat(), "brier_gap": cum_b, "profit": cum_p}
        )
    step = max(1, len(series) // 150)
    cumulative = series[::step] + ([series[-1]] if (len(series) - 1) % step else [])

    z = pb["z"]
    if z > 2:
        verdict = "Le marché est significativement plus précis que le modèle : n'engagez pas d'argent sur ses écarts."
    elif z < -2:
        verdict = "Le modèle est significativement plus précis que le marché sur cet échantillon : à confirmer sur de nouvelles données avant toute conclusion."
    else:
        verdict = "Aucune différence statistiquement établie entre le modèle et le marché sur cet échantillon."
    return {
        **base,
        "available": True,
        "matches": len(joint),
        "reliable": len(joint) >= 300,
        "scores": {
            "model": row(p_model),
            "market": row(p_market),
            "baseline": row(p_base),
            "chance": row(uniform),
        },
        "model_minus_market": {
            "brier": pb,
            "log_loss": pl,
            "note": "Différence moyenne par match (modèle − marché) ; positive = modèle moins précis. z > 2 ≈ différence établie.",
        },
        "by_season": seasons,
        "value_bets": value,
        "calibration": calib,
        "cumulative": cumulative,
        "verdict": verdict,
        "notes": [
            "Mêmes matchs pour toutes les lignes : ceux que le modèle peut prédire ET qui ont des cotes de clôture complètes.",
            "Le marché est ici la moyenne des cotes de clôture, marge retirée par normalisation : la référence la plus exigeante.",
            "Paris simulés : mise unitaire sur chaque issue dont la valeur espérée dépasse le seuil, aux cotes de clôture (marge incluse). Rétrospectif, sans garantie future.",
        ],
    }
