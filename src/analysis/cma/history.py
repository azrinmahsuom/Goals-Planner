"""Annual series built from the sources, for the historical forecasts.

Shiller (monthly) becomes one row per December origin. Inputs follow the pre-registered
3-month publication lag: December price, with dividends, earnings and CPI as of September.
JST stays annual; series with gaps are split into contiguous runs, and nothing (growth rates,
levels, realised returns) is carried across a gap.
"""

import numpy as np
import pandas as pd

LAG_MONTH = 9  # September values are the latest known at a December origin
CAPE_MONTHS = 120


def shiller_annual(monthly: pd.DataFrame) -> pd.DataFrame:
    """One row per year: December price, September D/E/CPI, CAPE known at the origin, and
    December total-return and bond indices (nominal and real) for realised returns.

    The data end at the last month with a reported dividend; later months are estimates."""
    m = monthly.loc[: monthly["dividend"].last_valid_index()].copy()
    m["tr_index"] = ((m["price"] + m["dividend"] / 12) / m["price"].shift(1)).fillna(1).cumprod()
    m["bond_index"] = (1 + m["bond_tr"].fillna(0)).cumprod()
    m["real_eps"] = m["earnings"] / m["cpi"]
    # Average real earnings over the 120 months to each month (a month's own CPI deflates it).
    m["avg_real_eps_10y"] = m["real_eps"].rolling(CAPE_MONTHS, min_periods=CAPE_MONTHS).mean()

    dec = m[m.index.month == 12]
    sep = m[m.index.month == LAG_MONTH]
    out = pd.DataFrame(index=pd.Index(dec.index.year, name="year"))
    out["price"] = dec["price"].to_numpy()
    out["cpi_dec"] = dec["cpi"].to_numpy()
    out["gs10"] = dec["gs10"].to_numpy()
    out["tr_index"] = dec["tr_index"].to_numpy()
    out["bond_index"] = dec["bond_index"].to_numpy()
    lagged = sep.set_index(sep.index.year)
    out["dividend"] = lagged["dividend"].reindex(out.index)
    out["earnings"] = lagged["earnings"].reindex(out.index)
    out["cpi_lag"] = lagged["cpi"].reindex(out.index)
    out["cape"] = (out["price"] / out["cpi_lag"]) / lagged["avg_real_eps_10y"].reindex(out.index)
    out["real_tr_index"] = out["tr_index"] / out["cpi_dec"]
    return out


def contiguous_runs(valid: pd.Series) -> pd.Series:
    """Run id for each year where `valid` is True; NaN where it is False. A new run starts
    after any invalid year or a missing year in the index."""
    years = valid.index.to_numpy()
    new_run = np.r_[True, np.diff(years) != 1] | ~valid.shift(1, fill_value=False).to_numpy()
    run = pd.Series(np.cumsum(new_run), index=valid.index, dtype=float)
    return run.where(valid)


def jst_country(panel: pd.DataFrame) -> pd.DataFrame:
    """One country's annual levels within contiguous runs of complete equity and CPI data.

    price_index cumulates eq_capgain; dividend = eq_dp x price_index; real_tr_index cumulates
    eq_tr and deflates by cpi. Each run starts its own levels at 1."""
    df = panel.sort_index().copy()
    valid = df[["eq_tr", "eq_capgain", "eq_dp", "cpi"]].notna().all(axis=1)
    df["run"] = contiguous_runs(valid)
    df = df[df["run"].notna()].copy()
    by_run = df.groupby("run", group_keys=False)
    df["price_index"] = by_run["eq_capgain"].apply(lambda r: (1 + r).cumprod())
    df["tr_index"] = by_run["eq_tr"].apply(lambda r: (1 + r).cumprod())
    df["real_tr_index"] = df["tr_index"] / df["cpi"]
    df["real_dividend"] = df["eq_dp"] * df["price_index"] / df["cpi"]
    return df


def jst_bond_country(panel: pd.DataFrame) -> pd.DataFrame:
    """One country's nominal bond total-return index within contiguous runs of bond_tr and
    ltrate."""
    df = panel.sort_index().copy()
    df["run"] = contiguous_runs(df[["bond_tr", "ltrate"]].notna().all(axis=1))
    df = df[df["run"].notna()].copy()
    df["bond_index"] = df.groupby("run", group_keys=False)["bond_tr"].apply(
        lambda r: (1 + r).cumprod()
    )
    return df
