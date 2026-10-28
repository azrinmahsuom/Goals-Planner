import numpy as np
import pandas as pd
import pytest

from analysis.cma import history, methods
from analysis.sources import documents


def synthetic_shiller(start="1871-01", end="1960-12", seed=0) -> pd.DataFrame:
    """Monthly frame shaped like sources.shiller.monthly(), with random but positive data."""
    idx = pd.period_range(start, end, freq="M", name="month")
    rng = np.random.default_rng(seed)
    n = len(idx)
    price = 10 * np.exp(np.cumsum(rng.normal(0.004, 0.04, n)))
    return pd.DataFrame(
        {
            "price": price,
            "dividend": price * 0.04 * np.exp(rng.normal(0, 0.05, n)),
            "earnings": price * 0.07 * np.exp(rng.normal(0, 0.10, n)),
            "cpi": 10 * np.exp(np.cumsum(rng.normal(0.001, 0.005, n))),
            "gs10": 0.04 + rng.normal(0, 0.002, n),
            "bond_tr": rng.normal(0.003, 0.01, n),
        },
        index=idx,
    )


def test_shiller_annual_uses_december_price_and_september_fundamentals():
    m = synthetic_shiller()
    a = history.shiller_annual(m)
    assert a.loc[1900, "price"] == m.loc["1900-12", "price"]
    assert a.loc[1900, "dividend"] == m.loc["1900-09", "dividend"]
    assert a.loc[1900, "cpi_lag"] == m.loc["1900-09", "cpi"]


def test_shiller_forecasts_ignore_data_after_the_origin():
    """Changing everything after 1930 leaves every forecast and benchmark up to 1930 unchanged."""
    base = synthetic_shiller()
    changed = base.copy()
    later = changed.index >= pd.Period("1931-01", freq="M")
    changed.loc[later, ["price", "dividend", "earnings", "cpi"]] *= 1.7
    a = methods.shiller_equity(history.shiller_annual(base))
    b = methods.shiller_equity(history.shiller_annual(changed))
    for name in ("E1", "E2", "E3", "D1"):
        early_a, early_b = a[name].loc[:1930], b[name].loc[:1930]
        pd.testing.assert_series_equal(early_a["forecast"], early_b["forecast"])
        pd.testing.assert_series_equal(early_a["historical_mean"], early_b["historical_mean"])


def test_burn_in_leaves_first_thirty_years_without_forecasts():
    frames = methods.shiller_equity(history.shiller_annual(synthetic_shiller()))
    first = frames["D1"]["forecast"].first_valid_index()
    assert first == 1871 + 30


def jst_panel(years=range(1870, 1951), gap=None) -> pd.DataFrame:
    """One-country panel with a 4% dividend yield and real dividends growing exactly 2% a year
    (constant CPI and yield, so prices also grow 2%)."""
    years = list(years)
    df = pd.DataFrame(
        {
            "eq_capgain": 0.02,
            "eq_dp": 0.04,
            "eq_tr": 0.02 + 0.04 * 1.02,
            "cpi": 100.0,
            "bond_tr": 0.03,
            "ltrate": 0.03,
        },
        index=pd.MultiIndex.from_product([["Testland"], years], names=["country", "year"]),
    )
    if gap is not None:
        df.loc[("Testland", gap), "eq_tr"] = np.nan
    return df


def test_d1_is_yield_plus_real_dividend_growth():
    frame = methods.jst_d1(jst_panel())["Testland"]
    assert frame["forecast"].dropna().to_numpy() == pytest.approx(0.04 + 0.02)


def test_jst_gap_restarts_growth_and_burn_in():
    frame = methods.jst_d1(jst_panel(gap=1900))["Testland"]
    # Before the gap: forecasts from 1870 + 30 = 1900 would be the first, but 1900 is the gap.
    assert frame.loc[:1899, "forecast"].notna().sum() == 0
    # After the gap the new run starts in 1901, so the first forecast is 1931.
    assert frame["forecast"].first_valid_index() == 1931
    # No realised window spans the gap.
    assert frame.loc[1890:1899, "realised"].isna().all()


def test_contiguous_runs_split_on_gaps():
    valid = pd.Series([True, True, False, True], index=[1, 2, 3, 4])
    runs = history.contiguous_runs(valid)
    assert runs[1] == runs[2]
    assert np.isnan(runs[3])
    assert runs[4] != runs[1]


def test_bond_b1_forecast_is_the_starting_yield():
    a = history.shiller_annual(synthetic_shiller())
    b1 = methods.shiller_bonds(a)["B1"]
    assert b1.loc[1950, "forecast"] == a.loc[1950, "gs10"]


def test_acwd_withholding_rate_from_reference():
    assert documents.withholding_rate("ACWD", "fy2026") == pytest.approx(17_687_265 / 140_163_819)


def test_changed_document_is_drift_not_failure(monkeypatch):
    """A newer factsheet at the same URL is reported, and its quotes are not checked."""
    from analysis import manifest

    real = manifest.load()
    if not all(doc.exists() for doc, *_ in documents.CHECKS):
        pytest.skip("documents not fetched (e.g. CI, where raw data isn't committed)")
    altered = {k: dict(v) for k, v in real.items()}
    altered["documents/ACWD_factsheet.pdf"]["sha256"] = "0" * 64
    monkeypatch.setattr(manifest, "load", lambda *a, **k: altered)
    result = documents.verify_reference()
    assert result["drifted"] == ["documents/ACWD_factsheet.pdf"]
    assert "TER 0.12%" not in result["checked"]
