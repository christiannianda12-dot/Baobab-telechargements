"""Adaptateurs de formats CSV d'historique vers le format natif de PREDIX AI.

Formats reconnus (football-data.co.uk) :
- « principal » : Date, HomeTeam, AwayTeam, FTHG, FTAG (+ stats, cotes) — un fichier par championnat et par saison ;
- « autres pays » : Country, League, Season, Date, Home, Away, HG, AG (+ cotes) — toutes saisons dans un fichier ;
- « prochains matchs » : Date, HomeTeam, AwayTeam sans score, avec cotes avant-match.
Aucune valeur n'est inventée : une colonne absente reste vide. Heures traitées comme UTC ; sans heure, 12:00 UTC.
"""

import csv
import io
import re
from datetime import date

DIVISIONS = {
    "E0": "Premier League (Angleterre)",
    "E1": "Championship (Angleterre)",
    "E2": "League One (Angleterre)",
    "E3": "League Two (Angleterre)",
    "EC": "National League (Angleterre)",
    "SC0": "Premiership (Écosse)",
    "SC1": "Championship (Écosse)",
    "SC2": "League One (Écosse)",
    "SC3": "League Two (Écosse)",
    "D1": "Bundesliga (Allemagne)",
    "D2": "2. Bundesliga (Allemagne)",
    "I1": "Serie A (Italie)",
    "I2": "Serie B (Italie)",
    "SP1": "La Liga (Espagne)",
    "SP2": "La Liga 2 (Espagne)",
    "F1": "Ligue 1 (France)",
    "F2": "Ligue 2 (France)",
    "N1": "Eredivisie (Pays-Bas)",
    "B1": "Jupiler Pro League (Belgique)",
    "P1": "Liga Portugal (Portugal)",
    "T1": "Süper Lig (Turquie)",
    "G1": "Super League (Grèce)",
}
# colonne football-data -> colonne native
STATS = {
    "HS": "home_shots",
    "AS": "away_shots",
    "HST": "home_shots_on_target",
    "AST": "away_shots_on_target",
    "HC": "home_corners",
    "AC": "away_corners",
    "HF": "home_fouls",
    "AF": "away_fouls",
    "HY": "home_yellow",
    "AY": "away_yellow",
    "HR": "home_red",
    "AR": "away_red",
    "HTHG": "home_score_ht",
    "HTAG": "away_score_ht",
}
CLOSE_COLS = ["close_home", "close_draw", "close_away"]
PRE_COLS = ["pre_home", "pre_draw", "pre_away"]
CLOSE_SOURCES = [
    ("AvgCH", "AvgCD", "AvgCA"),
    ("B365CH", "B365CD", "B365CA"),
]  # moyenne marché, sinon Bet365
PRE_SOURCES = [("AvgH", "AvgD", "AvgA"), ("B365H", "B365D", "B365A")]
# colonnes football-data -> bookmaker affiché (seulement les libellés certains)
BOOKS = {
    "B365": "Bet365",
    "BW": "Bwin",
    "BV": "BetVictor",
    "BFD": "Betfred",
    "SKB": "Sky Bet",
    "PS": "Pinnacle",
    "WH": "William Hill",
    "IW": "Interwetten",
    "VC": "VC Bet",
    "Max": "Meilleure cote du marché",
    "Avg": "Moyenne du marché",
}


def _extra_odds(r: dict) -> str:
    """Cotes 1X2 et plus/moins 2,5 de tous les bookmakers présents, en JSON (colonne odds_extra)."""
    import json

    out = []
    for code, label in BOOKS.items():
        for suf, sel in (("H", "home"), ("D", "draw"), ("A", "away")):
            v = r.get(f"{code}{suf}")
            if v:
                out.append({"b": label, "m": "1X2", "s": sel, "l": None, "p": v})
        for sym, sel in ((">2.5", "over"), ("<2.5", "under")):
            v = r.get(f"{code}{sym}")
            if v:
                out.append({"b": label, "m": "OU", "s": sel, "l": 2.5, "p": v})
    return json.dumps(out, separators=(",", ":")) if out else ""


NATIVE_HEAD = [
    "date",
    "competition",
    "season",
    "home_team",
    "away_team",
    "home_score",
    "away_score",
]


def _cols(text: str) -> set[str]:
    first = text.lstrip("﻿").split("\n", 1)[0]
    return {c.strip() for c in re.split(r"[;,]", first)}


