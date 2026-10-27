"""MAS statistics: domestic interest rates (interbank, SORA) and SGS benchmark yields.

The download functions submit the MAS ASP.NET forms; they are adapted from
Multi-Asset-Allocation (commit a92a325), which checked the form fields on 2026-10-27, and they
re-check every field label before submitting so a changed form fails loudly.
"""

import re
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from analysis.sources.base import HEADERS, TIMEOUT, RawFile, fixed

RATES_PAGE = "https://eservices.mas.gov.sg/statistics/dir/DomesticInterestRates.aspx"
SGS_PAGE = "https://eservices.mas.gov.sg/statistics/fdanet/BenchmarkPricesAndYields.aspx"
LICENCE = (
    "MAS Terms of Use of Datasets (mas.gov.sg/terms-of-use): royalty-free licence to use and "
    "distribute, with a notice acknowledging MAS as the source."
)
# Checkbox positions on the rates form, checked against their labels by the download.
RATE_COLUMNS = {
    0: "Interbank Overnight",
    4: "Interbank 3-month",
    13: "SORA",
    14: "SORA Index",
    16: "3-month Compounded SORA",
}
SGS_TENORS = ["Two", "Five", "Seven", "Ten", "Fifteen", "Twenty", "Thirty"]
PREFIX = "ctl00$ContentPlaceHolder1$"


def _hidden_fields(html: str) -> dict[str, str]:
    return dict(re.findall(r'<input type="hidden" name="([^"]+)" id="[^"]*" value="([^"]*)"', html))


def _post_csv(session: requests.Session, url: str, form: dict, timeout: int) -> bytes:
    response = session.post(url, data=form, timeout=timeout)
    response.raise_for_status()
    if "text/csv" not in response.headers.get("content-type", ""):
        raise RuntimeError("MAS did not return a CSV. The form may have changed.")
    return response.content


def download_rates(url: str) -> bytes:
    """Daily domestic interest rates, January 1987 to December of the current year."""
    session = requests.Session()
    session.headers.update(HEADERS)
    page = session.get(url, timeout=TIMEOUT)
    page.raise_for_status()
    labels = dict(
        re.findall(r'for="ContentPlaceHolder1_ColumnsCheckBoxList_(\d+)">([^<]*)', page.text)
    )
    for i, label in RATE_COLUMNS.items():
        if labels.get(str(i), "").strip().lower() != label.lower():
            raise RuntimeError(f"MAS form column {i} is {labels.get(str(i))!r}, not {label!r}.")
    form = _hidden_fields(page.text)
    form.update(
        {
            PREFIX + "StartYearDropDownList": "1987",
            PREFIX + "EndYearDropDownList": str(pd.Timestamp.today().year),
            PREFIX + "StartMonthDropDownList": "1",
            PREFIX + "EndMonthDropDownList": "12",
            PREFIX + "Button2": "Download",
        }
    )
    form.update({f"{PREFIX}ColumnsCheckBoxList${i}": "on" for i in RATE_COLUMNS})
    return _post_csv(session, url, form, TIMEOUT)


def download_sgs(url: str) -> bytes:
    """Daily SGS benchmark yields for every tenor, 1988 to this year."""
    session = requests.Session()
    session.headers.update(HEADERS)
    page = session.get(url, timeout=TIMEOUT)
    page.raise_for_status()
    for tenor in SGS_TENORS:
        if f"{PREFIX}{tenor}YearBondYieldCheckBox" not in page.text:
            raise RuntimeError(f"MAS SGS form has no {tenor}-year yield box; it may have changed.")
    form = _hidden_fields(page.text)
    form.update(
        {
            PREFIX + "StartYearDropDownList": "1988",
            PREFIX + "StartMonthDropDownList": "1",
            PREFIX + "EndYearDropDownList": str(pd.Timestamp.today().year),
            PREFIX + "EndMonthDropDownList": "12",
            PREFIX + "FrequencyDropDownList": "D",
            PREFIX + "DownloadButton": "Download",
        }
    )
    form.update({f"{PREFIX}{t}YearBondYieldCheckBox": "on" for t in SGS_TENORS})
    return _post_csv(session, url, form, TIMEOUT * 2)


