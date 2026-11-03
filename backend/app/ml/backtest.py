"""Backtest chronologique (walk-forward) : chaque match est prédit avec les SEULS matchs antérieurs."""

from app.ml import metrics, poisson
from app.ml.data import Rec


def run(recs: list[Rec], max_matches: int = 2000, **fit_kw) -> dict:
    recs = sorted(recs, key=lambda r: r.when)[-max_matches:]
    probs, base, outs, p_home, hit_home = [], [], [], [], []
    skipped = 0
    for i, r in enumerate(recs):
        past = [x for x in recs[:i] if x.when < r.when]
        f = poisson.fit(past, r.when, **fit_kw)
        if poisson.eligibility(f, r.home, r.away):
            skipped += 1
            continue
        mk = poisson.markets(*poisson.expected_goals(f, r.home, r.away))["1X2"]
        o = metrics.outcome_index(r.hg, r.ag)
        n = len(past)
        freq = (
            sum(x.hg > x.ag for x in past) / n,
            sum(x.hg == x.ag for x in past) / n,
            sum(x.hg < x.ag for x in past) / n,
        )
        probs.append((mk["home"], mk["draw"], mk["away"]))
        base.append(freq)
        outs.append(o)
        p_home.append(mk["home"])
        hit_home.append(o == 0)
    res = {
        "model": f"{poisson.MODEL_NAME}-{poisson.MODEL_VERSION}",
        "evaluated": len(outs),
        "skipped_insufficient_data": skipped,
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
