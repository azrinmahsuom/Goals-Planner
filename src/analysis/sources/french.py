"""Kenneth French data library: developed-markets market return (USD), monthly, from 1990."""

import io
import re
import zipfile
from pathlib import Path

import pandas as pd

from analysis.sources.base import RawFile, fixed

FTP = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
LANDING = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html"


def _monthly_table(path: Path) -> pd.DataFrame:
    """The first (monthly) table of the CSV inside the zip: date, Mkt-RF, SMB, HML, RF in %."""
    with zipfile.ZipFile(path) as zf:
        text = zf.read(zf.namelist()[0]).decode("latin-1")
    lines, header = [], None
    for line in text.splitlines():
        if header is None and "Mkt-RF" in line:
            header = ["date"] + [c.strip() for c in line.split(",")[1:]]
            continue
        if header is not None:
            if re.match(r"\s*\d{6}\s*,", line):
                lines.append(line)
            elif lines:
                break  # end of the monthly table (annual figures follow)
    df = pd.read_csv(io.StringIO("\n".join(lines)), header=None, names=header)
    df.index = pd.PeriodIndex(pd.to_datetime(df.pop("date").astype(str), format="%Y%m"), freq="M")
    df.index.name = "month"
    return df


def describe(path: Path) -> tuple[int, str, str]:
    df = _monthly_table(path)
    return len(df), str(df.index[0]), str(df.index[-1])


FILES = [
    RawFile(
        source="french",
        filename="Developed_3_Factors_CSV.zip",
        name="Kenneth French data library: Developed markets 3 factors (monthly)",
        landing_page=LANDING,
        series="Developed_3_Factors (Mkt-RF, RF)",
        licence="No licence stated by the source; free download. Treated as not redistributable.",
        redistributable=False,
        units="Monthly, % per month, USD. Market = Mkt-RF + RF (value-weighted developed markets).",
        resolve_url=fixed(FTP + "Developed_3_Factors_CSV.zip"),
        describe=describe,
    )
]


def developed_market(path: Path = FILES[0].path) -> pd.Series:
    """Monthly developed-markets total return in USD (decimal)."""
    df = _monthly_table(path)
    return ((df["Mkt-RF"] + df["RF"]) / 100).rename("developed_usd")
