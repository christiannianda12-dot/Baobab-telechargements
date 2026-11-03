import math
from datetime import UTC, datetime, timedelta

import pytest

from app.ml import backtest, elo, metrics, poisson
from app.ml.data import Rec
from tests.synth import league

T0 = datetime(2026, 1, 1, tzinfo=UTC)


def test_markets_are_coherent():
    mk = poisson.markets(1.5, 1.1)
    h = mk["1X2"]
    assert sum(h.values()) == pytest.approx(1.0)
    assert mk["DC"]["1X"] == pytest.approx(h["home"] + h["draw"])
    for v in mk["OU"].values():
        assert v["over"] + v["under"] == pytest.approx(1.0)
    assert mk["OU"]["0.5"]["over"] > mk["OU"]["1.5"]["over"] > mk["OU"]["2.5"]["over"]
    assert mk["BTTS"]["yes"] + mk["BTTS"]["no"] == pytest.approx(1.0)
    assert h["home"] > h["away"]  # lambda domicile plus grand


def test_markets_match_hand_computation():
    lam = 1.0  # deux équipes à 1 but attendu : P(0-0) = e^-2
    mk = poisson.markets(lam, lam)
    assert mk["1X2"]["home"] == pytest.approx(mk["1X2"]["away"])
    assert mk["OU"]["0.5"]["under"] == pytest.approx(math.exp(-2), rel=1e-6)
    assert mk["BTTS"]["yes"] == pytest.approx((1 - math.exp(-1)) ** 2, rel=1e-6)
    assert mk["exact_scores"][0]["probability"] == pytest.approx(math.exp(-2), rel=1e-6)


def test_fit_recovers_strength_order_and_ignores_future():
    recs, strength = league()
    half = recs[:150]
    cut = recs[150].when
    f = poisson.fit(half, cut)
    best, worst = max(strength, key=strength.get), min(strength, key=strength.get)
    assert f.attack[best] / f.defense[best] > f.attack[worst] / f.defense[worst]
    # aucune fuite : ajouter des matchs postérieurs à as_of ne change rien
    f2 = poisson.fit(recs, cut)
    assert f2.n_matches == f.n_matches and f2.attack == f.attack


def test_shrinkage_pulls_tiny_samples_to_average():
    recs = [Rec(T0 + timedelta(days=i), 1, 2, 9, 0) for i in range(2)] + [
        Rec(T0 + timedelta(days=5), 3, 4, 1, 1)
    ]
    f = poisson.fit(recs, T0 + timedelta(days=30))
    assert f.attack[1] < 2.5  # sans prior, il tendrait vers l'infini


def test_eligibility_thresholds():
    recs, _ = league()
    f = poisson.fit(recs[:10], recs[10].when)
    assert "insuffisant" in poisson.eligibility(f, recs[10].home, recs[10].away)
    f = poisson.fit(recs, recs[-1].when + timedelta(days=1))
    assert poisson.eligibility(f, 1, 2) is None
    assert "minimum" in poisson.eligibility(f, 1, 999)


def test_elo_zero_sum_and_ranking():
    recs = [Rec(T0 + timedelta(days=i), 1, 2, 3, 0) for i in range(10)]
    r = elo.ratings(recs)
    assert r[1] > 1500 > r[2] and r[1] + r[2] == pytest.approx(3000)
    assert elo.expected_score(1500, 1500, 0) == pytest.approx(0.5)


def test_metrics_known_values():
    uniform = [(1 / 3, 1 / 3, 1 / 3)] * 3
    assert metrics.brier(uniform, [0, 1, 2]) == pytest.approx(2 / 3)
    assert metrics.log_loss(uniform, [0, 1, 2]) == pytest.approx(math.log(3))
    assert metrics.brier([(1, 0, 0)], [0]) == 0
    assert metrics.log_loss([(0.0, 1.0, 0.0)], [0]) > 20  # jamais d'infini
    bins = metrics.calibration_bins([0.1, 0.15, 0.9], [False, True, True], bins=5)
    assert bins[0]["n"] == 2 and bins[0]["observed_frequency"] == 0.5


def test_backtest_beats_baseline_on_synthetic_league():
    recs, _ = league()
    res = backtest.run(recs)
    assert res["evaluated"] > 100 and res["reliable"] is True
    assert res["brier"] < res["brier_baseline"] and res["brier_skill"] > 0.02
    assert res["log_loss"] < res["log_loss_baseline"]


def test_backtest_small_sample_makes_no_claim():
    recs, _ = league()
    res = backtest.run(recs[:40])
    assert res["reliable"] is False and "brier" not in res
