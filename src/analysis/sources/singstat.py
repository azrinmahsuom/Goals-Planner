"""Singapore Department of Statistics: CPI, all items, monthly (table M213751)."""

import json
from pathlib import Path

import pandas as pd

from analysis.sources.base import RawFile, fixed

TABLE = "M213751"


def describe(path: Path) -> tuple[int, str, str]:
    columns = json.loads(path.read_text())["Data"]["row"][0]["columns"]
    months = [pd.to_datetime(c["key"], format="%Y %b") for c in columns]
    return len(months), min(months).strftime("%Y-%m"), max(months).strftime("%Y-%m")


FILES = [
    RawFile(
        source="singstat",
        filename=f"{TABLE}_cpi_monthly.json",
        name="Singapore Department of Statistics, CPI (2024 = 100), monthly",
        landing_page=f"https://tablebuilder.singstat.gov.sg/table/TS/{TABLE}",
        series=f"{TABLE}, All Items index (and sub-indices), not seasonally adjusted",
        licence=(
            "Terms not confirmed (singstat.gov.sg/terms-of-use returned no text on 2026-10-28). "
            "Treated as not redistributable; only derived figures are shown, with citation."
        ),
        redistributable=False,
        units="Monthly index, 2024 = 100, NSA.",
        resolve_url=fixed(f"https://tablebuilder.singstat.gov.sg/api/table/tabledata/{TABLE}"),
        describe=describe,
    )
]


def cpi_monthly(path: Path = FILES[0].path) -> pd.Series:
    """All-items CPI index by month."""
    rows = json.loads(path.read_text())["Data"]["row"]
    all_items = next(r for r in rows if r["rowText"].strip().lower() == "all items")
    index = pd.Series(
        {
            pd.Period(pd.to_datetime(c["key"], format="%Y %b"), freq="M"): float(c["value"])
            for c in all_items["columns"]
        }
    ).sort_index()
    index.index.name = "month"
    return index.rename("sg_cpi")
