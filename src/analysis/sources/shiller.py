"""Robert Shiller's US stock market data (S&P Composite, CPI, 10-year yield), monthly from 1871."""

from pathlib import Path

import pandas as pd

from analysis.sources.base import RawFile, link_on_page

LANDING = "https://shillerdata.com/"
NO_LICENCE = "No licence stated by the source; free download. Treated as not redistributable."
# "Monthly Total Bond Returns" (gross, 1 + r). Row t holds the return from month t to t + 1 on a
# 10-year par bond (semi-annual coupons) repriced at the next month's GS10: reverse-engineered on
# 2026-10-28 (correlation 0.99999, mean gap 0.57 bp a month). monthly() shifts it to row t + 1.
BOND_TR_COLUMN = 17


def _month(value: float) -> pd.Period:
    """Shiller dates are year.month floats where 1871.1 means October: format to 2 dp."""
    year, month = f"{value:.2f}".split(".")
    return pd.Period(f"{year}-{month}", freq="M")


def describe(path: Path) -> tuple[int, str, str]:
    df = pd.read_excel(path, sheet_name="Data", header=7)
    dates = pd.to_numeric(df["Date"], errors="coerce").dropna()
    return len(dates), str(_month(dates.iloc[0])), str(_month(dates.iloc[-1]))


FILES = [
    RawFile(
        source="shiller",
        filename="ie_data.xls",
        name="Robert Shiller online data",
        landing_page=LANDING,
        series="ie_data.xls, sheet Data",
        licence=NO_LICENCE,
        redistributable=False,
        units=(
            "Monthly. P: S&P Composite price (monthly average of daily closes); D, E: "
            "dividends and earnings per share, annualised, USD; CPI: US CPI-U index; "
            "Rate GS10: 10-year Treasury yield, % p.a.; total bond returns (gross, monthly)."
        ),
        resolve_url=link_on_page(LANDING, r"ie_data\.xls"),
        describe=describe,
    )
]


def monthly(path: Path = FILES[0].path) -> pd.DataFrame:
    """Price, dividend, earnings, CPI, 10-year yield (decimal) and bond total return by month.

    Months after the last reported dividend are kept for prices but carry NaN in D and E; the
    file marks the newest CPI and prices as estimates, so callers decide where to stop.
    """
    raw = pd.read_excel(path, sheet_name="Data", header=7)
    raw = raw[pd.to_numeric(raw["Date"], errors="coerce").notna()].copy()
    out = pd.DataFrame(index=pd.PeriodIndex([_month(d) for d in raw["Date"]], name="month"))
    out["price"] = pd.to_numeric(raw["P"], errors="coerce").to_numpy()
    out["dividend"] = pd.to_numeric(raw["D"], errors="coerce").to_numpy()
    out["earnings"] = pd.to_numeric(raw["E"], errors="coerce").to_numpy()
    out["cpi"] = pd.to_numeric(raw["CPI"], errors="coerce").to_numpy()
    out["gs10"] = pd.to_numeric(raw["Rate GS10"], errors="coerce").to_numpy() / 100
    bond_gross = pd.to_numeric(raw.iloc[:, BOND_TR_COLUMN], errors="coerce").to_numpy()
    out["bond_tr"] = pd.Series(bond_gross - 1, index=out.index).shift(1)  # return into month t
    return out
