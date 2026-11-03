"""Adaptateurs de formats CSV d'historique vers le format natif de PREDIX AI.

Format reconnu : football-data.co.uk (colonnes Date, HomeTeam, AwayTeam, FTHG, FTAG, ...). Les cotes de ce
format sont ignorées à l'import (non utilisées par le moteur). Aucune valeur n'est inventée : une colonne
absente reste vide. Les heures (fuseau local britannique dans la source) sont traitées comme UTC ; sans heure,
12:00 UTC est utilisé — sans effet sur les statistiques, seulement sur l'ordre des matchs d'un même jour.
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
    "SC0": "Premiership (Écosse)",
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
NATIVE_HEAD = [
    "date",
    "competition",
    "season",
    "home_team",
    "away_team",
    "home_score",
    "away_score",
]


def sniff(text: str) -> str:
    first = text.lstrip("﻿").split("\n", 1)[0]
    cols = {c.strip() for c in re.split(r"[;,]", first)}
    return (
        "football-data"
        if {"HomeTeam", "AwayTeam", "FTHG", "FTAG"} <= cols
        or {"HomeTeam", "AwayTeam", "HG", "AG"} <= cols
        else "native"
    )


def _iso_date(raw: str) -> str:
    raw = raw.strip()
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{2}|\d{4})", raw)
    if not m:
        return raw  # laissé tel quel : l'import natif signalera la ligne invalide
    d, mo, y = int(m[1]), int(m[2]), int(m[3])
    y += 2000 if y < 100 and y < 70 else 1900 if y < 100 else 0
    return date(y, mo, d).isoformat()


def season_of(iso_date: str) -> str:
    y, mth = int(iso_date[:4]), int(iso_date[5:7])
    return f"{y}-{y + 1}" if mth >= 7 else f"{y - 1}-{y}"


def to_native(
    text: str, competition: str | None = None, season: str | None = None
) -> tuple[str, str]:
    """Retourne (csv_natif, format_détecté). Un CSV déjà natif est renvoyé inchangé."""
    if sniff(text) == "native":
        return text, "native"
    text = text.lstrip("﻿")
    delim = ";" if text.split("\n", 1)[0].count(";") > text.split("\n", 1)[0].count(",") else ","
    rows = list(csv.DictReader(io.StringIO(text), delimiter=delim))
    extra = [c for c in STATS.values()]
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    w.writerow(NATIVE_HEAD + extra)
    for r in rows:
        r = {(k or "").strip(): (v or "").strip() for k, v in r.items()}
        if not r.get("HomeTeam") and not r.get("AwayTeam"):
            continue  # ligne vide de fin de fichier
        hg, ag = r.get("FTHG", r.get("HG", "")), r.get("FTAG", r.get("AG", ""))
        iso = _iso_date(r.get("Date", ""))
        when = (
            f"{iso}T{r['Time']}:00Z"
            if r.get("Time") and re.fullmatch(r"\d{1,2}:\d{2}", r["Time"])
            else (f"{iso}T12:00:00Z" if re.fullmatch(r"\d{4}-\d{2}-\d{2}", iso) else iso)
        )
        comp = competition or DIVISIONS.get(r.get("Div", ""), r.get("Div", ""))
        ssn = season or (season_of(iso) if re.fullmatch(r"\d{4}-\d{2}-\d{2}", iso) else "")
        w.writerow(
            [when, comp, ssn, r.get("HomeTeam", ""), r.get("AwayTeam", ""), hg, ag]
            + [r.get(k, "") for k in STATS]
        )
    return out.getvalue(), "football-data"
