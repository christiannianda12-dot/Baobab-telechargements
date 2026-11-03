"""Meilleures cotes disponibles pour les matchs à venir (toutes sources de cotes confondues, hors cotes de clôture)."""

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Odds
from app.services.csv_import import CLOSING_BOOKMAKER

AVG_LABEL = "Moyenne du marché"
MAX_LABEL = "Meilleure cote du marché"


def best_for_matches(db: Session, match_ids: list[int]) -> dict[int, dict[tuple, dict]]:
    """match_id -> {(marché, issue, ligne): {price, bookmaker, bookmakers, average}} ; dernière cote de chaque bookmaker."""
    if not match_ids:
        return {}
    latest: dict[tuple, float] = {}
    q = (
        select(Odds)
        .where(Odds.match_id.in_(match_ids), Odds.bookmaker != CLOSING_BOOKMAKER)
        .order_by(Odds.recorded_at, Odds.id)
    )
    for o in db.scalars(q):
        latest[(o.match_id, o.market, o.selection, o.line, o.bookmaker)] = o.price
    groups: dict[tuple, list[tuple[str, float]]] = defaultdict(list)
    for (mid, mk, sel, line, bk), price in latest.items():
        groups[(mid, mk, sel, line)].append((bk, price))
    out: dict[int, dict[tuple, dict]] = defaultdict(dict)
    for (mid, mk, sel, line), entries in groups.items():
        bk, price = max(entries, key=lambda e: e[1])
        avg = next((p for b, p in entries if b == AVG_LABEL), None)
        real = [p for b, p in entries if b not in (AVG_LABEL, MAX_LABEL)] or [p for _, p in entries]
        out[mid][(mk, sel, line)] = {
            "price": price,
            "bookmaker": bk,
            "bookmakers": len(entries),
            "average": avg if avg else sum(real) / len(real),
        }
    return out
