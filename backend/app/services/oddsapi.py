"""Connecteur The Odds API (https://the-odds-api.com) : cotes de nombreux bookmakers, dont 1xBet quand la région le propose.

Officiel, gratuit jusqu'à un quota (≈500 crédits/mois). Nécessite une clé personnelle, saisie dans Paramètres.
Lecture seule : l'application n'envoie aucun pari. Une requête « /sports » ne consomme pas de crédit ; chaque requête
de cotes en consomme (marchés x régions). Le quota restant est lu dans les en-têtes et respecté."""

import time
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import FollowedLeague, Match, Odds, Team
from app.models.mixins import DataSource, utcnow
from app.models.sports import MatchStatus
from app.services import appsettings
from app.services.names import norm_key, resolve_existing

BASE = "https://api.the-odds-api.com/v4"
MIN_REMAINING = 25  # on s'arrête avant d'épuiser le quota
# code du catalogue -> clés « sport » de The Odds API (les clés inexistantes sont ignorées après interrogation de /sports)
SPORT_KEYS = {
    "E0": "soccer_epl",
    "E1": "soccer_efl_champ",
    "SC0": "soccer_spl",
    "D1": "soccer_germany_bundesliga",
    "D2": "soccer_germany_bundesliga2",
    "I1": "soccer_italy_serie_a",
    "I2": "soccer_italy_serie_b",
    "SP1": "soccer_spain_la_liga",
    "SP2": "soccer_spain_segunda_division",
    "F1": "soccer_france_ligue_one",
    "F2": "soccer_france_ligue_two",
    "N1": "soccer_netherlands_eredivisie",
    "B1": "soccer_belgium_first_div",
    "P1": "soccer_portugal_primeira_liga",
    "T1": "soccer_turkey_super_league",
    "G1": "soccer_greece_super_league",
    "CL": "soccer_uefa_champs_league",
    "EL": "soccer_uefa_europa_league",
    "CONF": "soccer_uefa_europa_conference_league",
    "BRA": "soccer_brazil_campeonato",
    "ARG": "soccer_argentina_primera_division",
    "USA": "soccer_usa_mls",
    "JPN": "soccer_japan_j_league",
    "MEX": "soccer_mexico_ligamx",
}
LINES = {1.5, 2.5, 3.5}


class OddsApiError(Exception):
    pass


def _get(client: httpx.Client, path: str, params: dict) -> httpx.Response:
    try:
        r = client.get(f"{BASE}{path}", params=params, timeout=30)
    except httpx.HTTPError as e:
        raise OddsApiError(f"Connexion impossible ({type(e).__name__}).") from None
    if r.status_code == 401:
        raise OddsApiError("Clé refusée (401) : vérifiez la clé de The Odds API.")
    if r.status_code == 429:
        raise OddsApiError("Quota de requêtes dépassé (429).")
    if r.status_code != 200:
        raise OddsApiError(f"The Odds API a répondu HTTP {r.status_code}.")
    return r


def test_key(key: str, client: httpx.Client | None = None) -> dict:
    """Vérifie la clé via /sports (sans consommer de crédit) et indique le quota restant."""
    own = client is None
    client = client or httpx.Client()
    try:
        r = _get(client, "/sports", {"apiKey": key})
    finally:
        if own:
            client.close()
    soccer = [s for s in r.json() if str(s.get("key", "")).startswith("soccer")]
    return {
        "ok": True,
        "soccer_competitions": len(soccer),
        "remaining": r.headers.get("x-requests-remaining"),
        "used": r.headers.get("x-requests-used"),
    }


def _outcomes(event: dict, home: str, away: str):
    """Itère (bookmaker, marché, issue, ligne, cote) à partir d'un évènement The Odds API."""
    for bk in event.get("bookmakers", []):
        title = str(bk.get("title") or bk.get("key"))[:80]
        for mk in bk.get("markets", []):
            for o in mk.get("outcomes", []):
                price = o.get("price")
                if not isinstance(price, (int, float)) or price <= 1:
                    continue
                if mk["key"] == "h2h":
                    nm = o.get("name", "")
                    sel = (
                        "draw"
                        if nm.lower() == "draw"
                        else "home"
                        if nm == home
                        else "away"
                        if nm == away
                        else None
                    )
                    if sel:
                        yield title, "1X2", sel, None, float(price)
                elif (
                    mk["key"] == "totals"
                    and o.get("point") in LINES
                    and o.get("name") in ("Over", "Under")
                ):
                    yield title, "OU", o["name"].lower(), float(o["point"]), float(price)


