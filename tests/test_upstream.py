import json

import pytest

from analysis import upstream

BACKTEST_MD = """Intro. Withholding drag = equity weight x trailing dividend yield 1.42% x rate.

|  | basis | ISAC.L_weight | A35.SI_weight | ter_bps | wht_drag_bps | trading_bps | all_in_annual_bps | one_off_purchase_bps |
|---|---|---|---|---|---|---|---|---|
| Menu: 59% equity | binding menu | 59.0% | 41.0% | 21.64 | 10.06 | 1.28 | 32.98 | 12.04 |

After the table.
"""  # noqa: E501

FRONTIER_MD = """| mix | expected_real_return | max_drawdown |
|---|---|---|
| 0% equity | 3.4% | -57.2% |
| 100% equity | 6.3% | -76.8% |
"""


def test_percent():
    assert upstream.percent(" 59.0% ") == 0.59


def test_markdown_table_stops_at_first_non_table_line():
    (table,) = upstream.markdown_tables(BACKTEST_MD, "all_in_annual_bps")
    assert len(table) == 1
    assert table.columns[0] == "label"


def test_mix_costs_parses_components():
    row = upstream.mix_costs(BACKTEST_MD).iloc[0]
    assert row["equity_share"] == 0.59
    assert row["all_in_annual_bps"] == 32.98
    assert row["commit"] == upstream.COMMITS[upstream.MAA][:7]


def test_risk_menu_marks_infeasible_limits():
    headline = json.dumps(
        {"menu long -30%: equity share": -1.0, "menu long -50%: equity share": 0.59}
    )
    menu = upstream.risk_menu(headline).set_index("drawdown_limit")
    assert not menu.loc[-0.3, "feasible"]
    assert menu.loc[-0.5, "equity_share"] == 0.59


def test_historical_returns_require_identical_horizons():
    returns = upstream.historical_mix_returns(FRONTIER_MD + "\n" + FRONTIER_MD)
    assert returns["expected_real_return"].tolist() == [0.034, 0.063]
    changed = FRONTIER_MD.replace("6.3%", "6.4%")
    with pytest.raises(ValueError, match="differ across horizons"):
        upstream.historical_mix_returns(FRONTIER_MD + "\n" + changed)


def test_vendored_mix_costs_add_up():
    """Each committed all-in cost equals its components, within one 0.01 bp rounding unit
    (upstream rounds each component separately: 20.48 + 15.01 + 0.88 = 36.37 vs 36.38)."""
    mixes = upstream.load("mix_costs")
    parts = mixes["ter_bps"] + mixes["wht_drag_bps"] + mixes["trading_bps"]
    assert (parts - mixes["all_in_annual_bps"]).abs().max() <= 0.01 + 1e-9


def test_vendored_ter_component_is_weighted_fund_ter():
    """ter_bps = equity weight x ISAC TER + bond weight x A35 TER, from the vendored fund facts."""
    facts = upstream.load("fund_facts").query("field == 'ter'").set_index("ticker")["value"]
    mixes = upstream.load("mix_costs")
    w = mixes["equity_share"]
    implied = (w * facts["ISAC.L"] + (1 - w) * facts["A35.SI"]) * 1e4
    assert implied.round(2).tolist() == mixes["ter_bps"].tolist()
