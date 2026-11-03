"""Analyse de combinés.

Probabilité conjointe :
- sélections de MATCHS DIFFÉRENTS : supposées indépendantes (produit). Hypothèse simplificatrice, énoncée à l'utilisateur ;
- sélections du MÊME match : calculées exactement sur la matrice de scores du modèle (jamais un simple produit) ;
- sélections incompatibles (ex. victoire domicile ET victoire extérieur) : probabilité 0, combiné invalide.
"""

from collections import defaultdict

from sqlalchemy.orm import Session

from app.ml import poisson
from app.models import Match
from app.services.predict import build_prediction

MAX_LEGS = 8
LABELS = {
    "home": "victoire domicile",
    "draw": "match nul",
    "away": "victoire extérieur",
    "over": "plus de",
    "under": "moins de",
    "yes": "les deux équipes marquent",
    "no": "au moins une équipe ne marque pas",
    "1X": "domicile ou nul",
    "12": "domicile ou extérieur",
    "X2": "nul ou extérieur",
}


def predicate(market: str, sel: str, line: float | None):
    """Fonction (buts_dom, buts_ext) -> bool pour une sélection, ou ValueError si non supportée."""
    if market == "1X2":
        return {
            "home": lambda i, j: i > j,
            "draw": lambda i, j: i == j,
            "away": lambda i, j: i < j,
        }[sel]
    if market == "DC":
        return {"1X": lambda i, j: i >= j, "12": lambda i, j: i != j, "X2": lambda i, j: i <= j}[
            sel
        ]
    if market == "OU" and line in (0.5, 1.5, 2.5, 3.5, 4.5):
        return (lambda i, j: i + j > line) if sel == "over" else (lambda i, j: i + j < line)
    if market == "BTTS":
        return (lambda i, j: i > 0 and j > 0) if sel == "yes" else (lambda i, j: i == 0 or j == 0)
    raise ValueError("unsupported")


def describe(market: str, sel: str, line: float | None) -> str:
    if market == "OU":
        return f"{LABELS[sel]} {line} buts"
    return LABELS.get(sel, sel)


def _prob(matrix, preds) -> float:
    return sum(
        p for i, row in enumerate(matrix) for j, p in enumerate(row) if all(f(i, j) for f in preds)
    )