def refresh_odds(
    db: Session, client: httpx.Client | None = None, regions: str = "eu,uk", pause: float = 1.0
) -> dict:
    """Met à jour les cotes des matchs à venir des championnats suivis. Retourne un résumé."""
    key = appsettings.get(db, "odds_api_key").strip()
    if not key:
        return {"skipped": "pas de clé The Odds API"}
    own = client is None
    client = client or httpx.Client()
    summary = {
        "requests": 0,
        "events": 0,
        "matched": 0,
        "odds_added": 0,
        "errors": [],
        "stopped": None,
    }
    try:
        active = {s["key"] for s in _get(client, "/sports", {"apiKey": key}).json()}
        followed = [f.code for f in db.scalars(select(FollowedLeague))]
        teams: dict[str, Team] = {}
        for t in db.scalars(select(Team)):
            teams.setdefault(norm_key(t.name), t)
        now = utcnow()
        for code in followed:
            sport = SPORT_KEYS.get(code)
            if not sport or sport not in active:
                continue
            try:
                r = _get(
                    client,
                    f"/sports/{sport}/odds",
                    {
                        "apiKey": key,
                        "regions": regions,
                        "markets": "h2h,totals",
                        "oddsFormat": "decimal",
                    },
                )
            except OddsApiError as e:
                summary["errors"].append(f"{code}: {e}")
                if "Quota" in str(e) or "Clé" in str(e):
                    summary["stopped"] = str(e)
                    break
                continue
            summary["requests"] += 1
            remaining = r.headers.get("x-requests-remaining")
            if remaining is not None:
                appsettings.put(db, "odds_api_remaining", remaining)
            for ev in r.json():
                summary["events"] += 1
                h = resolve_existing(norm_key(ev.get("home_team", "")), teams)
                a = resolve_existing(norm_key(ev.get("away_team", "")), teams)
                try:
                    kick = datetime.fromisoformat(
                        str(ev["commence_time"]).replace("Z", "+00:00")
                    ).astimezone(UTC)
                except (KeyError, ValueError):
                    continue
                if not h or not a:
                    continue
                m = db.scalar(
                    select(Match).where(
                        Match.home_team_id == h[0].id,
                        Match.away_team_id == a[0].id,
                        Match.status == MatchStatus.SCHEDULED,
                        Match.kickoff_at >= kick - timedelta(days=1),
                        Match.kickoff_at <= kick + timedelta(days=1),
                    )
                )
                if m is None:
                    continue
                summary["matched"] += 1
                latest = {
                    (o.bookmaker, o.market, o.selection, o.line): o.price
                    for o in db.scalars(
                        select(Odds)
                        .where(Odds.match_id == m.id)
                        .order_by(Odds.recorded_at, Odds.id)
                    )
                }
                for bk, mk, sel, line, price in _outcomes(ev, ev["home_team"], ev["away_team"]):
                    if latest.get((bk, mk, sel, line)) != price:
                        db.add(
                            Odds(
                                match_id=m.id,
                                bookmaker=bk,
                                market=mk,
                                selection=sel,
                                line=line,
                                price=price,
                                recorded_at=now,
                                source=DataSource.API,
                            )
                        )
                        summary["odds_added"] += 1
            db.commit()
            if remaining is not None and remaining.isdigit() and int(remaining) < MIN_REMAINING:
                summary["stopped"] = f"quota presque épuisé ({remaining} crédits restants)"
                break
            time.sleep(pause)
        appsettings.put(db, "odds_api_last_run", utcnow().isoformat())
    finally:
        if own:
            client.close()
    return summary
