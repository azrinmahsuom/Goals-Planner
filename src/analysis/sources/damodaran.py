"""Aswath Damodaran (NYU): implied equity risk premium for the S&P 500, annual (comparison)."""

from pathlib import Path

import pandas as pd

from analysis.sources.base import RawFile, fixed

URL = "https://pages.stern.nyu.edu/~adamodar/pc/datasets/histimpl.xls"


def _table(path: Path) -> pd.DataFrame:
    raw = pd.read_excel(path, header=None)
    header_row = raw.index[raw[0].astype(str).str.strip() == "Year"][0]
    table = raw.loc[header_row + 1 :].copy()
    table.columns = [str(c).strip() for c in raw.loc[header_row]]
    table["Year"] = pd.to_numeric(table["Year"], errors="coerce")
    return table[table["Year"].between(1900, 2200)].set_index("Year")


def describe(path: Path) -> tuple[int, str, str]:
    years = _table(path).index
    return len(years), f"{years.min():.0f}", f"{years.max():.0f}"


FILES = [
    RawFile(
        source="damodaran",
        filename="histimpl.xls",
        name="Aswath Damodaran, implied equity risk premiums (S&P 500)",
        landing_page="https://pages.stern.nyu.edu/~adamodar/New_Home_Page/data.html",
        series="histimpl.xls: implied ERP (FCFE), T.Bond rate, dividends + buybacks, by year",
        licence="No licence stated by the source; free download. Treated as not redistributable.",
        redistributable=False,
        units="Annual, by year as labelled in the source; US, nominal, decimals.",
        resolve_url=fixed(URL),
        describe=describe,
    )
]


def implied_erp(path: Path = FILES[0].path) -> pd.DataFrame:
    """Implied ERP (FCFE) and the 10-year T-bond rate by year, as decimals."""
    table = _table(path)
    out = table[["Implied ERP (FCFE)", "T.Bond Rate"]].apply(pd.to_numeric, errors="coerce")
    out.columns = ["implied_erp", "tbond_rate"]
    out.index = out.index.astype(int)
    return out.dropna()


def payout_yields(path: Path = FILES[0].path) -> dict[str, float]:
    """Latest year's S&P 500 dividend yield and total payout (dividends + buybacks) yield."""
    table = _table(path)
    cols = ["S&P 500", "Dividends*", "Dividends + Buybacks"]
    row = table[cols].apply(pd.to_numeric, errors="coerce").dropna().iloc[-1]
    return {
        "payout_year": int(row.name),
        "us_dividend_yield": float(row["Dividends*"] / row["S&P 500"]),
        "us_total_payout_yield": float(row["Dividends + Buybacks"] / row["S&P 500"]),
    }
