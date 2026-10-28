import json
import re

import numpy as np
import pandas as pd
import pytest
from test_methods import jst_panel

from analysis.cma import forward, report, scenarios
from analysis.config import DOCS, REFERENCE, REPORTS


def monthly_cpi(start="1990-01", end="2026-09", annual=0.02) -> pd.Series:
    idx = pd.period_range(start, end, freq="M")
    return pd.Series(100 * (1 + annual) ** (np.arange(len(idx)) / 12), index=idx)


def test_inflation_cma_is_30_year_compound_rate():
    value, rates = forward.inflation_cma(monthly_cpi(), as_of="2026-09-30")
    assert value == pytest.approx(0.02)
    assert (rates.index.min(), rates.index.max()) == (1996, 2025)


def test_dividend_growth_by_country_matches_constant_growth():
    growth, annual = forward.dividend_growth_by_country(jst_panel(range(1870, 2016)), 2015)
    assert growth["Testland"] == pytest.approx(0.02)
    assert annual["Testland"].to_numpy() == pytest.approx(0.02)


def test_country_without_30_year_run_is_excluded():
    growth, _ = forward.dividend_growth_by_country(jst_panel(range(1870, 2016), gap=1990), 2015)
    assert growth.empty  # run 1991-2015 is only 24 years


def test_sgs_interpolation_and_rolldown_by_hand():
    curve = pd.Series({5: 0.02, 10: 0.025})
    out = forward.sgs_nominal(curve)
    slope = 0.005 / 5
    assert out["B1"] == pytest.approx(0.02 + 3.18 * slope)
    assert out["rolldown"] == pytest.approx(slope * 7.18)


def test_cash_splice_switches_to_sora_in_2014():
    idx = pd.period_range("2013-11", "2014-02", freq="M")
    rates = pd.DataFrame(
        {"Interbank 3-Month": [0.004, 0.004, 0.009, 0.009], "Compound SORA - 3 month": 0.001},
        index=idx,
    )
    spliced = forward.three_month_spliced(rates)
    assert spliced.tolist() == [0.004, 0.004, 0.001, 0.001]


def test_cash_cma_is_midpoint_of_start_and_long_run():
    assert forward.cash_cma(0.03, 0.02, 0.01) == pytest.approx(0.01)


def test_scenario_width_is_the_wider_of_spread_and_se():
    s = scenarios.scenario(0.03, 0.004, 0.006)
    assert (s["low"], s["high"]) == pytest.approx((0.024, 0.036))
    assert s["width_set_by"].startswith("(b)")
    assert scenarios.scenario(0.03, 0.007, 0.006)["width_set_by"].startswith("(a)")


def test_block_length_and_compound_rate():
    assert scenarios.block_length(30) == 4
    assert scenarios.compound_rate(np.array([0.1, -0.1])) == pytest.approx((1.1 * 0.9) ** 0.5 - 1)


def test_drift_check_flags_moves_beyond_tolerance(tmp_path, monkeypatch):
    path = tmp_path / "cma_figures.json"
    path.write_text(
        json.dumps({"scenarios": {"sgs": {"low": 0.01, "central": 0.02, "high": 0.03}}})
    )
    monkeypatch.setattr(report, "FIGURES_JSON", path)
    small = {"scenarios": {"sgs": {"low": 0.0105, "central": 0.02, "high": 0.03}}}
    large = {"scenarios": {"sgs": {"low": 0.01, "central": 0.0215, "high": 0.03}}}
    assert report.check_drift(small) == []
    assert report.check_drift(large) == ["sgs central: 0.0200 -> 0.0215"]


def _numbers(value) -> set[str]:
    """Every way a JSON number can be printed in the doc."""
    out = set()
    if isinstance(value, dict):
        for v in value.values():
            out |= _numbers(v)
    elif isinstance(value, list):
        for v in value:
            out |= _numbers(v)
    elif isinstance(value, int | float) and not isinstance(value, bool):
        for scaled in (value, value * 100):
            for dp in (0, 1, 2, 3):
                out.add(f"{scaled:.{dp}f}")
                out.add(f"{abs(scaled):.{dp}f}")
    elif isinstance(value, str):
        out |= set(re.findall(r"\d+(?:\.\d+)?", value))
    return out


@pytest.mark.skipif(not (REPORTS / "cma_figures.json").exists(), reason="report not built")
def test_every_number_in_cma_doc_is_generated_or_cited():
    figures = json.loads((REPORTS / "cma_figures.json").read_text())
    allowed = _numbers(figures)
    for csv in REFERENCE.rglob("*.csv"):
        allowed |= set(re.findall(r"\d+(?:\.\d+)?", csv.read_text()))
    text = (DOCS / "cma.md").read_text()
    text = re.sub(r"\(\.\./reports/[^)]*\)", "", text)  # image path
    found = set(re.findall(r"(?<![\w.])\d+(?:\.\d+)?", text))
    unexplained = {
        n
        for n in found
        if n not in allowed and not (n.isdigit() and (int(n) <= 30 or 1800 <= int(n) <= 2100))
    }
    # Method constants stated in decisions.md: replications, seed, HAC lags, horizon.
    assert unexplained <= {"2000", "20261028"}, unexplained


def test_zero_dividend_inside_a_run_does_not_exclude_the_country():
    """Only the endpoints need positive dividends (correction, docs/decisions.md 2026-10-28)."""
    panel = jst_panel(range(1870, 2016))
    panel.loc[("Testland", 1923), "eq_dp"] = 0.0
    growth, annual = forward.dividend_growth_by_country(panel, 2015)
    assert "Testland" in growth.index
    assert np.isfinite(annual["Testland"]).all()


def test_joint_bootstrap_resamples_years_shared_across_countries():
    years = range(1900, 1960)
    rng = np.random.default_rng(3)
    common = pd.Series(rng.normal(0.02, 0.05, len(years)), index=years)
    together = {"A": common, "B": common.copy()}
    draws = scenarios.dividend_growth_draws(together, reps=200, seed=1)
    # Identical countries draw identical years, so the median equals each country's growth.
    single = scenarios.dividend_growth_draws({"A": common}, reps=200, seed=1)
    assert draws == pytest.approx(single)
