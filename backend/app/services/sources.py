"""Catalogue des championnats et téléchargement depuis football-data.co.uk (usage personnel, gratuit).

Garde-fous : un seul domaine autorisé, taille limitée, pas de redirection, pause entre requêtes, User-Agent explicite.
Un fichier invalide est refusé en bloc (import atomique) et signalé ; un fichier absent (404) n'est pas une erreur."""

import csv
import io
import time
from datetime import date
from urllib.parse import urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import FollowedLeague
from app.models.mixins import utcnow
from app.services.csv_adapters import DIVISIONS
from app.services.csv_import import import_csv

BASE = "https://www.football-data.co.uk"
ALLOWED_HOSTS = {"www.football-data.co.uk", "football-data.co.uk"}
CUPS_BASE = "https://raw.githubusercontent.com/openfootball/champions-league/master"  # domaine public (openfootball)
MAX_BYTES = 12_000_000
USER_AGENT = "Mozilla/5.0 (compatible; PREDIX-AI/1.0; usage personnel)"

# code -> (nom, pays)
MAIN = {
    code: (name.rsplit(" (", 1)[0], name.rsplit(" (", 1)[1].rstrip(")"))
    for code, name in DIVISIONS.items()
}
EXTRA = {
    "ARG": ("Primera División", "Argentine"),
    "AUT": ("Bundesliga", "Autriche"),
    "BRA": ("Série A", "Brésil"),
    "CHN": ("Super League", "Chine"),
    "DNK": ("Superliga", "Danemark"),
    "FIN": ("Veikkausliiga", "Finlande"),
    "IRL": ("Premier Division", "Irlande"),
    "JPN": ("J1 League", "Japon"),
    "MEX": ("Liga MX", "Mexique"),
    "NOR": ("Eliteserien", "Norvège"),
    "POL": ("Ekstraklasa", "Pologne"),
    "ROU": ("Liga 1", "Roumanie"),
    "RUS": ("Premier League", "Russie"),
    "SWE": ("Allsvenskan", "Suède"),
    "SWZ": ("Super League", "Suisse"),
    "USA": ("MLS", "États-Unis"),
}


# coupes continentales : code -> (nom, zone, nom de fichier)
CUPS = {
    "CL": ("Ligue des champions", "Europe", "cl"),
    "EL": ("Europa League", "Europe", "el"),
    "CONF": ("Conference League", "Europe", "conf"),
}


class SourceError(Exception):
    pass


def catalog() -> list[dict]:
    rows = [{"code": c, "name": n, "country": p, "kind": "main"} for c, (n, p) in MAIN.items()]
    rows += [{"code": c, "name": n, "country": p, "kind": "extra"} for c, (n, p) in EXTRA.items()]
    rows += [{"code": c, "name": n, "country": z, "kind": "cup"} for c, (n, z, _) in CUPS.items()]
    return rows


def recent_seasons(n: int, today: date | None = None) -> list[str]:
    """Codes de saison (ex. '2627') de la plus récente à la plus ancienne ; une saison démarre en juillet."""
    today = today or date.today()
    y0 = today.year if today.month >= 7 else today.year - 1
    return [f"{(y % 100):02d}{((y + 1) % 100):02d}" for y in range(y0, y0 - n, -1)]


def url_for(code: str, season: str | None = None) -> str:
    if code in MAIN:
        if not season:
            raise SourceError("saison requise")
        return f"{BASE}/mmz4281/{season}/{code}.csv"
    if code in EXTRA:
        return f"{BASE}/new/{code}.csv"
    if code in CUPS:
        if not season:
            raise SourceError("saison requise")
        return f"{CUPS_BASE}/20{season[:2]}-{season[2:]}/{CUPS[code][2]}.txt"
    raise SourceError(f"Championnat inconnu : {code}")


def _allowed(url: str) -> bool:
    u = urlparse(url)
    if u.scheme != "https":
        return False
    return u.hostname in ALLOWED_HOSTS or (
        u.hostname == "raw.githubusercontent.com" and u.path.startswith("/openfootball/")
    )


def fetch_text(url: str, client: httpx.Client | None = None, attempts: int = 3) -> str | None:
    """Télécharge un fichier texte. None si absent (404). Nouvelles tentatives sur erreur réseau / 5xx / 429.
    Lève SourceError avec un message de diagnostic (adresse, code HTTP) sinon."""
    if not _allowed(url):
        raise SourceError("Domaine non autorisé.")
    own = client is None
    client = client or httpx.Client(
        timeout=30, headers={"User-Agent": USER_AGENT}, follow_redirects=False
    )
    short = url.split("//", 1)[1][:90]
    try:
        r = None
        for i in range(attempts):
            try:
                r = client.get(url)
            except httpx.HTTPError as e:
                if i == attempts - 1:
                    raise SourceError(
                        f"Téléchargement impossible ({type(e).__name__}) : {short} — vérifiez la connexion Internet."
                    ) from None
                time.sleep(1.5 * (i + 1))
                continue
            if r.status_code in (429, 500, 502, 503, 504) and i < attempts - 1:
                time.sleep(1.5 * (i + 1))
                continue
            break
    finally:
        if own:
            client.close()
    if r.status_code == 404:
        return None
    if r.status_code != 200:
        raise SourceError(f"Le site a répondu HTTP {r.status_code} : {short}")
    if len(r.content) > MAX_BYTES:
        raise SourceError("Fichier trop volumineux.")
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return r.content.decode(enc)
        except UnicodeDecodeError:
            continue
    raise SourceError("Encodage illisible.")


