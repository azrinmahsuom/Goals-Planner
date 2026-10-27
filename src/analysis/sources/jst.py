"""Jordà-Schularick-Taylor Macrohistory Database (R6): 18 countries, annual, 1870-2020."""

from pathlib import Path

import pandas as pd

from analysis.sources.base import RawFile, link_on_page

LANDING = "https://www.macrohistory.net/database/"
LICENCE = (
    "CC BY-NC-SA 4.0 (macrohistory.net/database/licence-terms/). Non-commercial use, "
    "citation required (Jordà et al. 2019, QJE), share-alike."
)
CREDIT = (
    "Source: Jordà-Schularick-Taylor Macrohistory Database (R6); Jordà et al. (2019), QJE. "
    "Licensed CC BY-NC-SA 4.0."
)
COLUMNS = ["eq_tr", "eq_capgain", "eq_dp", "bond_tr", "ltrate", "cpi"]


def describe(path: Path) -> tuple[int, str, str]:
    df = pd.read_excel(path, usecols=["year", "country"])
    return len(df), str(df["year"].min()), str(df["year"].max())


FILES = [
    RawFile(
        source="jst",
        filename="JSTdatasetR6.xlsx",
        name="Jordà-Schularick-Taylor Macrohistory Database",
        landing_page=LANDING,
        series="JSTdatasetR6.xlsx (country-year panel)",
        licence=LICENCE,
        redistributable=True,
        units=(
            "Annual, local currency. eq_tr, eq_capgain, bond_tr: nominal returns (decimal); "
            "eq_dp: dividend-price ratio; ltrate: long-term government bond yield (% p.a.); "
            "cpi: consumer price index."
        ),
        resolve_url=link_on_page(LANDING, r"JSTdataset\w*\.xlsx"),
        describe=describe,
    )
]


def annual(path: Path = FILES[0].path) -> pd.DataFrame:
    """Country-year panel of the columns the CMA validation uses, ltrate as a decimal."""
    raw = pd.read_excel(path, usecols=["year", "country", *COLUMNS])
    raw["ltrate"] = raw["ltrate"] / 100
    return raw.sort_values(["country", "year"]).set_index(["country", "year"])
