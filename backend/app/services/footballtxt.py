"""Analyseur du format Football.TXT (openfootball, domaine public) pour les coupes UEFA.

Exemple :  « ▪ League, Matchday 1 / Tue Sep 16 2025 / 21:00 Juventus FC (ITA) v Borussia Dortmund (GER) 4-4 (0-0) »
Le score retenu est celui des 90 minutes (prolongations et tirs au but exclus), cohérent avec le modèle statistique.
Un match sans score reste « programmé » s'il est à venir ; sinon la ligne est signalée (reporté / résultat absent)."""

import csv
import io
import re
from datetime import date

MONTHS = {
    m: i
    for i, m in enumerate(
        ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1
    )
}
DATE_RE = re.compile(
    r"^\s+(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+([A-Z][a-z]{2})\s+(\d{1,2})(?:\s+(\d{4}))?\s*$"
)
MATCH_RE = re.compile(r"^\s*(?:(\d{1,2})[:.](\d{2})\s+)?(.+?)\s+v\s+(.+?)\s*$")
COUNTRY_END = re.compile(r"^(.*?\([A-Za-z]{2,3}\))\s*(.*)$")
SCORE_RE = re.compile(
    r"^(\d+)-(\d+)(?:\s+pen\.\s+\d+-\d+\s+a\.e\.t\.)?(?:\s+a\.e\.t\.)?(?:\s*\(([^)]*)\))?"
)
CODE_RE = re.compile(r"\s*\([A-Za-z]{2,3}\)\s*$")


def sniff(text: str) -> bool:
    first = next((ln for ln in text.lstrip("\ufeff").split("\n") if ln.strip()), "")
    return first.startswith("=") and " v " in text[:20000]


def _scores(tail: str) -> tuple[int, int, int | None, int | None] | None:
    """Retourne (dom, ext, mt_dom, mt_ext) sur 90 minutes, ou None si pas de score exploitable."""
    tail = tail.split(" @ ")[0].strip()
    m = SCORE_RE.match(tail)
    if not m:
        return None
    a, b, paren = int(m[1]), int(m[2]), m[3]
    parts = [p.strip() for p in paren.split(",")] if paren else []
    aet = "a.e.t." in tail
    ft = (a, b)
    ht = None
    if aet and parts and re.fullmatch(r"\d+-\d+", parts[0]):
        ft = tuple(int(x) for x in parts[0].split("-"))  # score après 90 min
        parts = parts[1:]
    if parts and re.fullmatch(r"\d+-\d+", parts[0]):
        ht = tuple(int(x) for x in parts[0].split("-"))
    return ft[0], ft[1], ht[0] if ht else None, ht[1] if ht else None


def to_native_csv(text: str, today: date | None = None) -> str:
    today = today or date.today()
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    w.writerow(
        [
            "date",
            "competition",
            "season",
            "home_team",
            "away_team",
            "home_score",
            "away_score",
            "home_score_ht",
            "away_score_ht",
        ]
    )
    comp, season, year, last_month, time_ = "", "", None, None, "12:00"
    for line in text.lstrip("\ufeff").split("\n"):
        if line.startswith("="):
            title = line.lstrip("= ").strip()
            ms = re.search(r"(\d{4})/(\d{2,4})\s*$", title)
            if ms:
                y1 = int(ms[1])
                y2 = int(ms[2]) if len(ms[2]) == 4 else (y1 // 100) * 100 + int(ms[2])
                season, comp = f"{y1}-{y2}", title[: ms.start()].strip()
            else:
                comp = title
            continue
        md = DATE_RE.match(line)
        if md:
            mon, day = MONTHS.get(md[1]), int(md[2])
            if mon is None:
                continue
            if md[3]:
                year = int(md[3])
            elif year is None and season:
                year = int(season[:4]) if mon >= 7 else int(season[:4]) + 1
            elif last_month is not None and mon < last_month:
                year = (year or 0) + 1  # passage décembre -> janvier
            last_month = mon
            cur_date = f"{year:04d}-{mon:02d}-{day:02d}" if year else ""
            time_ = "12:00"
            continue
        mm = MATCH_RE.match(line)
        if not mm or not comp:
            continue
        if mm[1]:
            time_ = f"{int(mm[1]):02d}:{mm[2]}"
        home, rest = mm[3].strip(), mm[4].strip()
        c = COUNTRY_END.match(rest)
        away, tail = (
            (c[1], c[2])
            if c
            else (
                re.split(r"\s{2,}", rest, maxsplit=1)[0],
                (re.split(r"\s{2,}", rest, maxsplit=1) + [""])[1],
            )
        )
        home, away = CODE_RE.sub("", home).strip(), CODE_RE.sub("", away).strip()
        sc = _scores(tail)
        w.writerow(
            [f"{cur_date}T{time_}:00Z", comp, season, home, away, *(sc if sc else ("", "", "", ""))]
            if sc
            else [f"{cur_date}T{time_}:00Z", comp, season, home, away, "", "", "", ""]
        )
    return out.getvalue()
