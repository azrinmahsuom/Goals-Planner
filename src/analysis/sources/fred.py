"""FRED series: US constant-maturity yields (for the rolldown test) and SGD per USD."""

from pathlib import Path

import pandas as pd

from analysis.sources.base import RawFile, fixed

LICENCE = "Public domain, citation requested (FRED series page)."
SERIES = {
    "GS5": ("5-year Treasury constant maturity yield", "Monthly average, % p.a."),
    "GS10": ("10-year Treasury constant maturity yield", "Monthly average, % p.a."),
    "EXSIUS": ("Singapore dollars to one US dollar", "Monthly average, SGD per USD"),
}


def describe(path: Path) -> tuple[int, str, str]:
    df = pd.read_csv(path)
    return len(df), str(df.iloc[0, 0])[:7], str(df.iloc[-1, 0])[:7]


FILES = [
    RawFile(
        source="fred",
        filename=f"{series_id}.csv",
        name=f"FRED: {title}",
        landing_page=f"https://fred.stlouisfed.org/series/{series_id}",
        series=series_id,
        licence=LICENCE,
        redistributable=True,
        units=units,
        resolve_url=fixed(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"),
        describe=describe,
    )
    for series_id, (title, units) in SERIES.items()
]


def monthly(series: list[str] | None = None) -> pd.DataFrame:
    """Monthly FRED series side by side; yields stay in % p.a. as published."""
    frames = []
    for series_id in series or list(SERIES):
        df = pd.read_csv(FILES[list(SERIES).index(series_id)].path)
        df.columns = ["date", series_id]
        df[series_id] = pd.to_numeric(df[series_id], errors="coerce")
        df.index = pd.PeriodIndex(pd.to_datetime(df.pop("date")), freq="M", name="month")
        frames.append(df)
    return pd.concat(frames, axis=1)
