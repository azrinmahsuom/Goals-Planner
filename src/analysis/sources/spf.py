"""Philadelphia Fed Survey of Professional Forecasters: 10-year median forecasts (comparison)."""

from pathlib import Path

import pandas as pd

from analysis.sources.base import RawFile, link_on_page

BASE = "https://www.philadelphiafed.org/surveys-and-data/"
SERIES = {
    "STOCK10": "10-year average annual S&P 500 return",
    "BOND10": "10-year average 10-year Treasury yield",
    "BILL10": "10-year average 3-month Treasury bill return",
    "CPI10": "10-year average annual CPI inflation",
}


def describe(path: Path) -> tuple[int, str, str]:
    df = pd.read_excel(path).dropna()
    first, last = df.iloc[0], df.iloc[-1]
    return (
        len(df),
        f"{first['YEAR']:.0f}Q{first['QUARTER']:.0f}",
        f"{last['YEAR']:.0f}Q{last['QUARTER']:.0f}",
    )


FILES = [
    RawFile(
        source="spf",
        filename=f"Median_{series_id}_Level.xlsx",
        name=f"Philadelphia Fed SPF, median {series_id}: {title}",
        landing_page=BASE + series_id.lower(),
        series=series_id,
        licence=(
            "Terms page not found on 2026-10-28; treated as not redistributable. Figures cited "
            "with source only."
        ),
        redistributable=False,
        units="% a year, US, nominal; median across forecasters; survey quarter in YEAR/QUARTER.",
        resolve_url=link_on_page(BASE + series_id.lower(), rf"Median_{series_id}_Level\.xlsx"),
        describe=describe,
    )
    for series_id, title in SERIES.items()
]


def medians() -> pd.DataFrame:
    """Median forecasts by survey quarter, one column per series, as decimals."""
    frames = []
    for raw in FILES:
        df = pd.read_excel(raw.path).dropna()
        df.index = pd.PeriodIndex.from_fields(
            year=df["YEAR"].astype(int), quarter=df["QUARTER"].astype(int), freq="Q"
        )
        frames.append((df[raw.series] / 100).rename(raw.series))
    out = pd.concat(frames, axis=1)
    out.index.name = "survey"
    return out
