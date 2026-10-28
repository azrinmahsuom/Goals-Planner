# ruff: noqa: E501  (user-facing text shipped to the page, one string per line)
"""Build app/params.js: everything the public page ships, generated from committed outputs.

Only parameters and computed results are written: no monthly series, raw file or document
(docs/decisions.md, 2026-10-28, Phase 3 pre-registration, section 9).
"""

import json
import math

import pandas as pd

from analysis.cma.report import FIGURES_JSON as CMA_JSON
from analysis.config import REFERENCE, ROOT
from analysis.sim import PATHS, SEED, SGS_DURATION, costs, engine, srs
from analysis.sim.history import h_sgd
from analysis.sim.report import (
    ENGINES,
    EXAMPLES,
    MAIN,
    PLAUSIBLE_SETS,
    SET_LABELS,
    SHOWN_SETS,
    SIM_JSON,
)

APP = ROOT / "app"
PARAMS = APP / "params.js"
STUDENT_T = "Student-t, SGD era"
SET_NOTES = {
    "central": "Today's dividend yield plus long-run dividend growth for shares; today's bond yield for SGS.",
    "P2": "The central share estimate raised by its historical under-forecast (a post-hoc correction).",
    "hist_eq_yield": "The long-run historical share return, with bonds and cash from today's yields.",
    "historical": "Long-run global history for both shares and bonds; shown for reference only.",
}
LICENCES = [
    {
        "item": "Return assumptions and ranges",
        "from": "Robert Shiller data; Jordà-Schularick-Taylor Macrohistory Database (R6); ACWD factsheet; MAS rates and SGS yields; SingStat CPI",
        "rule": "Derived figures only (Shiller, SingStat); CC BY-NC-SA 4.0 with citation (JST); cited figures (factsheet); MAS Terms of Use of Datasets with notice",
    },
    {
        "item": "Fat-tailed return model (Student-t degrees of freedom and scale)",
        "from": "SGD-era monthly returns built from the Kenneth French data library (developed markets), FRED DEXSIUS, MAS SGS yields and SingStat CPI",
        "rule": "Derived summary statistics only; the monthly series are not redistributed (French: no licence stated; SingStat: terms unconfirmed); FRED public domain; MAS notice",
    },
    {
        "item": "Full-engine results for the four examples",
        "from": "The same SGD-era history, resampled in blocks",
        "rule": "Computed results only",
    },
    {
        "item": "Fund costs and trading fee schedule",
        "from": "Issuer documents and broker fee pages, via the author's earlier projects (Multi-Asset-Allocation, ETF-vehicle-selection)",
        "rule": "Cited figures; cost data, not a broker recommendation",
    },
    {
        "item": "SRS rules and resident tax bands",
        "from": "IRAS pages: SRS contributions and tax relief; Tax on SRS withdrawals; Individual income tax rates. MOM: Retirement",
        "rule": "Cited figures, by page title",
    },
    {
        "item": "Near-term inflation cross-check",
        "from": "MAS Survey of Professional Forecasters, September 2026",
        "rule": "MAS Terms of Use of Datasets with notice",
    },
]


