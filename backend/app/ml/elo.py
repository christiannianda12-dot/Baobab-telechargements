"""Classement Elo (force relative). Sert de classement et d'indicateur ; les probabilités de résultat
proviennent du modèle de Poisson (Elo seul ne modélise pas le nul)."""

import math

from app.ml.data import Rec

INITIAL = 1500.0


def expected_score(r_home: float, r_away: float, home_adv: float = 60.0) -> float:
    return 1.0 / (1.0 + 10 ** (-(r_home + home_adv - r_away) / 400.0))


def ratings(recs: list[Rec], k: float = 20.0, home_adv: float = 60.0) -> dict[int, float]:
    r: dict[int, float] = {}
    for m in sorted(recs, key=lambda x: x.when):
        rh, ra = r.setdefault(m.home, INITIAL), r.setdefault(m.away, INITIAL)
        e = expected_score(rh, ra, home_adv)
        s = 1.0 if m.hg > m.ag else 0.5 if m.hg == m.ag else 0.0
        g = 1.0 + math.log1p(abs(m.hg - m.ag)) * 0.5  # marge de victoire, modérée
        d = k * g * (s - e)
        r[m.home], r[m.away] = rh + d, ra - d  # somme nulle
    return r
