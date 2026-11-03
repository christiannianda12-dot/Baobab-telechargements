"""Modèle de Poisson indépendant (attaque/défense par équipe, avantage du terrain).

Estimation : maximum a posteriori avec prior Gamma (rétrécissement vers la moyenne de la ligue, équivalent
à `shrink` matchs fictifs « moyens »), pondération temporelle exponentielle, correction itérative de la
force des adversaires. Aucune dépendance externe.

LIMITES (affichées à l'utilisateur) : buts supposés indépendants (pas de correction de Dixon-Coles : les
nuls et les scores faibles sont légèrement mal estimés) ; ni blessures, ni compositions, ni motivation ;
forme estimée sur une seule compétition ; fiabilité faible sous ~5 matchs par équipe.
"""

import math
from dataclasses import dataclass, field
from datetime import datetime

import numpy as np

from app.ml.data import Rec

MODEL_NAME = "poisson"
MODEL_VERSION = "1.0.0"
MIN_LEAGUE_MATCHES = 30
MIN_TEAM_MATCHES = 5
MAX_GOALS = 12
LIMITATIONS = [
    "Buts supposés indépendants (pas de correction de Dixon-Coles) : nuls et scores faibles approximatifs.",
    "N'intègre ni blessures, ni suspensions, ni compositions, ni motivation.",
    "Force des équipes estimée uniquement sur les matchs de cette compétition déjà enregistrés.",
    "Estimation statistique, jamais une certitude.",
]


@dataclass
class Fit:
    mu_home: float
    mu_away: float
    attack: dict[int, float]
    defense: dict[int, float]
    games: dict[int, int]
    n_matches: int
    params: dict = field(default_factory=dict)


def fit(
    recs: list[Rec],
    as_of: datetime,
    half_life_days: float = 365.0,
    shrink: float = 5.0,
    iters: int = 30,
) -> Fit:
    """Estimation vectorisée (numpy). Mêmes formules que la version itérative d'origine."""
    recs = [r for r in recs if r.when < as_of]  # garde-fou anti-fuite
    params = {"half_life_days": half_life_days, "shrink": shrink}
    if not recs:
        return Fit(0.0, 0.0, {}, {}, {}, 0, params)
    team_ids = sorted({t for r in recs for t in (r.home, r.away)})
    pos = {t: i for i, t in enumerate(team_ids)}
    T = len(team_ids)
    h = np.fromiter((pos[r.home] for r in recs), dtype=np.intp, count=len(recs))
    a = np.fromiter((pos[r.away] for r in recs), dtype=np.intp, count=len(recs))
    hg = np.fromiter((r.hg for r in recs), dtype=float, count=len(recs))
    ag = np.fromiter((r.ag for r in recs), dtype=float, count=len(recs))
    age = (
        np.fromiter(
            (max(as_of.timestamp() - r.when.timestamp(), 0.0) for r in recs),
            dtype=float,
            count=len(recs),
        )
        / 86400
    )
    w = 0.5 ** (age / half_life_days)
    sw = w.sum() or 1.0
    mu_h, mu_a = float((w * hg).sum() / sw), float((w * ag).sum() / sw)
    mu = (mu_h + mu_a) / 2 or 1.0
    bc = lambda idx, vals: np.bincount(idx, weights=vals, minlength=T)  # noqa: E731
    s_att, s_def = bc(h, w * hg) + bc(a, w * ag), bc(a, w * hg) + bc(h, w * ag)
    att, dfn = np.ones(T), np.ones(T)
    k = shrink * mu
    for _ in range(iters):
        e_att = bc(h, w * mu_h * dfn[a]) + bc(a, w * mu_a * dfn[h])
        e_def = bc(a, w * mu_h * att[h]) + bc(h, w * mu_a * att[a])
        att, dfn = (s_att + k) / (e_att + k), (s_def + k) / (e_def + k)  # mise à jour simultanée
    games = np.bincount(h, minlength=T) + np.bincount(a, minlength=T)
    return Fit(
        mu_h,
        mu_a,
        dict(zip(team_ids, att.tolist(), strict=True)),
        dict(zip(team_ids, dfn.tolist(), strict=True)),
        dict(zip(team_ids, games.tolist(), strict=True)),
        len(recs),
        params,
    )


def eligibility(f: Fit, home: int, away: int) -> str | None:
    """None si la prédiction est permise, sinon la raison du refus."""
    if f.n_matches < MIN_LEAGUE_MATCHES:
        return f"Historique insuffisant : {f.n_matches} match(s) terminé(s) dans cette compétition (minimum {MIN_LEAGUE_MATCHES})."
    for label, t in (("domicile", home), ("extérieur", away)):
        if f.games.get(t, 0) < MIN_TEAM_MATCHES:
            return f"Équipe {label} : {f.games.get(t, 0)} match(s) enregistré(s) avant celui-ci (minimum {MIN_TEAM_MATCHES})."
    return None


def expected_goals(f: Fit, home: int, away: int) -> tuple[float, float]:
    return (
        f.mu_home * f.attack[home] * f.defense[away],
        f.mu_away * f.attack[away] * f.defense[home],
    )


def _pmf(lam: float) -> list[float]:
    p = [math.exp(-lam)]
    for k in range(1, MAX_GOALS + 1):
        p.append(p[-1] * lam / k)
    s = sum(p)
    return [x / s for x in p]


def score_matrix(lh: float, la: float) -> list[list[float]]:
    ph, pa = _pmf(lh), _pmf(la)
    return [[x * y for y in pa] for x in ph]


def markets(lh: float, la: float) -> dict:
    m = score_matrix(lh, la)
    n = range(MAX_GOALS + 1)
    home = sum(m[i][j] for i in n for j in n if i > j)
    draw = sum(m[i][i] for i in n)
    away = 1.0 - home - draw
    total = {k: sum(m[i][j] for i in n for j in n if i + j == k) for k in range(2 * MAX_GOALS + 1)}
    ou = {}
    for line in (0.5, 1.5, 2.5, 3.5, 4.5):
        over = sum(p for k, p in total.items() if k > line)
        ou[str(line)] = {"over": over, "under": 1.0 - over}
    btts = 1.0 - sum(m[0][j] for j in n) - sum(m[i][0] for i in n) + m[0][0]
    top = sorted(((m[i][j], i, j) for i in n for j in n), reverse=True)[:5]
    return {
        "1X2": {"home": home, "draw": draw, "away": away},
        "DC": {"1X": home + draw, "12": home + away, "X2": draw + away},
        "OU": ou,
        "BTTS": {"yes": btts, "no": 1.0 - btts},
        "exact_scores": [{"score": f"{i}-{j}", "probability": p} for p, i, j in top],
    }
