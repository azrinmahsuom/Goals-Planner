"""Forward 10-year CMAs at the as-of date, under the rules in docs/decisions.md (2026-10-28).

All outputs are annualised real returns (decimals) at index level, before fund costs.
"""

import numpy as np
import pandas as pd

from analysis.cma import AS_OF, BURN_IN, JST_END_YEAR
from analysis.cma.history import jst_country

INFLATION_YEARS = 30
SGS_DURATION = 8.18  # A35 weighted average duration, reference/upstream/fund_facts.csv
CASH_START_YEAR = 1988
INTERBANK_LAST_MONTH = "2013-12"  # MAS discontinued 3-month interbank from 1 Jan 2014


def annual_inflation(cpi: pd.Series) -> pd.Series:
    """Dec-to-Dec inflation by calendar year from a monthly CPI index."""
    dec = cpi[cpi.index.month == 12]
    dec.index = dec.index.year
    return (dec / dec.shift(1) - 1).dropna()


def inflation_cma(cpi: pd.Series, as_of: str = AS_OF) -> tuple[float, pd.Series]:
    """Annualised CPI inflation over the 30 full calendar years before the as-of date."""
    last = pd.Period(as_of, freq="M").year - 1
    rates = annual_inflation(cpi).loc[last - INFLATION_YEARS + 1 : last]
    if len(rates) != INFLATION_YEARS:
        raise ValueError(f"Need {INFLATION_YEARS} years of CPI to {last}, have {len(rates)}")
    return float(np.prod(1 + rates) ** (1 / INFLATION_YEARS) - 1), rates


def _annual_growth(level: pd.Series) -> pd.Series:
    """Year-on-year growth, dropping changes into or out of a zero level (undefined in logs)."""
    rates = (level / level.shift(1) - 1).replace([np.inf, -np.inf], np.nan)
    return rates[rates > -1].dropna()


def dividend_growth_by_country(
    panel: pd.DataFrame, end_year: int = JST_END_YEAR
) -> tuple[pd.Series, dict[str, pd.Series]]:
    """Each country's annualised real dividend growth over its contiguous run ending in
    end_year (runs shorter than the burn-in are excluded), and the annual growth rates behind
    it (for the bootstrap)."""
    growth, annual = {}, {}
    for country, rows in panel.groupby(level="country"):
        df = jst_country(rows.droplevel("country")).loc[:end_year]
        if df.empty or df.index.max() != end_year:
            continue
        run = df[df["run"] == df.loc[end_year, "run"]]["real_dividend"]
        years = run.index.max() - run.index.min()
        if years < BURN_IN or run.iloc[0] <= 0 or run.iloc[-1] <= 0:
            continue
        growth[country] = (run.iloc[-1] / run.iloc[0]) ** (1 / years) - 1
        annual[country] = _annual_growth(run)
    return pd.Series(growth, name="real_dividend_growth"), annual


def dividend_growth_longest_run(panel: pd.DataFrame, end_year: int = JST_END_YEAR) -> pd.Series:
    """Post-hoc sensitivity P1 (docs/decisions.md, 2026-10-28): each country's annualised real
    dividend growth over its longest contiguous run of at least 30 years ending by end_year."""
    growth = {}
    for country, rows in panel.groupby(level="country"):
        df = jst_country(rows.droplevel("country")).loc[:end_year]
        if df.empty:
            continue
        lengths = df.groupby("run")["real_dividend"].apply(lambda r: r.index.max() - r.index.min())
        run = df[df["run"] == lengths.idxmax()]["real_dividend"]
        years = run.index.max() - run.index.min()
        if years >= BURN_IN and run.iloc[0] > 0 and run.iloc[-1] > 0:
            growth[country] = (run.iloc[-1] / run.iloc[0]) ** (1 / years) - 1
    return pd.Series(growth, name="real_dividend_growth_longest_run")


def eps_growth(monthly: pd.DataFrame) -> tuple[float, str, str]:
    """Annualised real EPS growth from the first to the last month with reported earnings."""
    monthly = monthly.loc[: pd.Period(AS_OF, freq="M")]  # cut at the as-of month (Phase 4)
    real = (monthly["earnings"] / monthly["cpi"]).dropna()
    months = (real.index[-1] - real.index[0]).n
    return (
        float((real.iloc[-1] / real.iloc[0]) ** (12 / months) - 1),
        str(real.index[0]),
        str(real.index[-1]),
    )


def gdp_per_capita_growth(panel: pd.DataFrame, end_year: int = JST_END_YEAR) -> pd.Series:
    """Each country's annualised real GDP per capita growth from its first year to end_year."""
    out = {}
    for country, rows in panel.groupby(level="country"):
        g = rows.droplevel("country")["rgdpmad"].loc[:end_year].dropna()
        if len(g) > 1:
            out[country] = (g.iloc[-1] / g.iloc[0]) ** (1 / (g.index[-1] - g.index[0])) - 1
    return pd.Series(out, name="real_gdp_per_capita_growth")


def yield_at(curve: pd.Series, maturity: float) -> float:
    """Linear interpolation between the 5- and 10-year benchmark yields (decimals)."""
    y5, y10 = curve[5], curve[10]
    return float(y5 + (maturity - 5) / 5 * (y10 - y5))


def sgs_curve(yields: pd.DataFrame, as_of: str = AS_OF) -> tuple[pd.Series, str]:
    """The benchmark curve on the last trading day at or before the as-of date."""
    day = yields.loc[:as_of].dropna(subset=[5, 10]).index[-1]
    return yields.loc[day], day.strftime("%Y-%m-%d")


def sgs_nominal(curve: pd.Series) -> dict[str, float]:
    """B1 = yield at A35's duration; B2 = B1 + rolldown (yield at D - yield at D-1) x (D-1)."""
    b1 = yield_at(curve, SGS_DURATION)
    rolldown = (b1 - yield_at(curve, SGS_DURATION - 1)) * (SGS_DURATION - 1)
    return {"B1": b1, "B2": b1 + rolldown, "rolldown": rolldown}


def three_month_spliced(rates: pd.DataFrame) -> pd.Series:
    """Month-end 3-month SGD rate: interbank to Dec 2013, then compounded SORA."""
    interbank = rates["Interbank 3-Month"].loc[:INTERBANK_LAST_MONTH]
    sora = rates["Compound SORA - 3 month"].loc[pd.Period(INTERBANK_LAST_MONTH, "M") + 1 :]
    return pd.concat([interbank, sora]).dropna().rename("sgd_3m")


def cash_long_run(rates: pd.DataFrame, cpi: pd.Series, as_of: str = AS_OF) -> pd.Series:
    """Annual real 3-month rate: each year's average month-end rate minus Dec-to-Dec inflation,
    1988 to the last full year before the as-of date."""
    last = pd.Period(as_of, freq="M").year - 1
    spliced = three_month_spliced(rates)
    by_year = spliced.groupby(spliced.index.year).mean()
    real = by_year - annual_inflation(cpi)
    return real.loc[CASH_START_YEAR:last].dropna().rename("real_3m")


def cash_start(rates: pd.DataFrame, as_of: str = AS_OF) -> float:
    """3-month compounded SORA at the as-of month end (nominal)."""
    return float(
        rates["Compound SORA - 3 month"].loc[: pd.Period(as_of, freq="M")].dropna().iloc[-1]
    )


def cash_cma(start_nominal: float, inflation: float, long_run_real: float) -> float:
    """Average of a linear path from the start real rate to the long-run real rate."""
    return ((start_nominal - inflation) + long_run_real) / 2