def analyze(db: Session, legs: list[dict]) -> dict:
    """legs : [{match_id, market, selection, line}] -> analyse complète (ou 'invalid' avec raisons)."""
    if not legs:
        return {"valid": False, "problems": ["Aucune sélection."]}
    problems: list[str] = []
    if len(legs) > MAX_LEGS:
        return {"valid": False, "problems": [f"Maximum {MAX_LEGS} sélections."]}
    if len({(g["match_id"], g["market"], g["selection"], g.get("line")) for g in legs}) < len(legs):
        return {"valid": False, "problems": ["Sélection en double."]}

    cache: dict[int, dict] = {}
    by_match: dict[int, list] = defaultdict(list)
    out_legs = []
    for g in legs:
        mid = g["match_id"]
        if mid not in cache:
            m = db.get(Match, mid)
            if m is None:
                problems.append(f"Match {mid} introuvable.")
                continue
            cache[mid] = {"match": m, "pred": build_prediction(db, m)}
        pred = cache[mid]["pred"]
        if not pred["available"]:
            problems.append(f"Match {mid} : {pred['reason']}")
            continue
        try:
            f = predicate(g["market"], g["selection"], g.get("line"))
        except (ValueError, KeyError):
            problems.append(
                f"Match {mid} : sélection non supportée ({g['market']} {g['selection']} {g.get('line') or ''})."
            )
            continue
        lh, la = pred["lambdas"]
        matrix = poisson.score_matrix(lh, la)
        p = _prob(matrix, [f])
        # cote retenue : la meilleure saisie pour cette sélection
        prices = [
            v["price"]
            for v in pred["value"]
            if (v["market"], v["selection"], v["line"])
            == (g["market"], g["selection"], g.get("line"))
        ]
        price = max(prices) if prices else None
        by_match[mid].append((f, matrix))
        out_legs.append(
            {
                "match_id": mid,
                "market": g["market"],
                "selection": g["selection"],
                "line": g.get("line"),
                "label": describe(g["market"], g["selection"], g.get("line")),
                "probability": p,
                "odds": price,
                "training_matches": pred["training"]["matches"],
                "expected_goals": pred["expected_goals"],
            }
        )
    if problems:
        return {"valid": False, "problems": problems}

    joint, groups = 1.0, []
    for mid, items in by_match.items():
        gp = _prob(items[0][1], [f for f, _ in items])
        joint *= gp
        if len(items) > 1:
            naive = 1.0
            for leg in (leg for leg in out_legs if leg["match_id"] == mid):
                naive *= leg["probability"]
            groups.append(
                {
                    "match_id": mid,
                    "legs": len(items),
                    "joint_probability": gp,
                    "naive_product": naive,
                }
            )
    naive_all = 1.0
    for leg in out_legs:
        naive_all *= leg["probability"]

    warnings = []
    if joint == 0:
        return {
            "valid": False,
            "problems": ["Sélections incompatibles : leur probabilité conjointe est nulle."],
            "legs": out_legs,
        }
    for gr in groups:
        warnings.append(
            f"Match {gr['match_id']} : {gr['legs']} sélections corrélées. Probabilité conjointe exacte du modèle "
            f"{gr['joint_probability']:.1%} (le produit naïf donnerait {gr['naive_product']:.1%}). "
            "Les bookmakers appliquent une cote spécifique à ces combinaisons : le produit des cotes simples ne les reflète pas."
        )
    if len(out_legs) > 4:
        warnings.append(
            f"{len(out_legs)} sélections : la probabilité conjointe s'effondre avec le nombre de jambes."
        )
    if joint < 0.10:
        warnings.append(
            f"Combiné très risqué : probabilité conjointe estimée {joint:.1%} (< 10 %)."
        )
    if any(leg["training_matches"] < 60 for leg in out_legs):
        warnings.append(
            "Au moins une sélection repose sur un historique court (< 60 matchs) : incertitude élevée."
        )
    warnings.append("Hypothèse : les matchs différents sont supposés indépendants.")

    all_odds = all(leg["odds"] for leg in out_legs)
    total_odds = None
    ev = None
    if all_odds:
        total_odds = 1.0
        for leg in out_legs:
            total_odds *= leg["odds"]
        ev = joint * total_odds - 1.0
        if groups:
            warnings.append(
                "Cote totale = produit des cotes saisies ; non applicable telle quelle aux sélections d'un même match."
            )
    else:
        warnings.append("Cote totale non calculée : au moins une sélection n'a pas de cote saisie.")
    return {
        "valid": True,
        "legs": out_legs,
        "joint_probability": joint,
        "naive_product": naive_all,
        "total_odds": total_odds,
        "expected_value": ev,
        "same_match_groups": groups,
        "warnings": warnings,
        "model": f"{poisson.MODEL_NAME}-{poisson.MODEL_VERSION}",
    }


CANDIDATES = [
    ("1X2", "home", None),
    ("1X2", "away", None),
    ("DC", "1X", None),
    ("DC", "X2", None),
    ("DC", "12", None),
    ("OU", "over", 2.5),
    ("OU", "under", 2.5),
    ("OU", "over", 1.5),
    ("BTTS", "yes", None),
    ("BTTS", "no", None),
]


def suggest(db: Session, match_ids: list[int], size: int, min_probability: float = 0.0) -> dict:
    """Pour chaque match, la sélection la plus probable (une seule par match => pas de corrélation interne) ;
    garde les `size` matchs les plus probables. Privilégie la probabilité, pas la valeur."""
    picks, skipped = [], []
    for mid in match_ids:
        m = db.get(Match, mid)
        if m is None:
            skipped.append({"match_id": mid, "reason": "introuvable"})
            continue
        pred = build_prediction(db, m)
        if not pred["available"]:
            skipped.append({"match_id": mid, "reason": pred["reason"]})
            continue
        lh, la = pred["lambdas"]
        matrix = poisson.score_matrix(lh, la)
        market, sel, line = max(CANDIDATES, key=lambda c: _prob(matrix, [predicate(*c)]))
        picks.append(
            (
                {"match_id": mid, "market": market, "selection": sel, "line": line},
                _prob(matrix, [predicate(market, sel, line)]),
            )
        )
    picks = [p for p in picks if p[1] >= min_probability]
    picks.sort(key=lambda x: -x[1])
    chosen = [p[0] for p in picks[:size]]
    if len(chosen) < size:
        return {
            "valid": False,
            "problems": [f"Seulement {len(chosen)} match(s) éligible(s) sur {size} demandés."],
            "skipped": skipped,
            "legs": [],
        }
    res = analyze(db, chosen)
    res["skipped"] = skipped
    res["selection_rule"] = (
        "Sélection la plus probable de chaque match, matchs les plus probables retenus (aucune recherche de valeur)."
    )
    return res
