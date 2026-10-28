"""Monthly real return histories that give the simulation its shape (not its level).

H-SGD (primary): developed-market equities converted to SGD and a constant-duration SGS bond,
both deflated by Singapore CPI, from July 1998. H-US (sensitivity): Shiller US equities and a
constant-duration bond priced from GS10, deflated by US CPI, from 1871. Both end at the as-of
month at the latest.
"""

import pandas as pd

from analysis.cma import AS_OF
from analysis.sim import SGS_DURATION
from analysis.sources import fred, french, mas, shiller, singstat

COUPONS_PER_YEAR = 2


def par_bond_return(prev_yield: pd.Series, yield_now: pd.Series, maturity: float) -> pd.Series:
    """One-month return on a par bond (semi-annual coupons) bought at prev_yield and repriced at
    yield_now one month later: coupon income plus the price change."""
    n = (maturity - 1 / 12) * COUPONS_PER_YEAR
    coupon, discount = prev_yield / COUPONS_PER_YEAR, 1 + yield_now / COUPONS_PER_YEAR
    price = coupon / (yield_now / COUPONS_PER_YEAR) * (1 - discount**-n) + discount**-n
    return price - 1 + prev_yield / 12


def _real(nominal: pd.Series, inflation: pd.Series) -> pd.Series:
    return (1 + nominal) / (1 + inflation) - 1


def sgs_month_end_yield(yields: pd.DataFrame, maturity: float = SGS_DURATION) -> pd.Series:
    """Month-end SGS yield at `maturity`, interpolated between the 5- and 10-year benchmarks."""
    daily = yields[[5, 10]].dropna()
    month_end = daily.groupby(daily.index.to_period("M")).last()
    out = month_end[5] + (maturity - 5) / 5 * (month_end[10] - month_end[5])
    out.index.name = "month"
    return out


def h_sgd() -> pd.DataFrame:
    """Monthly real SGD returns of developed-market equities and SGS at A35's duration."""
    fx = fred.month_end("DEXSIUS")  # SGD per USD
    equity_sgd = (1 + french.developed_market()) * (fx / fx.shift(1)) - 1
    y = sgs_month_end_yield(mas.sgs_yields())
    sgs = par_bond_return(y.shift(1), y, SGS_DURATION)
    inflation = singstat.cpi_monthly().pct_change()
    df = pd.DataFrame(
        {"equity": _real(equity_sgd, inflation), "sgs": _real(sgs, inflation)}
    ).dropna()
    return df.loc[: pd.Period(AS_OF, freq="M")]  # cut at the as-of month (Phase 4)


def h_us() -> pd.DataFrame:
    """Monthly real USD returns of US equities (Shiller) and a GS10-priced bond at A35's duration,
    to the last month with a reported dividend."""
    m = shiller.monthly().loc[: pd.Period(AS_OF, freq="M")]  # cut at the as-of month (Phase 4)
    m = m.loc[: m["dividend"].last_valid_index()]
    equity = (m["price"] + m["dividend"] / 12) / m["price"].shift(1) - 1
    bond = par_bond_return(m["gs10"].shift(1), m["gs10"], SGS_DURATION)
    inflation = m["cpi"].pct_change()
    return pd.DataFrame(
        {"equity": _real(equity, inflation), "sgs": _real(bond, inflation)}
    ).dropna()


HISTORIES = {"H-SGD": h_sgd, "H-US": h_us}