def build() -> dict:
    cma = json.loads(CMA_JSON.read_text())
    sim = json.loads(SIM_JSON.read_text())
    fit = engine.fit_student_t(h_sgd())
    fees = costs.load_fees()
    rules = srs.rules()
    bands = pd.read_csv(REFERENCE / "iras_resident_tax_rates.csv")
    gaps = {
        k: {
            s: sim["grid"][k][STUDENT_T][s]["p_goal"] - sim["grid"][k][MAIN][s]["p_goal"]
            for s in SHOWN_SETS
        }
        for k in EXAMPLES
    }
    all_gaps = [g for k in gaps for g in gaps[k].values()]
    validation = {(v["method"], v["sample"]): v for v in cma["validation"]}
    fee_rows = fees.schedule.drop(columns=["repo", "commit", "path", "locator"]).where(
        fees.schedule.notna(), None
    )
    return {
        "generated_from": ["reports/cma_figures.json", "reports/simulation_figures.json"],
        "as_of": cma["as_of"],
        "paths": PATHS,
        "seed": SEED,
        "sets": {
            s: {
                "label": SET_LABELS[s],
                "note": SET_NOTES[s],
                "plausible": s in PLAUSIBLE_SETS,
                **sim["cma_sets"][s],
            }
            for s in SHOWN_SETS
        },
        "central_range": {k: sim["cma_sets"][k] for k in ("low", "high")},
        "student_t": {"df": fit.df, "scale": fit.scale.tolist(), "history": "SGD era, monthly"},
        "history_span": sim["histories"]["H-SGD"],
        "costs": {
            "acwd_ter": fees.acwd_ter,
            "acwd_dividend_yield": fees.acwd_dividend_yield,
            "acwd_withholding": fees.acwd_withholding,
            "a35_ter": fees.a35_ter,
            "mix_trading_bps": {str(k): v for k, v in fees.mix_trading_bps.items()},
            "fee_schedule": fee_rows.to_dict(orient="records"),
        },
        "risk_menu_mixes": [0.49, 0.59, 0.67, 0.88],
        "srs": {
            "contribution_cap_citizen_pr": rules["contribution_cap_citizen_spr"],
            "contribution_cap_foreigner": rules["contribution_cap_foreigner"],
            "relief_cap": rules["personal_relief_cap"],
            "statutory_retirement_age_default": rules["statutory_retirement_age"],
            "statutory_retirement_age_options": [62, 63, 64],
            "taxable_share": rules["taxable_share_penalty_free"],
            "taxable_share_premature": rules["taxable_share_premature"],
            "premature_penalty": rules["premature_penalty"],
            "withdrawal_years": rules["withdrawal_period"],
            "tax_bands": bands[["band_from", "band_to", "rate"]]
            .where(bands.notna(), None)
            .to_dict(orient="records"),
        },
        "presets": {
            k: {
                **{
                    f: ex[f]
                    for f in ("age", "initial", "monthly", "growth", "years", "goal", "equity")
                },
                "srs": bool(ex.get("srs")),
                "full_engine": {s: sim["grid"][k][MAIN][s]["p_goal"] for s in SHOWN_SETS},
                "full_engine_range": {
                    s: sim["grid"][k][MAIN][s]["p_goal"] for s in ("low", "high")
                },
                "gap": gaps[k],
            }
            for k, ex in EXAMPLES.items()
        },
        "engine_gap": {
            "min": min(all_gaps),
            "max": max(all_gaps),
            "lower_count": sum(g < 0 for g in all_gaps),
            "count": len(all_gaps),
        },
        "engine_spread": {
            "min": sim["headline_spread"]["engine_min"],
            "max": sim["headline_spread"]["engine_max"],
            "engines": len(ENGINES),
        },
        "validation": {
            "bond_r2_us": validation[("B1", "Shiller US")]["oos_r2"],
            "bond_r2_jst": validation[("B1", "JST pooled")]["oos_r2"],
            "equity_r2_jst": validation[("D1", "JST pooled")]["oos_r2"],
            "equity_r2_jst_low": validation[("D1", "JST pooled")]["r2_low"],
            "equity_r2_jst_high": validation[("D1", "JST pooled")]["r2_high"],
        },
        "inflation": {
            "cma": cma["inflation"]["cma"],
            "window": cma["inflation"]["window"],
            "mas_spf": cma.get("mas_spf_cpi"),
        },
        "sgs_duration": SGS_DURATION,
        "licences": LICENCES,
        "notices": [
            "Contains information from MAS statistics and the MAS Survey of Professional Forecasters (available from mas.gov.sg), made available under the terms of the Monetary Authority of Singapore's Terms of Use of Datasets.",
            "Figures derived from the Jordà-Schularick-Taylor Macrohistory Database (Jordà et al. 2019, Quarterly Journal of Economics) are licensed CC BY-NC-SA 4.0.",
        ],
    }


def _clean(value):
    """JSON-safe: NaN becomes null, numpy scalars become Python numbers."""
    if isinstance(value, dict):
        return {str(k): _clean(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_clean(v) for v in value]
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def run() -> dict:
    params = _clean(build())
    APP.mkdir(exist_ok=True)
    body = json.dumps(params, indent=1, ensure_ascii=False, allow_nan=False)
    PARAMS.write_text(
        "// Generated by `make app` (analysis.app_params); do not edit by hand.\n"
        f'(typeof window !== "undefined" ? window : globalThis).GOALS_PARAMS = {body};\n'
    )
    return params
