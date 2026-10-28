import math

import numpy as np
import pandas as pd
import pytest

from analysis.sim import costs, engine, srs
from analysis.sim.history import par_bond_return


def constant_draws(r_monthly: float, months: int, paths: int = 3) -> np.ndarray:
    return np.full((paths, months, 2), r_monthly)


def test_zero_volatility_matches_the_annuity_formula_exactly():
    r, months, initial, monthly = 0.004, 240, 10_000.0, 500.0
    plan = engine.Plan(initial, monthly, 0.0, months, 0.6)
    wealth = engine.simulate(constant_draws(r, months), plan, annual_cost=0.0).wealth[:, -1]
    annuity = initial * (1 + r) ** months + monthly * ((1 + r) ** months - 1) / r
    assert wealth == pytest.approx(np.full(3, annuity), rel=1e-12)


def test_annual_cost_reduces_a_constant_return_by_exactly_c():
    r_annual, c = 0.05, 0.003
    r = (1 + r_annual) ** (1 / 12) - 1
    plan = engine.Plan(1.0, 0.0, 0.0, 12, 0.5)
    wealth = engine.simulate(constant_draws(r, 12), plan, annual_cost=c).wealth[0, -1]
    assert wealth == pytest.approx((1 + r_annual) * (1 - c))


def test_contribution_growth_steps_every_twelve_months():
    plan = engine.Plan(0.0, 100.0, 0.10, 25, 0.5)
    amounts = engine.contributions(plan)
    assert amounts[:12] == pytest.approx(100.0)
    assert amounts[12:24] == pytest.approx(110.0)
    assert amounts[24] == pytest.approx(121.0)


