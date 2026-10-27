import numpy as np
import pandas as pd
import pytest

from analysis.cma import validate


def test_forward_return_annualises_over_horizon():
    level = pd.Series([1.0, 1.1, 2.0**0.5], index=[2000, 2001, 2002])
    out = validate.forward_return(level, years=2)
    assert out[2000] == pytest.approx(2**0.25 - 1)
    assert np.isnan(out[2001])  # window runs past the data


def test_historical_mean_uses_only_completed_windows():
    realised = pd.Series(np.arange(30, dtype=float), index=range(1900, 1930))
    hm = validate.historical_mean(realised, years=10)
    assert np.isnan(hm[1909])  # no window has ended yet
    assert hm[1910] == 0.0  # only the 1900 window (ending 1910) is complete
    assert hm[1915] == pytest.approx(np.mean(range(6)))


def test_newey_west_with_no_lags_is_the_iid_standard_error():
    e = pd.Series([0.01, -0.02, 0.03, 0.00, 0.02])
    expected = e.std(ddof=0) / np.sqrt(len(e))
    assert validate.newey_west_se(e, lags=0) == pytest.approx(expected)


def test_newey_west_widens_with_positive_autocorrelation():
    e = pd.Series(np.repeat([0.02, -0.02], 10))  # long runs: strong positive autocorrelation
    assert validate.newey_west_se(e, lags=9) > validate.newey_west_se(e, lags=0)


def _frame(forecast, realised, hm):
    return pd.DataFrame({"forecast": forecast, "realised": realised, "historical_mean": hm})


def test_perfect_forecast_has_r2_one_and_benchmark_has_r2_zero():
    rng = np.random.default_rng(0)
    realised = pd.Series(rng.normal(0.05, 0.03, 50))
    hm = pd.Series(rng.normal(0.05, 0.01, 50))
    perfect = validate.evaluate(_frame(realised, realised, hm))
    assert perfect["oos_r2"] == pytest.approx(1.0)
    assert perfect["rmse"] == pytest.approx(0.0)
    assert validate.evaluate(_frame(hm, realised, hm))["oos_r2"] == pytest.approx(0.0)


def test_noise_forecast_has_negative_r2():
    rng = np.random.default_rng(1)
    realised = pd.Series(rng.normal(0.05, 0.03, 200))
    hm = pd.Series(0.05, index=realised.index)
    noise = pd.Series(rng.normal(0.05, 0.03, 200))
    assert validate.evaluate(_frame(noise, realised, hm))["oos_r2"] < 0


def test_evaluate_reports_counts_and_bias():
    f = _frame([0.06, 0.05, np.nan], [0.05, 0.04, 0.03], [0.05, 0.05, 0.05])
    f.index = [1950, 1951, 1952]
    stats = validate.evaluate(f)
    assert stats["origins"] == 2
    assert stats["bias"] == pytest.approx(0.01)
    assert (stats["first_origin"], stats["last_origin"]) == (1950, 1951)


def test_pooled_standard_error_averages_errors_within_a_year():
    years = range(1950, 1970)
    a = _frame(pd.Series(0.06, index=years), pd.Series(0.05, index=years), 0.05)
    b = a.copy()
    pooled = validate.evaluate_pooled({"A": a, "B": b})
    assert pooled["countries"] == 2
    assert pooled["origins"] == 40
    assert pooled["effective_n"] == pytest.approx(2.0)  # 20 distinct years / 10