def _import(
    db: Session,
    text: str,
    label: str,
    user_id: int | None,
    source: str,
    since_year: int | None = None,
    url: str = "",
) -> dict:
    rep = import_csv(
        db,
        text,
        source=source,
        label=label,
        user_id=user_id,
        max_rows=200_000,
        since_year=since_year,
        tolerant=True,
    )
    if rep.errors:
        e = rep.errors[0]
        return {
            "label": label,
            "status": "erreur",
            "url": url,
            "format": rep.source_format,
            "message": f"fichier refusé : {len(rep.errors)} ligne(s) invalide(s), première → ligne {e['line']} : {e['error']}. Rien n'a été importé.",
        }
    return {
        "label": label,
        "status": "ok",
        "created": rep.created_matches,
        "updated": rep.updated_matches,
        "skipped": rep.skipped_duplicates,
        "ignored": rep.ignored_count,
        "ignored_sample": [f"ligne {e['line']} : {e['error']}" for e in rep.ignored[:3]],
        "auto_matched": rep.auto_matched,
        "warnings": rep.warnings,
        "batch_id": rep.batch_id,
        "format": rep.source_format,
    }


def _mark(db: Session, code: str, status: str) -> None:
    f = db.scalar(select(FollowedLeague).where(FollowedLeague.code == code))
    if f is None:
        f = FollowedLeague(code=code)
        db.add(f)
    f.last_update_at, f.last_status = utcnow(), status[:500]
    db.commit()


def add_league(
    db: Session,
    code: str,
    n_seasons: int = 3,
    user_id: int | None = None,
    client=None,
    pause: float = 1.0,
    today: date | None = None,
) -> list[dict]:
    """Télécharge et importe les n dernières saisons d'un championnat, puis le suit pour les mises à jour."""
    today = today or date.today()
    results = []
    if code in MAIN or code in CUPS:
        for i, ssn in enumerate(recent_seasons(n_seasons, today)):
            if i:
                time.sleep(pause)
            try:
                text = fetch_text(url_for(code, ssn), client)
            except SourceError as e:
                results.append({"label": f"{code} {ssn}", "status": "erreur", "message": str(e)})
                continue
            results.append(
                {"label": f"{code} {ssn}", "status": "absent"}
                if text is None
                else _import(db, text, f"{code} {ssn}", user_id, "download")
            )
    elif code in EXTRA:
        try:
            text = fetch_text(url_for(code), client)
        except SourceError as e:
            results.append({"label": code, "status": "erreur", "message": str(e)})
        else:
            results.append(
                {"label": code, "status": "absent"}
                if text is None
                else _import(
                    db, text, code, user_id, "download", since_year=today.year - n_seasons + 1
                )
            )
    else:
        raise SourceError(f"Championnat inconnu : {code}")
    ok = sum(r["status"] == "ok" for r in results)
    _mark(
        db,
        code,
        f"{ok}/{len(results)} fichier(s) importé(s)"
        + ("" if ok else " — " + "; ".join(r.get("message", r["status"]) for r in results)[:300]),
    )
    return results


def _only_divs(text: str, divs: set[str]) -> str:
    rows = list(csv.DictReader(io.StringIO(text.lstrip("﻿"))))
    if not rows:
        return text
    out = io.StringIO()
    w = csv.DictWriter(out, fieldnames=list(rows[0].keys()), lineterminator="\n")
    w.writeheader()
    w.writerows(r for r in rows if (r.get("Div") or "") in divs)
    return out.getvalue()


def update_all(
    db: Session,
    user_id: int | None = None,
    client=None,
    pause: float = 1.0,
    today: date | None = None,
    progress=None,
) -> list[dict]:
    """Met à jour les championnats suivis (résultats récents) et importe les prochains matchs avec leurs cotes."""
    today = today or date.today()
    followed = [f.code for f in db.scalars(select(FollowedLeague).order_by(FollowedLeague.code))]
    results: list[dict] = []
    n_main = (
        2 if today.month in (7, 8, 9) else 1
    )  # en début de saison, on rattrape aussi la précédente
    for i, code in enumerate(followed):
        if progress:
            progress(i, len(followed) + 1, f"Mise à jour {code}")
        sub = add_league(
            db, code, n_main if code in MAIN or code in CUPS else 2, user_id, client, pause, today
        )
        results += sub
        time.sleep(pause)
    divs = {c for c in followed if c in MAIN}
    if divs:
        if progress:
            progress(len(followed), len(followed) + 1, "Prochains matchs")
        try:
            text = fetch_text(f"{BASE}/fixtures.csv", client)
        except SourceError as e:
            results.append({"label": "prochains matchs", "status": "erreur", "message": str(e)})
        else:
            if text is None:
                results.append({"label": "prochains matchs", "status": "absent"})
            else:
                filtered = _only_divs(text, divs)
                results.append(
                    _import(db, filtered, "prochains matchs", user_id, "fixtures")
                    if filtered.count("\n") > 1
                    else {
                        "label": "prochains matchs",
                        "status": "ok",
                        "created": 0,
                        "updated": 0,
                        "skipped": 0,
                        "warnings": [],
                    }
                )
    return results
