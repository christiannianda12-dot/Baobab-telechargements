"""Combinés proposés (prudent / équilibré / ambitieux) et aperçu des prochains matchs.

Chaque sélection combine DEUX avis : le modèle statistique et le marché (cotes moyennes, marge retirée). Le marché étant
mesuré plus précis que le modèle (page Fiabilité), il pèse davantage (70 %). Les cotes proposées sont les plus hautes trouvées
parmi tous les bookmakers disponibles. La valeur espérée est affichée telle quelle, y compris quand elle est négative.
Hypothèse : les matchs d'un même combiné sont indépendants."""

import itertools
import time
from datetime import timedelta
from math import prod

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Competition, Match, Prediction, Team
from app.models.mixins import utcnow
from app.models.sports import MatchStatus
from app.services.best_odds import best_for_matches
from app.services.combos import describe
from app.services.predict import build_prediction

W_MARKET = 0.7
KEYS = [
    ("1X2", "home", None),
    ("1X2", "draw", None),
    ("1X2", "away", None),
    ("OU", "over", 2.5),
    ("OU", "under", 2.5),
]
PROFILES = {
    "prudent": {
        "label": "Prudent",
        "legs": (2, 3),
        "odds": (1.15, 1.65),
        "min_p": 0.60,
        "total": (1.8, 5.0),
        "rank": "prob",
        "blurb": "Peu de sélections très probables : on vise la régularité, pas le gros gain.",
    },
    "equilibre": {
        "label": "Équilibré",
        "legs": (3, 4),
        "odds": (1.35, 2.3),
        "min_p": 0.42,
        "total": (4.0, 14.0),
        "rank": "ev",
        "blurb": "Un compromis : cote totale moyenne, sélections plausibles, valeur espérée la moins défavorable.",
    },
    "ambitieux": {
        "label": "Ambitieux",
        "legs": (4, 5),
        "odds": (1.7, 3.8),
        "min_p": 0.28,
        "total": (12.0, 80.0),
        "rank": "ev",
        "blurb": "Grosse cote totale, probabilité faible : à réserver à de petites mises.",
    },
}
_CACHE: dict[int, tuple[float, dict]] = {}


def _pred(db: Session, m: Match, ttl: float = 120.0) -> dict:
    hit = _CACHE.get(m.id)
    if hit and time.monotonic() - hit[0] < ttl:
        return hit[1]
    p = build_prediction(db, m)
    _CACHE[m.id] = (time.monotonic(), p)
    return p


def _fair(avgs: dict[str, float]) -> dict[str, float] | None:
    if not avgs or any(v <= 1 for v in avgs.values()):
        return None
    tot = sum(1 / v for v in avgs.values())
    return {k: (1 / v) / tot for k, v in avgs.items()}


def upcoming(db: Session, days: int, limit: int = 60) -> list[Match]:
    now = utcnow()
    q = (
        select(Match)
        .where(
            Match.status == MatchStatus.SCHEDULED,
            Match.kickoff_at > now,
            Match.kickoff_at <= now + timedelta(days=days),
        )
        .order_by(Match.kickoff_at)
        .limit(limit)
    )
    return list(db.scalars(q))


def candidates(db: Session, days: int = 3) -> list[dict]:
    ms = upcoming(db, days)
    best = best_for_matches(db, [m.id for m in ms])
    names = {t.id: t.name for t in db.scalars(select(Team))}
    comps = {c.id: c.name for c in db.scalars(select(Competition))}
    out = []
    for m in ms:
        b = best.get(m.id, {})
        if not b:
            continue
        pred = _pred(db, m)
        est = pred.get("probabilities") if pred.get("available") else None
        fair1 = (
            _fair(
                {
                    s: b[("1X2", s, None)]["average"]
                    for s in ("home", "draw", "away")
                    if ("1X2", s, None) in b
                }
            )
            if all(("1X2", s, None) in b for s in ("home", "draw", "away"))
            else None
        )
        fair2 = (
            _fair({s: b[("OU", s, 2.5)]["average"] for s in ("over", "under")})
            if all(("OU", s, 2.5) in b for s in ("over", "under"))
            else None
        )
        for key in KEYS:
            if key not in b:
                continue
            mk, sel, line = key
            pm = (est["OU"]["2.5"][sel] if mk == "OU" else est["1X2"][sel]) if est else None
            pk = fair2 if mk == "OU" else fair1
            pk = pk[sel] if pk else None
            if pm is None and pk is None:
                continue
            pf = (
                (W_MARKET * pk + (1 - W_MARKET) * pm)
                if (pm is not None and pk is not None)
                else (pm if pm is not None else pk)
            )
            e = b[key]
            out.append(
                {
                    "match_id": m.id,
                    "match": f"{names.get(m.home_team_id, '?')} – {names.get(m.away_team_id, '?')}",
                    "league": comps.get(m.competition_id),
                    "kickoff_at": m.kickoff_at.isoformat(),
                    "market": mk,
                    "selection": sel,
                    "line": line,
                    "label": describe(mk, sel, line),
                    "odds": e["price"],
                    "bookmaker": e["bookmaker"],
                    "bookmakers": e["bookmakers"],
                    "avg_odds": round(e["average"], 2),
                    "p_model": pm,
                    "p_market": pk,
                    "p_final": pf,
                    "edge": pf * e["price"] - 1,
                    "basis": "modèle + marché"
                    if pm is not None and pk is not None
                    else "marché seul (modèle indisponible)"
                    if pm is None
                    else "modèle seul",
                }
            )
    return out


