"""Backtest chronologique (walk-forward) : chaque match est prédit avec les SEULS matchs antérieurs."""

from app.ml import metrics, poisson
from app.ml.data import Rec


def walk_forward(recs: list[Rec], max_matches: int = 2000, **fit_kw) -> list[dict]:
    """Prédit chaque match avec les seuls matchs antérieurs. Retourne une entrée par match évaluable."""
    recs = sorted(recs, key=lambda r: r.when)[-max_matches:]
    out = []
    for i, r in enumerate(recs):
        past = [x for x in recs[:i] if x.when < r.when]
        f = poisson.fit(past, r.when, **fit_kw)
        if poisson.eligibility(f, r.home, r.away):
            continue
        mk = poisson.markets(*poisson.expected_goals(f, r.home, r.away))["1X2"]
        n = len(past)
        out.append(
            {
                "rec": r,
                "outcome": metrics.outcome_index(r.hg, r.ag),
                "probs": (mk["home"], mk["draw"], mk["away"]),
                "base": (
                    sum(x.hg > x.ag for x in past) / n,
                    sum(x.hg == x.ag for x in past) / n,
                    sum(x.hg < x.ag for x in past) / n,
                ),
            }
        )
    return out


def run(recs: list[Rec], max_matches: int = 2000, **fit_kw) -> dict:
    total = min(len(recs), max_matches)
    ev = walk_forward(recs, max_matches, **fit_kw)
    probs, base, outs = (
        [e["probs"] for e in ev],
        [e["base"] for e in ev],
        [e["outcome"] for e in ev],
    )
    p_home, hit_home = [p[0] for p in probs], [o == 0 for o in outs]
    res = {
        "model": f"{poisson.MODEL_NAME}-{poisson.MODEL_VERSION}",
        "evaluated": len(outs),
        "skipped_insufficient_data": total - len(outs),
    }
    if len(outs) < 20:
        return {
            **res,
            "reliable": False,
            "note": "Moins de 20 matchs évaluables : aucune conclusion statistique.",
        }
    b, bb = metrics.brier(probs, outs), metrics.brier(base, outs)
    ll, bl = metrics.log_loss(probs, outs), metrics.log_loss(base, outs)
    return {
        **res,
        "reliable": len(outs) >= 100,
        "brier": b,
        "brier_baseline": bb,
        "brier_skill": 1 - b / bb,
        "log_loss": ll,
        "log_loss_baseline": bl,
        "calibration_home_win": metrics.calibration_bins(p_home, hit_home),
        "note": "Baseline = fréquences observées des résultats avant chaque match. Skill > 0 : le modèle fait mieux que la baseline.",
    }
