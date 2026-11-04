"""Analyse des cotes ENREGISTRÉES d'un match (jamais de cote non saisie/récupérée)."""

from collections import defaultdict

from app.models import Odds
from app.services import odds as calc

# Issues attendues pour considérer un marché « complet » (nécessaire à la correction de marge).
COMPLETE_SELECTIONS: dict[str, frozenset[str]] = {
    "1X2": frozenset({"home", "draw", "away"}),
    "OU": frozenset({"over", "under"}),
    "BTTS": frozenset({"yes", "no"}),
}


def latest_per_selection(rows: list[Odds]) -> dict[tuple[str, str, str, float | None], Odds]:
    """Dernière cote saisie par (bookmaker, marché, sélection, ligne)."""
    latest: dict[tuple[str, str, str, float | None], Odds] = {}
    for o in sorted(rows, key=lambda r: (r.recorded_at, r.id)):
        latest[(o.bookmaker, o.market, o.selection, o.line)] = o
    return latest


def analyse(rows: list[Odds]) -> list[dict]:
    groups: dict[tuple[str, str, float | None], dict[str, Odds]] = defaultdict(dict)
    for (bookmaker, market, selection, line), o in latest_per_selection(rows).items():
        groups[(bookmaker, market, line)][selection] = o

    out = []
    for (bookmaker, market, line), sels in sorted(
        groups.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2] or 0)
    ):
        expected = COMPLETE_SELECTIONS.get(market)
        entry = {
            "bookmaker": bookmaker,
            "market": market,
            "line": line,
            "selections": {
                s: {"price": o.price, "implied_probability": calc.implied_probability(o.price)}
                for s, o in sels.items()
            },
            "complete": bool(expected and set(sels) == expected),
            "margin": None,
            "fair_probabilities": None,
        }
        if entry["complete"]:
            names = sorted(sels)
            prices = [sels[n].price for n in names]
            entry["margin"] = calc.margin(prices)
            entry["fair_probabilities"] = dict(zip(names, calc.remove_margin(prices), strict=True))
        out.append(entry)
    return out
