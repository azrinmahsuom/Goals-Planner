"""Run every pre-registered validation on the real data and save the statistics.

Writes data/processed/cma_validation.csv (one row per method and sample) and
data/processed/cma_validation_by_country.csv (JST, one row per method and country).
"""

import pandas as pd

from analysis.cma import JST_END_YEAR, history, methods, validate
from analysis.config import DATA_PROCESSED
from analysis.sources import fred, jst, shiller

SUMMARY = DATA_PROCESSED / "cma_validation.csv"
BY_COUNTRY = DATA_PROCESSED / "cma_validation_by_country.csv"


def _row(method: str, sample: str, stats: dict, basis: str) -> dict:
    return {"method": method, "sample": sample, "basis": basis, **stats}


def run() -> pd.DataFrame:
    """Evaluate E1-E3 and D1 (real) and B1/B2 (nominal) on Shiller US, and D1 and B1 on the
    JST countries to JST_END_YEAR, per country and pooled."""
    annual = history.shiller_annual(shiller.monthly())
    rows = []
    for name, frame in methods.shiller_equity(annual).items():
        rows.append(_row(name, "Shiller US", validate.evaluate(frame), "real"))

    fred_monthly = fred.monthly(["GS5", "GS10"])
    fred_dec = fred_monthly[fred_monthly.index.month == 12].set_index(
        fred_monthly.index[fred_monthly.index.month == 12].year
    )
    bonds = methods.shiller_bonds(annual, fred_dec)
    b1_common, b2_common = methods.same_origins(bonds["B1"], bonds["B2"])
    rows.append(_row("B1", "Shiller US", validate.evaluate(bonds["B1"]), "nominal"))
    rows.append(_row("B1", "Shiller US, B2 origins", validate.evaluate(b1_common), "nominal"))
    rows.append(_row("B2", "Shiller US, B2 origins", validate.evaluate(b2_common), "nominal"))

    panel = jst.annual()
    country_rows = []
    for name, frames, basis in (
        ("D1", methods.jst_d1(panel, JST_END_YEAR), "real"),
        ("B1", methods.jst_b1(panel, JST_END_YEAR), "nominal"),
    ):
        usable = {c: f for c, f in frames.items() if f["forecast"].notna().any()}
        for country, frame in usable.items():
            stats = validate.evaluate(frame)
            if stats["origins"]:
                country_rows.append(_row(name, country, stats, basis))
        rows.append(_row(name, "JST pooled", validate.evaluate_pooled(usable), basis))

    summary = pd.DataFrame(rows)
    by_country = pd.DataFrame(country_rows)
    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    summary.to_csv(SUMMARY, index=False)
    by_country.to_csv(BY_COUNTRY, index=False)
    return summary
