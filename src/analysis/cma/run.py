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


def _row(method: str, sample: str, frame: pd.DataFrame, basis: str) -> dict:
    """Statistics plus the bootstrap 95% interval for the out-of-sample R²."""
    low, high = validate.r2_interval(frame)
    stats = validate.evaluate(frame)
    return {
        "method": method,
        "sample": sample,
        "basis": basis,
        **stats,
        "r2_low": low,
        "r2_high": high,
    }


def _pooled_row(method: str, frames: dict[str, pd.DataFrame], basis: str) -> dict:
    low, high = validate.r2_interval_pooled(frames)
    stats = validate.evaluate_pooled(frames)
    return {
        "method": method,
        "sample": "JST pooled",
        "basis": basis,
        **stats,
        "r2_low": low,
        "r2_high": high,
    }


def run() -> pd.DataFrame:
    """Evaluate E1-E3 and D1 (real) and B1/B2 (nominal) on Shiller US, and D1 and B1 on the
    JST countries to JST_END_YEAR, per country and pooled."""
    annual = history.shiller_annual(shiller.monthly())
    rows = []
    for name, frame in methods.shiller_equity(annual).items():
        rows.append(_row(name, "Shiller US", frame, "real"))

    fred_monthly = fred.monthly(["GS5", "GS10"])
    fred_dec = fred_monthly[fred_monthly.index.month == 12].set_index(
        fred_monthly.index[fred_monthly.index.month == 12].year
    )
    bonds = methods.shiller_bonds(annual, fred_dec)
    b1_common, b2_common = methods.same_origins(bonds["B1"], bonds["B2"])
    rows.append(_row("B1", "Shiller US", bonds["B1"], "nominal"))
    rows.append(_row("B1", "Shiller US, B2 origins", b1_common, "nominal"))
    rows.append(_row("B2", "Shiller US, B2 origins", b2_common, "nominal"))

    panel = jst.annual()
    country_rows = []
    for name, frames, basis in (
        ("D1", methods.jst_d1(panel, JST_END_YEAR), "real"),
        ("B1", methods.jst_b1(panel, JST_END_YEAR), "nominal"),
    ):
        usable = {c: f for c, f in frames.items() if f["forecast"].notna().any()}
        for country, frame in usable.items():
            if frame[["forecast", "realised", "historical_mean"]].dropna().shape[0]:
                country_rows.append(_row(name, country, frame, basis))
        rows.append(_pooled_row(name, usable, basis))

    summary = pd.DataFrame(rows)
    by_country = pd.DataFrame(country_rows)
    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    summary.to_csv(SUMMARY, index=False)
    by_country.to_csv(BY_COUNTRY, index=False)
    return summary
