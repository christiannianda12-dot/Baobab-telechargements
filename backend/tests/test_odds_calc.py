import math

import pytest

from app.services import odds as c


def test_implied_probability():
    assert c.implied_probability(2.0) == 0.5
    assert math.isclose(c.implied_probability(4.0), 0.25)


@pytest.mark.parametrize("bad", [1.0, 0.5, 0, -2])
def test_invalid_prices_rejected(bad):
    with pytest.raises(ValueError):
        c.implied_probability(bad)


def test_margin_and_fair_probabilities_1x2():
    prices = [2.10, 3.40, 3.60]  # surrondation connue
    over = 1 / 2.10 + 1 / 3.40 + 1 / 3.60
    assert math.isclose(c.overround(prices), over)
    assert math.isclose(c.margin(prices), over - 1)
    fair = c.remove_margin(prices)
    assert math.isclose(sum(fair), 1.0)
    assert fair[0] == pytest.approx((1 / 2.10) / over)


def test_fair_market_has_zero_margin():
    assert c.margin([2.0, 2.0]) == pytest.approx(0.0)
    assert c.remove_margin([2.0, 2.0]) == [0.5, 0.5]


def test_overround_needs_two_outcomes():
    with pytest.raises(ValueError):
        c.overround([1.9])


def test_expected_value_and_edge():
    assert c.expected_value(0.5, 2.0) == pytest.approx(0.0)
    assert c.expected_value(0.55, 2.0) == pytest.approx(0.10)
    assert c.expected_value(0.4, 2.0) == pytest.approx(-0.20)
    assert c.edge(0.55, 2.0) == pytest.approx(0.05)
    with pytest.raises(ValueError):
        c.expected_value(1.2, 2.0)
