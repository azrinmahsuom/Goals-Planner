"""The browser engine (app/engine.js) checked against the Python engine, run through quickjs.

Phase 3 pre-registration, section 7: deterministic parts must match exactly; the Student-t
chance of reaching the goal must match the Python Student-t results within two Monte Carlo
standard errors.
"""

import json
import math

import pytest

quickjs = pytest.importorskip("quickjs")

from analysis.config import ROOT  # noqa: E402
from analysis.sim import costs, srs  # noqa: E402

APP = ROOT / "app"
pytestmark = pytest.mark.skipif(not (APP / "params.js").exists(), reason="app not built")


@pytest.fixture(scope="module")
def js():
    ctx = quickjs.Context()
    ctx.eval((APP / "params.js").read_text())
    ctx.eval((APP / "engine.js").read_text())
    ctx.eval((ROOT / "tests" / "js_helpers.js").read_text())
    return ctx


def call(ctx, expr: str):
    return json.loads(ctx.eval(f"JSON.stringify({expr})"))


AMOUNTS = [0, 100, 500, 1000, 1275, 3000, 10_000, 12_000, 20_000, 150_000]
SHARES = [0.0, 0.49, 0.59, 0.88, 1.0]


def test_order_cost_matches_python(js):
    for share in SHARES:
        got = call(js, f"{AMOUNTS}.map(a => GoalsEngine.orderCost(a, {share}, GOALS_PARAMS.costs))")
        want = [costs.order_cost(a, share) if a > 0 else 0.0 for a in AMOUNTS]
        assert got == pytest.approx(want, rel=1e-12, abs=1e-12)


def test_annual_cost_matches_python(js):
    for share in [0.0, 0.3, 0.49, 0.54, 0.59, 0.67, 0.8, 0.88, 1.0]:
        got = call(js, f"GoalsEngine.annualCost({share}, GOALS_PARAMS.costs)")
        assert got == pytest.approx(costs.annual_cost(share), rel=1e-12)


def test_resident_tax_matches_python(js):
    for income in [0, 20_000, 35_000, 100_000, 400_000, 2_000_000]:
        got = call(js, f"GoalsEngine.residentTax({income}, GOALS_PARAMS.srs.tax_bands)")
        assert got == pytest.approx(float(srs.resident_tax(income)), abs=1e-9)


def test_zero_volatility_matches_the_annuity_formula(js):
    """With a zero scale matrix every month earns exactly ln(1 + CMA) / 12; no costs."""
    r_annual, years, initial, monthly = 0.03, 20, 10_000, 500
    got = call(js, f"TestHelpers.zeroVolTerminal({r_annual}, {years}, {initial}, {monthly})")
    r = math.expm1(math.log1p(r_annual) / 12)
    months = 12 * years
    annuity = initial * (1 + r) ** months + monthly * ((1 + r) ** months - 1) / r
    assert got == pytest.approx([annuity] * 3, rel=1e-9)


def test_srs_iras_example_tranche_is_tax_free(js):
    got = call(
        js,
        "GoalsEngine.residentTax(GOALS_PARAMS.srs.taxable_share * 40000,"
        " GOALS_PARAMS.srs.tax_bands)",
    )
    assert got == 0


def test_premature_uses_the_statutory_age_input(js):
    assert call(js, "GoalsEngine.srsPremature({age: 40, statutoryAge: 64}, 23)") is True
    assert call(js, "GoalsEngine.srsPremature({age: 40, statutoryAge: 62}, 23)") is False


@pytest.mark.parametrize("example", ["A", "B", "C", "D"])
def test_student_t_chance_matches_python_within_two_standard_errors(js, example):
    paths = 2000
    sim = json.loads((ROOT / "reports" / "simulation_figures.json").read_text())
    want = sim["grid"][example]["Student-t, SGD era"]["central"]["p_goal"]
    got = call(js, f'TestHelpers.presetChance("{example}", {paths})')
    se = math.sqrt(want * (1 - want) * (1 / paths + 1 / sim["paths"]))
    assert abs(got - want) <= 2 * se, (got, want, se)


def test_page_script_parses():
    """app.js needs a browser to run; this at least catches syntax errors."""
    ctx = quickjs.Context()
    source = (APP / "app.js").read_text()
    assert ctx.eval(f"typeof (function () {{ {source} }})") == "function"


def test_page_ships_no_monthly_series():
    """params.js holds parameters and results only (Phase 3 pre-registration, section 9)."""
    params = json.loads(
        (APP / "params.js").read_text().split("GOALS_PARAMS = ", 1)[1].rstrip().rstrip(";")
    )

    def longest_list(value) -> int:
        if isinstance(value, dict):
            return max((longest_list(v) for v in value.values()), default=0)
        if isinstance(value, list):
            return max([len(value), *(longest_list(v) for v in value)])
        return 0

    assert longest_list(params) < 50  # a monthly series would have hundreds of entries


def test_srs_split_matches_python(js):
    from analysis.sim import engine
    from analysis.sim import srs as srs_py

    member = srs_py.SRS(age=40, citizen_or_pr=True, marginal_rate=0.10)
    plan = engine.Plan(0.0, 1_000.0, 0.20, 36, 0.6)
    flows = srs_py.split(plan, member)
    got = call(
        js,
        "GoalsEngine.yearlyAmounts({years: 3, monthly: 1000, growth: 0.20},"
        " {citizenOrPr: true, marginalRate: 0.10}, GOALS_PARAMS.srs)",
    )
    assert got["intoSrs"] == pytest.approx([flows.into_srs[12 * y] for y in range(3)])
    assert got["outside"] == pytest.approx([flows.outside[12 * y] for y in range(3)])
    assert got["finalRelief"] == pytest.approx(flows.final_relief)


def test_premature_net_matches_python(js):
    import numpy as np

    from analysis.sim import srs as srs_py

    member = srs_py.SRS(
        age=40, citizen_or_pr=True, marginal_rate=0.115, other_income_in_retirement=30_000
    )
    balances = [50_000.0, 250_000.0, 1_500_000.0]
    want = srs_py.premature_net(np.array(balances), member).tolist()
    got = call(
        js,
        f"Array.from(GoalsEngine.prematureNet(Float64Array.from({balances}),"
        " {otherIncome: 30000}, GOALS_PARAMS.srs))",
    )
    assert got == pytest.approx(want, rel=1e-12)
