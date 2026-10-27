"""Historical forecasts for each pre-registered method, made with data up to each origin.

Every function returns a frame indexed by origin year with columns forecast, realised and
historical_mean, ready for validate.evaluate. Forecasts before the burn-in are NaN; realised
and historical_mean are kept for every origin, because the benchmark needs early windows.
"""

import pandas as pd

from analysis.cma import BURN_IN, HORIZON
from analysis.cma.history import jst_bond_country, jst_country
from analysis.cma.validate import annualised, historical_mean


def _growth_since_start(level: pd.Series, start: pd.Series) -> pd.Series:
    """Annualised growth of `level` from the year `start` gives to each year (NaN if the
    endpoints aren't positive or no time has passed)."""
    first = level.groupby(start).transform("first")
    years = pd.Series(level.index, index=level.index) - start
    ratio = (level / first).where((level > 0) & (first > 0))
    return (ratio ** (1 / years.where(years > 0)) - 1).astype(float)


def _realised_in_run(level: pd.Series, run: pd.Series, years: int = HORIZON) -> pd.Series:
    """Annualised return from t to t + years, only where both years are in the same run."""
    shifted_index = level.index + years
    future = pd.Series(level.reindex(shifted_index).to_numpy(), index=level.index)
    same_run = pd.Series(run.reindex(shifted_index).to_numpy(), index=level.index) == run
    return annualised((future / level).where(same_run), years)


def _frame(forecast: pd.Series, realised: pd.Series, burn_in_from: pd.Series) -> pd.DataFrame:
    years_of_data = pd.Series(forecast.index, index=forecast.index) - burn_in_from
    out = pd.DataFrame(
        {
            "forecast": forecast.where(years_of_data >= BURN_IN),
            "realised": realised,
        }
    )
    out["historical_mean"] = historical_mean(out["realised"])
    out.index.name = "origin"
    return out


# --- Shiller US: E1, E2, E3, D1 ---


def shiller_equity(annual: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """E1, E2, E3 and D1 forecasts on Shiller US data (real, annualised over 10 years)."""
    a = annual.dropna(subset=["price", "dividend", "earnings", "cpi_lag"])
    start = pd.Series(a.index.min(), index=a.index)
    y = a["dividend"] / a["price"]
    g_eps = _growth_since_start(a["earnings"] / a["cpi_lag"], start)
    g_div = _growth_since_start(a["dividend"] / a["cpi_lag"], start)
    cape = a["cape"]
    anchor = cape.expanding().median()  # medians of CAPE values known at or before each origin

    e1 = y + g_eps
    forecasts = {
        "E1": e1,
        "E2": e1 + (anchor / cape) ** (1 / HORIZON) - 1,
        "E3": 1 / cape,
        "D1": y + g_div,
    }
    run = pd.Series(1.0, index=annual.index)
    realised = _realised_in_run(annual["real_tr_index"], run).reindex(a.index)
    return {name: _frame(f, realised, start) for name, f in forecasts.items()}


# --- JST: D1 per country ---


def jst_d1(panel: pd.DataFrame, end_year: int | None = None) -> dict[str, pd.DataFrame]:
    """D1 = dividend yield + expanding real dividend growth, per JST country (local currency,
    real). Growth and the burn-in restart after any gap in the data."""
    out = {}
    for country, rows in panel.groupby(level="country"):
        df = jst_country(rows.droplevel("country"))
        if end_year is not None:
            df = df.loc[:end_year]
        if df.empty:
            continue
        start = df.groupby("run")["run"].transform(lambda r: r.index.min())
        g_div = _growth_since_start(df["real_dividend"], start)
        forecast = df["eq_dp"].where(df["eq_dp"] > 0) + g_div
        realised = _realised_in_run(df["real_tr_index"], df["run"])
        out[country] = _frame(forecast, realised, start)
    return out


# --- Bonds: B1 (starting yield) and B2 (plus rolldown), nominal ---


def shiller_bonds(annual: pd.DataFrame, fred_dec: pd.DataFrame | None = None) -> dict:
    """US B1: the 10-year yield at the origin vs the realised nominal 10-year bond return.
    B2 adds rolldown = (GS10 - GS5) / 5 x 9 from FRED December yields (from 1953), the
    one-year roll from 10 to 9 years on a linear 5-10 year curve."""
    start = pd.Series(annual.index.min(), index=annual.index)
    run = pd.Series(1.0, index=annual.index)
    realised = _realised_in_run(annual["bond_index"], run)
    frames = {"B1": _frame(annual["gs10"], realised, start)}
    if fred_dec is not None:
        slope = (fred_dec["GS10"] - fred_dec["GS5"]) / 100 / 5
        rolldown = (slope * (HORIZON - 1)).reindex(annual.index)
        frames["B2"] = _frame(annual["gs10"] + rolldown, realised, start)
    return frames


def jst_b1(panel: pd.DataFrame, end_year: int | None = None) -> dict[str, pd.DataFrame]:
    """JST B1 per country: ltrate at the origin vs the realised nominal 10-year bond return."""
    out = {}
    for country, rows in panel.groupby(level="country"):
        df = jst_bond_country(rows.droplevel("country"))
        if end_year is not None:
            df = df.loc[:end_year]
        if df.empty:
            continue
        start = df.groupby("run")["run"].transform(lambda r: r.index.min())
        realised = _realised_in_run(df["bond_index"], df["run"])
        out[country] = _frame(df["ltrate"], realised, start)
    return out


def same_origins(a: pd.DataFrame, b: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Restrict two method frames to origins where both have a forecast (for B1 vs B2)."""
    both = a["forecast"].notna() & b["forecast"].reindex(a.index).notna()
    keep = a.index[both]
    return a.loc[keep], b.loc[keep]