def _risk(p: float) -> str:
    return "faible" if p >= 0.35 else "modéré" if p >= 0.15 else "élevé"


def build(db: Session, profile: str, days: int = 3, top: int = 3) -> dict:
    cfg = PROFILES[profile]
    cands = candidates(db, days)
    pool = [
        c
        for c in cands
        if cfg["odds"][0] <= c["odds"] <= cfg["odds"][1] and c["p_final"] >= cfg["min_p"]
    ]
    by_match: dict[int, list[dict]] = {}
    for c in sorted(pool, key=lambda c: -c["p_final"]):
        by_match.setdefault(c["match_id"], []).append(c)
    pool = sorted((c for legs in by_match.values() for c in legs[:2]), key=lambda c: -c["p_final"])[
        :16
    ]
    results = []
    for n in range(cfg["legs"][0], cfg["legs"][1] + 1):
        for combo in itertools.combinations(pool, n):
            if len({c["match_id"] for c in combo}) < n:
                continue
            total = prod(c["odds"] for c in combo)
            if not cfg["total"][0] <= total <= cfg["total"][1]:
                continue
            joint = prod(c["p_final"] for c in combo)
            results.append(
                {
                    "legs": list(combo),
                    "total_odds": total,
                    "joint_probability": joint,
                    "expected_value": joint * total - 1,
                }
            )
    key = (
        (lambda r: (-r["joint_probability"], -r["expected_value"]))
        if cfg["rank"] == "prob"
        else (lambda r: (-r["expected_value"], -r["joint_probability"]))
    )
    chosen, used = [], []
    for r in sorted(results, key=key):
        ids = frozenset(c["match_id"] for c in r["legs"])
        if any(len(ids & u) >= len(ids) - 0 and ids == u for u in used):
            continue
        used.append(ids)
        r["risk"] = _risk(r["joint_probability"])
        r["notes"] = [
            "Matchs supposés indépendants.",
            "Cotes = les plus hautes trouvées entre bookmakers ; vérifiez-les chez votre bookmaker avant de jouer (elles bougent).",
            *(
                [
                    "Valeur espérée estimée négative : sur la durée, ce type de pari perd de l'argent en moyenne."
                ]
                if r["expected_value"] < 0
                else [
                    "Valeur espérée positive selon nos estimations : à prendre avec prudence, l'estimation reste incertaine."
                ]
            ),
        ]
        chosen.append(r)
        if len(chosen) >= top:
            break
    return {
        "profile": profile,
        "label": cfg["label"],
        "blurb": cfg["blurb"],
        "horizon_days": days,
        "candidates": len(cands),
        "eligible_legs": len(pool),
        "weights": {"marche": W_MARKET, "modele": round(1 - W_MARKET, 2)},
        "proposals": chosen,
        "empty_reason": None
        if chosen
        else (
            "Aucun match à venir avec des cotes dans cet horizon : mettez à jour les données (Centre de données) ou élargissez l'horizon."
            if not cands
            else "Aucune combinaison ne respecte les critères de ce profil sur cet horizon."
        ),
    }


def today(db: Session, days: int = 3, limit: int = 40) -> list[dict]:
    ms = upcoming(db, days, limit)
    best = best_for_matches(db, [m.id for m in ms])
    names = {t.id: t.name for t in db.scalars(select(Team))}
    comps = {c.id: c.name for c in db.scalars(select(Competition))}
    rec = (
        set(
            db.scalars(
                select(Prediction.match_id)
                .where(Prediction.match_id.in_([m.id for m in ms]))
                .distinct()
            )
        )
        if ms
        else set()
    )
    out = []
    for m in ms:
        pred = _pred(db, m)
        b = best.get(m.id, {})
        odds = {
            s: {
                "price": b[("1X2", s, None)]["price"],
                "bookmaker": b[("1X2", s, None)]["bookmaker"],
            }
            for s in ("home", "draw", "away")
            if ("1X2", s, None) in b
        }
        probs = pred["probabilities"]["1X2"] if pred.get("available") else None
        value = [s for s in odds if probs and probs[s] * odds[s]["price"] - 1 > 0.05]
        out.append(
            {
                "id": m.id,
                "kickoff_at": m.kickoff_at.isoformat(),
                "league": comps.get(m.competition_id),
                "home": names.get(m.home_team_id),
                "away": names.get(m.away_team_id),
                "probabilities": probs,
                "model_unavailable": None if probs else pred.get("reason"),
                "best_odds": odds,
                "value_selections": value,
                "recorded": m.id in rec,
            }
        )
    return out