def sniff(text: str) -> str:
    from app.services import footballtxt

    if footballtxt.sniff(text):
        return "football-txt"
    c = _cols(text)
    if {"HomeTeam", "AwayTeam", "FTHG", "FTAG"} <= c or {"HomeTeam", "AwayTeam", "HG", "AG"} <= c:
        return "football-data"
    if {"Home", "Away", "HG", "AG", "Date"} <= c:
        return "football-data-extra"
    if {"HomeTeam", "AwayTeam", "Date"} <= c:
        return "football-data-fixtures"
    return "native"


def _iso_date(raw: str) -> str:
    raw = raw.strip()
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{2}|\d{4})", raw)
    if not m:
        return raw  # laissé tel quel : l'import natif signalera la ligne invalide
    d, mo, y = int(m[1]), int(m[2]), int(m[3])
    y += 2000 if y < 100 and y < 70 else 1900 if y < 100 else 0
    try:
        return date(y, mo, d).isoformat()
    except ValueError:
        return raw


def season_of(iso_date: str) -> str:
    y, mth = int(iso_date[:4]), int(iso_date[5:7])
    return f"{y}-{y + 1}" if mth >= 7 else f"{y - 1}-{y}"


def _when(iso: str, time_: str | None) -> str:
    if time_ and re.fullmatch(r"\d{1,2}:\d{2}", time_):
        return f"{iso}T{time_}:00Z"
    return f"{iso}T12:00:00Z" if re.fullmatch(r"\d{4}-\d{2}-\d{2}", iso) else iso


def _first(r: dict, groups) -> list[str]:
    return next(
        ([r[c] for c in cols] for cols in groups if all(r.get(c) for c in cols)), ["", "", ""]
    )


def to_native(
    text: str,
    competition: str | None = None,
    season: str | None = None,
    since_year: int | None = None,
) -> tuple[str, str]:
    """Retourne (csv_natif, format_détecté). Un CSV déjà natif est renvoyé inchangé.
    since_year : ne garde que les matchs dont l'année >= since_year (fichiers « autres pays » multi-saisons)."""
    fmt = sniff(text)
    if fmt == "native":
        return text, "native"
    if fmt == "football-txt":
        from app.services import footballtxt

        return footballtxt.to_native_csv(text), fmt
    text = text.lstrip("﻿")
    first = text.split("\n", 1)[0]
    delim = ";" if first.count(";") > first.count(",") else ","
    rows = list(csv.DictReader(io.StringIO(text), delimiter=delim))
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    w.writerow(NATIVE_HEAD + list(STATS.values()) + CLOSE_COLS + PRE_COLS + ["odds_extra"])
    for r in rows:
        r = {(k or "").strip(): (v or "").strip() for k, v in r.items()}
        home, away = r.get("HomeTeam") or r.get("Home", ""), r.get("AwayTeam") or r.get("Away", "")
        if not home and not away:
            continue  # ligne vide de fin de fichier
        iso = _iso_date(r.get("Date", ""))
        ok_date = bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", iso))
        if since_year and ok_date and int(iso[:4]) < since_year:
            continue
        if fmt == "football-data-extra":
            comp = competition or f"{r.get('League', '')} ({r.get('Country', '')})".strip()
            ssn = season or r.get("Season", "").replace("/", "-")
            hg, ag = r.get("HG", ""), r.get("AG", "")
            close = _first(r, [("AvgH", "AvgD", "AvgA")])
            stats = [""] * len(STATS)
        else:
            comp = competition or DIVISIONS.get(r.get("Div", ""), r.get("Div", ""))
            ssn = season or (season_of(iso) if ok_date else "")
            hg, ag = (
                (r.get("FTHG", r.get("HG", "")), r.get("FTAG", r.get("AG", "")))
                if fmt == "football-data"
                else ("", "")
            )
            close = _first(r, CLOSE_SOURCES) if fmt == "football-data" else ["", "", ""]
            stats = [r.get(k, "") for k in STATS] if fmt == "football-data" else [""] * len(STATS)
        extra = _extra_odds(r) if fmt == "football-data-fixtures" else ""
        w.writerow(
            [_when(iso, r.get("Time")), comp, ssn, home, away, hg, ag]
            + stats
            + close
            + [""] * 3
            + [extra]
        )
    return out.getvalue(), fmt