def _dated_rows(path: Path) -> list[tuple[pd.Timestamp, list[str]]]:
    """(date, cells) for every data line. MAS leaves year and month blank after their first
    row, e.g. "1987,Jul,01,2.75" then ",,02,7.00"."""
    rows, year, month = [], None, None
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 4 or not parts[2].isdigit():
            continue
        year, month = parts[0] or year, parts[1] or month
        rows.append((pd.to_datetime(f"{year} {month} {parts[2]}", format="%Y %b %d"), parts[3:]))
    return rows


def describe(path: Path) -> tuple[int, str, str]:
    dates = [d for d, cells in _dated_rows(path) if any(c not in ("", "-") for c in cells)]
    return len(dates), min(dates).strftime("%Y-%m-%d"), max(dates).strftime("%Y-%m-%d")


FILES = [
    RawFile(
        source="mas",
        filename="domestic_interest_rates.csv",
        name="Monetary Authority of Singapore, Domestic Interest Rates",
        landing_page=RATES_PAGE,
        series=", ".join(RATE_COLUMNS.values()) + " (daily)",
        licence=LICENCE,
        redistributable=True,
        units=(
            "Daily, % p.a., SGD. Interbank rates Jul 1987 to Dec 2013 (discontinued by MAS from "
            "1 Jan 2014). SORA and 3-month compounded SORA (backward-looking) from 2005."
        ),
        resolve_url=fixed(RATES_PAGE),
        describe=describe,
        download=download_rates,
    ),
    RawFile(
        source="mas",
        filename="sgs_benchmark_yields.csv",
        name="Monetary Authority of Singapore, SGS benchmark prices and yields",
        landing_page=SGS_PAGE,
        series="SGS benchmark yields, 2/5/7/10/15/20/30-year (daily)",
        licence=LICENCE,
        redistributable=True,
        units="Daily, % p.a., SGD. The 7-year benchmark was discontinued on 1 February 2011.",
        resolve_url=fixed(SGS_PAGE),
        describe=describe,
        download=download_sgs,
    ),
]


def rate_tables(path: Path = FILES[0].path) -> list[pd.DataFrame]:
    """Every table in the rates CSV as a daily frame of floats ('-' becomes missing).

    A table starts at a header line whose text differs from the current one; the file repeats
    the same header every year inside a table."""
    tables, header, rows, year, month = [], None, [], None, None
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        parts = [p.strip() for p in line.split(",")]
        if parts[0].startswith(("End of Period", "SORA Value Date")):
            names = [p for p in parts[3:] if p]
            if names != header:
                if rows:
                    tables.append(_frame(rows, header))
                header, rows = names, []
            continue
        if len(parts) < 4 or not parts[2].isdigit() or header is None:
            continue
        year, month = parts[0] or year, parts[1] or month
        date = pd.to_datetime(f"{year} {month} {parts[2]}", format="%Y %b %d")
        rows.append([date, *parts[3 : 3 + len(header)]])
    if rows:
        tables.append(_frame(rows, header))
    return tables


def _frame(rows: list[list], header: list[str]) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=["date", *header]).set_index("date")
    return df.apply(pd.to_numeric, errors="coerce")


def three_month_rates(path: Path = FILES[0].path) -> pd.DataFrame:
    """Month-end 3-month SGD rates as decimals: interbank (to 2013) and compounded SORA."""
    out = {}
    for column in ("Interbank 3-Month", "Compound SORA - 3 month"):  # CSV headers, not form labels
        table = next(t for t in rate_tables(path) if column in t.columns)
        series = table[column].dropna() / 100
        out[column] = series.groupby(series.index.to_period("M")).last()
    df = pd.DataFrame(out)
    df.index.name = "month"
    return df


def sgs_yields(path: Path = FILES[1].path) -> pd.DataFrame:
    """Daily SGS benchmark yields (decimals), one column per tenor in years."""
    rows, tenors, year, month = [], None, None, None
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        parts = [p.strip() for p in line.split(",")]
        if tenors is None and len(parts) > 3 and "Bond Yield" in line:
            tenors = [int(re.search(r"(\d+)-Year", p).group(1)) for p in parts[3:] if p]
            continue
        if tenors is None or len(parts) < 4 or not parts[2].isdigit():
            continue
        year, month = parts[0] or year, parts[1] or month
        date = pd.to_datetime(f"{year} {month} {parts[2]}", format="%Y %b %d")
        cells = parts[3 : 3 + len(tenors)]
        rows.append([date, *(float(v) / 100 if v not in ("", "-") else np.nan for v in cells)])
    return pd.DataFrame(rows, columns=["date", *tenors]).set_index("date").sort_index()