def history(n=400, seed=0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    return pd.DataFrame(
        {"equity": rng.standard_t(5, n) * 0.04 + 0.005, "sgs": rng.normal(0.002, 0.015, n)}
    )


def test_recentring_hits_the_target_mean_log_return_exactly():
    out = engine.recentre(history(), {"equity": 0.03, "sgs": 0.01})
    assert out["equity"].mean() == pytest.approx(math.log1p(0.03) / 12, abs=1e-15)
    assert out["sgs"].mean() == pytest.approx(math.log1p(0.01) / 12, abs=1e-15)


def test_simulated_median_geometric_return_is_close_to_the_cma():
    """Geometric re-centring end to end: no costs, long horizon, single asset."""
    cma = {"equity": 0.03, "sgs": 0.01}
    months = 600
    draws = engine.DrawFactory(history(1000), "bootstrap", months, paths=4000).draws(cma)
    plan = engine.Plan(1.0, 0.0, 0.0, months, 1.0)
    terminal = engine.simulate(draws, plan, annual_cost=0.0).wealth[:, -1]
    median_geometric = np.median(terminal) ** (12 / months) - 1
    assert median_geometric == pytest.approx(0.03, abs=0.003)


def test_same_seed_reproduces_draws_and_different_seed_does_not():
    cma = {"equity": 0.03, "sgs": 0.01}
    a = engine.DrawFactory(history(), "bootstrap", 60, paths=50, seed=1).draws(cma)
    b = engine.DrawFactory(history(), "bootstrap", 60, paths=50, seed=1).draws(cma)
    c = engine.DrawFactory(history(), "bootstrap", 60, paths=50, seed=2).draws(cma)
    assert np.array_equal(a, b)
    assert not np.array_equal(a, c)


def test_stationary_bootstrap_mean_block_length():
    rng = np.random.default_rng(0)
    idx = engine.stationary_indices(1000, 2000, 24, 50, rng)
    new_blocks = (np.diff(idx, axis=1) != 1) & ~((idx[:, :-1] == 999) & (idx[:, 1:] == 0))
    mean_length = idx.shape[1] / (new_blocks.sum(axis=1).mean() + 1)
    assert mean_length == pytest.approx(24, rel=0.1)


def test_student_t_fit_recovers_heavy_tails():
    rng = np.random.default_rng(0)
    x = pd.DataFrame(
        {"equity": rng.standard_t(4, 3000) * 0.03, "sgs": rng.standard_t(4, 3000) * 0.01}
    )
    fit = engine.fit_student_t(np.expm1(x))
    assert 3 <= fit.df <= 6


def test_required_monthly_rises_with_the_target_probability():
    cma = {"equity": 0.03, "sgs": 0.01}
    draws = engine.DrawFactory(history(), "bootstrap", 120, paths=500).draws(cma)
    plan = engine.Plan(10_000, 0.0, 0.0, 120, 0.6)
    amounts = [
        engine.required_monthly(draws, plan, 100_000, p, annual_cost=0.003)
        for p in (0.5, 0.75, 0.9)
    ]
    assert amounts[0] <= amounts[1] <= amounts[2]
    assert amounts[0] > 0


def test_quarterly_batching_invests_every_third_month():
    plan = engine.Plan(0.0, 100.0, 0.0, 6, 0.5, batching="quarterly")
    p = engine.simulate(constant_draws(0.0, 6, 1), plan, 0.0, order_cost=lambda a, w: 1.0)
    assert p.wealth[0].tolist() == [0.0, 0.0, 0.0, 299.0, 299.0, 299.0, 598.0]


def test_par_bond_return_is_the_yield_when_yields_do_not_move():
    y = pd.Series([0.03, 0.03])
    assert par_bond_return(y.shift(1), y, 8.18).iloc[1] == pytest.approx(0.03 / 12)


# --- costs ---


def test_order_cost_matches_a_hand_calculation():
    f = costs.load_fees()
    s = f.schedule.set_index(["component", "market"])
    usd_per_sgd = 0.78235
    equity_usd = 1000 * 0.59 * usd_per_sgd  # 461.59
    expected_equity = (2.0 + 4.0 * 1.09 + equity_usd * 0.001 / 2) / usd_per_sgd  # minimums bind
    bond = 1000 * 0.41
    sgx = (0.99 + 1.50 + bond * (0.000325 + 0.000075)) * 1.09
    a35_half_spread = bond * float(s.loc[("spread", "SGX"), "rate"]) / 2
    expected = expected_equity + sgx + a35_half_spread
    assert costs.order_cost(1000, 0.59) == pytest.approx(expected)


def test_order_cost_adds_the_lse_levy_on_large_orders():
    """S$12,000 is below GBP 10,000 and S$20,000 above it. Both clear the USD 4 commission
    minimum; the USD 2 FX minimum binds at both."""
    small, large = costs.order_cost(12_000, 1.0), costs.order_cost(20_000, 1.0)
    levy_sgd = 1.5 * 1.3375 / 0.78235
    proportional = 8_000 * (0.0005 * 1.09 + 0.001 / 2)  # commission with GST + half spread
    assert large - small == pytest.approx(proportional + levy_sgd)


def test_annual_cost_uses_acwd_withholding_and_nearest_mix():
    f = costs.load_fees()
    expected = (
        0.59 * (f.acwd_ter + f.acwd_dividend_yield * f.acwd_withholding)
        + 0.41 * f.a35_ter
        + f.mix_trading_bps[0.59] / 1e4
    )
    assert costs.annual_cost(0.59) == pytest.approx(expected)
    assert costs.nearest_mix(0.54, f.mix_trading_bps.index) == 0.49  # tie goes to lower share


# --- SRS ---


def test_resident_tax_matches_iras_schedule():
    assert srs.resident_tax(20_000) == pytest.approx(0)  # IRAS example: $20,000 taxable -> nil
    assert srs.resident_tax(100_000) == pytest.approx(3_350 + 20_000 * 0.115)


def test_srs_withdrawal_iras_example_tranche_is_tax_free():
    """IRAS example: $40,000 withdrawn, 50% taxable = $20,000, tax nil."""
    out = srs.withdraw(
        np.array([400_000.0]),
        np.zeros((1, 10)),
        srs.SRS(age=40, citizen_or_pr=True, marginal_rate=0.115),
        taxed=True,
    )
    assert out["tax_paid"][0] == pytest.approx(0.0)
    assert out["after_tax_withdrawals"][0] == pytest.approx(400_000.0)


def test_premature_withdrawal_tax_and_penalty():
    member = srs.SRS(age=40, citizen_or_pr=True, marginal_rate=0.115)
    assert srs.premature(member, months=12 * 20)  # 60 < 64
    assert not srs.premature(member, months=12 * 24)  # 64
    assert srs.premature_net(np.array([100.0]), member)[0] == pytest.approx(
        100 * (1 - 0.115 - 0.05)
    )
