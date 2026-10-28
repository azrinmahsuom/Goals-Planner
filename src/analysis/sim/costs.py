"""Costs: the all-in annual holding cost of a mix and the trading cost of each buy order.

Rules: docs/decisions.md (2026-10-28, Phase 2 pre-registration, section 5). Inputs come from
reference/fund_documents.csv (ACWD) and the vendored reference/upstream/ tables.
"""

from dataclasses import dataclass
from functools import cache

import pandas as pd

from analysis import upstream
from analysis.sources import documents


@dataclass(frozen=True)
class Fees:
    acwd_ter: float
    acwd_dividend_yield: float
    acwd_withholding: float
    a35_ter: float
    mix_trading_bps: pd.Series  # by equity share of the committed mixes
    schedule: pd.DataFrame  # reference/upstream/fee_schedule.csv


@cache
def load_fees() -> Fees:
    acwd = documents.fund_documents().query("fund == 'ACWD'").set_index("field")["value"]
    facts = upstream.load("fund_facts").query("field == 'ter'").set_index("ticker")["value"]
    mixes = upstream.load("mix_costs").set_index("equity_share")["trading_bps"]
    return Fees(
        acwd_ter=float(acwd["ter"]),
        acwd_dividend_yield=float(acwd["index_dividend_yield"]),
        acwd_withholding=documents.withholding_rate("ACWD", "fy2026"),
        a35_ter=float(facts["A35.SI"]),
        mix_trading_bps=mixes.sort_index(),
        schedule=upstream.load("fee_schedule"),
    )


def nearest_mix(equity_share: float, mixes: pd.Index) -> float:
    """The committed mix closest in equity share; ties go to the lower share."""
    return min(mixes, key=lambda m: (round(abs(m - equity_share), 10), m))


def annual_cost(equity_share: float, fees: Fees | None = None) -> float:
    """All-in annual cost: fund TERs, ACWD's fund-level withholding drag, and the nearest
    committed mix's rebalancing trading cost."""
    f = fees or load_fees()
    equity = f.acwd_ter + f.acwd_dividend_yield * f.acwd_withholding
    trading = f.mix_trading_bps[nearest_mix(equity_share, f.mix_trading_bps.index)] / 1e4
    return equity_share * equity + (1 - equity_share) * f.a35_ter + trading


def _fee(schedule: pd.DataFrame, component: str, market: str) -> pd.Series:
    return schedule[(schedule["component"] == component) & (schedule["market"] == market)].iloc[0]


def _rate(schedule: pd.DataFrame, component: str, provider: str) -> float:
    rows = schedule[(schedule["component"] == component) & (schedule["provider"] == provider)]
    return float(rows.iloc[0]["rate"])


def order_cost(amount_sgd: float, equity_share: float, fees: Fees | None = None) -> float:
    """Cost in SGD of investing amount_sgd split by the target weights into two buy orders:
    ACWD on LSE (USD, via an SGD->USD conversion) and A35 on SGX (SGD)."""
    f = fees or load_fees()
    s = f.schedule
    gst = float(_fee(s, "gst", "SG")["rate"])
    usd_per_sgd = _rate(s, "usd_per_unit", "SGD")
    usd_per_gbp = _rate(s, "usd_per_unit", "GBP")
    total = 0.0

    equity_usd = amount_sgd * equity_share * usd_per_sgd
    if equity_usd > 0:
        fx = _fee(s, "fx_conversion", "FX")
        commission = _fee(s, "commission", "LSE")
        levy = _fee(s, "ptm_levy", "LSE")
        cost = max(equity_usd * fx["rate"], fx["minimum"])
        cost += max(equity_usd * commission["rate"], commission["minimum"]) * (1 + gst)
        if equity_usd / usd_per_gbp >= levy["min_trade_value"]:
            cost += levy["rate"] * usd_per_gbp
        cost += equity_usd * _rate(s, "spread", "ACWD (LSE)") / 2
        total += cost / usd_per_sgd

    bond = amount_sgd * (1 - equity_share)
    if bond > 0:
        fees_sgx = 0.0
        for component in ("commission", "platform_fee", "clearing_fee", "trading_access_fee"):
            row = _fee(s, component, "SGX")
            fees_sgx += max(bond * row["rate"], row["minimum"] if pd.notna(row["minimum"]) else 0)
        total += fees_sgx * (1 + gst) + bond * _rate(s, "spread", "A35 (SGX)") / 2
    return total
