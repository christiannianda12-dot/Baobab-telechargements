"""Données SYNTHÉTIQUES pour les tests uniquement (jamais insérées dans l'application)."""

import math
import random
from datetime import UTC, datetime, timedelta

from app.ml.data import Rec


def _poisson(rng: random.Random, lam: float) -> int:
    limit, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= limit:
            return k
        k += 1


def league(n_teams=16, seed=7, spread=0.35, home_boost=1.25) -> tuple[list[Rec], dict[int, float]]:
    rng = random.Random(seed)
    att = {t: math.exp(rng.gauss(0, spread)) for t in range(1, n_teams + 1)}
    dfn = {t: math.exp(rng.gauss(0, spread)) for t in range(1, n_teams + 1)}
    pairs = [(h, a) for h in att for a in att if h != a]
    rng.shuffle(pairs)
    t0, recs = datetime(2025, 8, 1, tzinfo=UTC), []
    for i, (h, a) in enumerate(pairs):
        recs.append(
            Rec(
                t0 + timedelta(days=i // 4, hours=i % 4),
                h,
                a,
                _poisson(rng, 1.35 * home_boost * att[h] * dfn[a]),
                _poisson(rng, 1.35 * att[a] * dfn[h]),
            )
        )
    strength = {t: att[t] / dfn[t] for t in att}
    return recs, strength
