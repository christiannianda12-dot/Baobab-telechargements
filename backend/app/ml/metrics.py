"""Mesures de qualité probabiliste. Les probabilités sont des triplets (home, draw, away)."""

import math

Probs = tuple[float, float, float]
EPS = 1e-12


def outcome_index(hg: int, ag: int) -> int:
    return 0 if hg > ag else 1 if hg == ag else 2


def brier(probs: list[Probs], outcomes: list[int]) -> float:
    """Brier multiclasse (0 = parfait ; 2/3 = prédiction uniforme à 3 issues)."""
    tot = 0.0
    for p, o in zip(probs, outcomes, strict=True):
        tot += sum((p[i] - (1.0 if i == o else 0.0)) ** 2 for i in range(3))
    return tot / len(probs)


def log_loss(probs: list[Probs], outcomes: list[int]) -> float:
    return -sum(math.log(max(p[o], EPS)) for p, o in zip(probs, outcomes, strict=True)) / len(probs)


def calibration_bins(p: list[float], hit: list[bool], bins: int = 5) -> list[dict]:
    """Table de fiabilité : probabilité moyenne annoncée vs fréquence observée, par tranche."""
    out = []
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        idx = [i for i, x in enumerate(p) if lo <= x < hi or (b == bins - 1 and x == 1.0)]
        if idx:
            out.append(
                {
                    "range": f"{lo:.1f}-{hi:.1f}",
                    "n": len(idx),
                    "mean_predicted": sum(p[i] for i in idx) / len(idx),
                    "observed_frequency": sum(hit[i] for i in idx) / len(idx),
                }
            )
    return out
