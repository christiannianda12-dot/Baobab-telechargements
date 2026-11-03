"""Normalisation de noms (équipes, championnats) : insensible à la casse, aux accents, à la ponctuation."""

import re
import unicodedata


def norm_key(name: str) -> str:
    s = unicodedata.normalize("NFKD", name.strip().casefold())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^\w\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


NOISE = {"fc", "cf", "afc", "sc", "ssc", "acf", "ss", "club", "de", "del", "the", "calcio"}
# nom (normalisé) tel qu'écrit par les sources de coupes -> nom (normalisé) tel qu'écrit par football-data.co.uk
KNOWN_ALIASES = {
    "club atletico de madrid": "ath madrid",
    "atletico madrid": "ath madrid",
    "athletic club": "ath bilbao",
    "paris saint germain": "paris sg",
    "paris saint germain fc": "paris sg",
    "fc bayern munchen": "bayern munich",
    "bayern munchen": "bayern munich",
    "fc internazionale milano": "inter",
    "internazionale milano": "inter",
    "ac milan": "milan",
    "borussia dortmund": "dortmund",
    "bayer 04 leverkusen": "leverkusen",
    "eintracht frankfurt": "ein frankfurt",
    "borussia monchengladbach": "m gladbach",
    "real betis balompie": "betis",
    "real betis": "betis",
    "real sociedad de futbol": "sociedad",
    "real sociedad": "sociedad",
    "sporting clube de portugal": "sp lisbon",
    "sporting cp": "sp lisbon",
    "sport lisboa e benfica": "benfica",
    "olympique de marseille": "marseille",
    "olympique lyonnais": "lyon",
    "as monaco fc": "monaco",
    "as monaco": "monaco",
    "lille osc": "lille",
    "stade rennais fc": "rennes",
    "ogc nice": "nice",
    "rc lens": "lens",
    "newcastle united fc": "newcastle",
    "newcastle united": "newcastle",
    "tottenham hotspur fc": "tottenham",
    "tottenham hotspur": "tottenham",
    "west ham united fc": "west ham",
    "wolverhampton wanderers fc": "wolves",
    "nottingham forest fc": "nott m forest",
    "nottingham forest": "nott m forest",
    "brighton hove albion fc": "brighton",
    "leicester city fc": "leicester",
    "afc bournemouth": "bournemouth",
    "ssc napoli": "napoli",
    "as roma": "roma",
    "ss lazio": "lazio",
    "atalanta bc": "atalanta",
    "acf fiorentina": "fiorentina",
    "vfb stuttgart": "stuttgart",
    "1899 hoffenheim": "hoffenheim",
    "tsg 1899 hoffenheim": "hoffenheim",
    "psv": "psv eindhoven",
    "afc ajax": "ajax",
    "feyenoord rotterdam": "feyenoord",
    "club brugge kv": "club brugge",
    "galatasaray sk": "galatasaray",
    "fenerbahce sk": "fenerbahce",
    "pae olympiakos sfp": "olympiacos",
    "olympiakos piraeus": "olympiacos",
    "celtic fc": "celtic",
    "rangers fc": "rangers",
    "manchester city fc": "man city",
    "manchester united fc": "man united",
    "manchester united": "man united",
    "manchester city": "man city",
    "sevilla fc": "sevilla",
    "valencia cf": "valencia",
    "villarreal cf": "villarreal",
    "fc barcelona": "barcelona",
    "real madrid cf": "real madrid",
    "juventus fc": "juventus",
    "chelsea fc": "chelsea",
    "arsenal fc": "arsenal",
    "liverpool fc": "liverpool",
    "aston villa fc": "aston villa",
    "fc porto": "porto",
    "sl benfica": "benfica",
    "rb leipzig": "rb leipzig",
    "sv werder bremen": "werder bremen",
    "fc augsburg": "augsburg",
}


def strip_key(key: str) -> str:
    return " ".join(t for t in key.split() if t not in NOISE) or key


def abbreviation(ka: str, kb: str) -> bool:
    """« man utd » ~ « manchester utd » : mêmes mots, chacun étant le début de l'autre (>= 3 lettres)."""
    ta, tb = ka.split(), kb.split()
    return len(ta) == len(tb) >= 2 and all(
        min(len(x), len(y)) >= 3 and (x.startswith(y) or y.startswith(x))
        for x, y in zip(ta, tb, strict=True)
    )


def resolve_existing(key: str, known: dict) -> tuple[object, str] | None:
    """Retrouve une équipe déjà connue sous un autre libellé. Retourne (équipe, règle) ou None.
    Règles prudentes, dans l'ordre : nom exact, table d'alias connus, mêmes mots hors « FC/CF/Club… », abréviation (unique)."""
    if key in known:
        return known[key], "exact"
    if (target := KNOWN_ALIASES.get(key)) and target in known:
        return known[target], "alias connu"
    sk = strip_key(key)
    same = {id(known[k]): known[k] for k in known if strip_key(k) == sk}
    if len(same) == 1:
        return next(iter(same.values())), "même nom hors préfixe/suffixe"
    abbr = {id(known[k]): known[k] for k in known if abbreviation(sk, strip_key(k))}
    if len(abbr) == 1:
        return next(iter(abbr.values())), "abréviation"
    return None
