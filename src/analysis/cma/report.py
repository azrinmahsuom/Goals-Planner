# ruff: noqa: E501  (the docs/cma.md template below is prose, one paragraph per line)
"""Forward CMAs, scenarios and comparison -> reports/cma_figures.json, a figure, docs/cma.md.

Every number in docs/cma.md is formatted from reports/cma_figures.json (or cited from
reference/). If a committed cma_figures.json exists, a rebuild that moves any headline
scenario value by more than DRIFT_TOLERANCE_BPS is written to the drift report and stops.
"""

import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from analysis import upstream  # noqa: E402
from analysis.cma import AS_OF, JST_END_YEAR, forward, history, methods  # noqa: E402
from analysis.cma import scenarios as sc  # noqa: E402
from analysis.cma.run import BY_COUNTRY, SUMMARY  # noqa: E402
from analysis.config import (  # noqa: E402
    DOCS,
    DRIFT_REPORT,
    DRIFT_TOLERANCE_BPS,
    FIGURES,
    REPORTS,
    ROOT,
)
from analysis.sources import damodaran, documents, fred, jst, mas, shiller, singstat, spf  # noqa: E402

FIGURES_JSON = REPORTS / "cma_figures.json"
CMA_DOC = DOCS / "cma.md"
CHART = FIGURES / "cma_validation_us.png"
BLUE, ORANGE, INK, MUTED, SURFACE = "#2a78d6", "#eb6834", "#0b0b0b", "#52514e", "#fcfcfb"
ASSETS = {
    "global_equity_sgd": "Global equities (SGD, unhedged)",
    "sgs": "Singapore Government Securities",
    "sgd_cash": "SGD cash",
    "sg_inflation": "Singapore CPI inflation",
}


def _clean(value):
    """JSON-safe: numpy scalars to Python, NaN to None, floats rounded to 6 dp."""
    if isinstance(value, dict):
        return {str(k): _clean(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_clean(v) for v in value]
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float):
        return None if np.isnan(value) else round(value, 6)
    return value


def compute() -> dict:
    """Forward CMAs, scenarios, validation summary and comparison, as one dictionary."""
    cpi = singstat.cpi_monthly()
    inflation, inflation_annual = forward.inflation_cma(cpi)
    inflation_draws = sc.inflation_draws(inflation_annual)

    panel = jst.annual()
    g_div_by_country, div_annual = forward.dividend_growth_by_country(panel)
    g_div = float(g_div_by_country.median())
    g_eps, eps_from, eps_to = forward.eps_growth(shiller.monthly())
    gdp = forward.gdp_per_capita_growth(panel)
    facts = documents.fund_documents().query("fund == 'ACWD'").set_index("field")["value"]
    dividend_yield, pe_fy1 = float(facts["index_dividend_yield"]), float(facts["pe_fy1"])
    d1, e1 = dividend_yield + g_div, dividend_yield + g_eps

    curve, curve_date = forward.sgs_curve(mas.sgs_yields())
    sgs = forward.sgs_nominal(curve)
    rates = mas.three_month_rates()
    long_run = forward.cash_long_run(rates, cpi)
    start = forward.cash_start(rates)
    cash = forward.cash_cma(start, inflation, float(long_run.mean()))
    long_run_draws = sc.mean_draws(long_run)
    cash_draws = forward.cash_cma(start, inflation_draws, long_run_draws)

    scenario = {
        "global_equity_sgd": sc.scenario(
            d1, abs(e1 - d1) / 2, float(sc.dividend_growth_draws(div_annual).std(ddof=1))
        ),
        "sgs": sc.scenario(
            sgs["B1"] - inflation,
            abs(sgs["B2"] - sgs["B1"]) / 2,
            float(inflation_draws.std(ddof=1)),
        ),
        "sgd_cash": sc.scenario(cash, 0.0, float(np.std(cash_draws, ddof=1))),
        "sg_inflation": sc.scenario(inflation, 0.0, float(inflation_draws.std(ddof=1))),
    }

    surveys = spf.medians()
    q1 = surveys.loc[pd.Period(f"{pd.Period(AS_OF, 'M').year}Q1", "Q")]
    erp = damodaran.implied_erp()
    erp_year = int(erp.index.max())
    history_mix = upstream.load("historical_mix_returns").set_index("equity_share")
    jst_to_end = panel.loc[(slice(None), slice(None, JST_END_YEAR)), :]

    validation = pd.read_csv(SUMMARY)
    by_country = pd.read_csv(BY_COUNTRY)
    country_summary = {
        m: {
            "countries": int(len(g)),
            "positive_r2": int((g["oos_r2"] > 0).sum()),
            "median_r2": float(g["oos_r2"].median()),
            "best": [g.loc[g["oos_r2"].idxmax(), "sample"], float(g["oos_r2"].max())],
            "worst": [g.loc[g["oos_r2"].idxmin(), "sample"], float(g["oos_r2"].min())],
        }
        for m, g in by_country.groupby("method")
    }
    mas_spf = documents.FILES[2].path
    longest = forward.dividend_growth_longest_run(panel)
    d1_jst_bias = next(
        r["bias"]
        for r in validation.to_dict(orient="records")
        if r["method"] == "D1" and r["sample"] == "JST pooled"
    )
    with_equity = sorted(panel["eq_tr"].dropna().index.get_level_values("country").unique())
    payout = damodaran.payout_yields()
    return _clean(
        {
            "as_of": AS_OF,
            "jst_end_year": JST_END_YEAR,
            "validation": validation.to_dict(orient="records"),
            "validation_by_country": country_summary,
            "inflation": {
                "cma": inflation,
                "window": f"{inflation_annual.index.min()}-{inflation_annual.index.max()}",
            },
            "equity": {
                "dividend_yield": dividend_yield,
                "g_div": g_div,
                "g_div_by_country": g_div_by_country.sort_values().to_dict(),
                "g_eps": g_eps,
                "g_eps_window": f"{eps_from} to {eps_to}",
                "D1": d1,
                "E1": e1,
                "pe_fy1": pe_fy1,
                "forward_earnings_yield": 1 / pe_fy1,
                "gdp_per_capita_growth_median": float(gdp.median()),
                "gdp_countries": int(len(gdp)),
                "real_fx_change": 0.0,
                "real_fx_evidence": real_fx_windows(),
                "countries_excluded": {
                    c: "no contiguous run of 30+ years ending in "
                    f"{JST_END_YEAR} with positive dividends at both ends"
                    for c in with_equity
                    if c not in g_div_by_country.index
                }
                | {
                    c: "no equity data in JST R6"
                    for c in sorted(set(panel.index.get_level_values("country")) - set(with_equity))
                },
            },
            "post_hoc": {
                "P1_g_div_longest_run": float(longest.median()),
                "P1_countries": int(len(longest)),
                "P1_added": sorted(set(longest.index) - set(g_div_by_country.index)),
                "P1_D1": dividend_yield + float(longest.median()),
                "P2_d1_jst_bias": d1_jst_bias,
                "P2_bias_corrected_D1": d1 - d1_jst_bias,
                "us_gross_buyback_yield": payout["us_total_payout_yield"]
                - payout["us_dividend_yield"],
            },
            "sgs": {
                "curve_date": curve_date,
                "yield_5y": float(curve[5]),
                "yield_10y": float(curve[10]),
                "duration": forward.SGS_DURATION,
                "B1_nominal": sgs["B1"],
                "B2_nominal": sgs["B2"],
                "rolldown": sgs["rolldown"],
                "B1_real": sgs["B1"] - inflation,
                "B2_real": sgs["B2"] - inflation,
            },
            "cash": {
                "start_nominal": start,
                "start_real": start - inflation,
                "long_run_real": float(long_run.mean()),
                "long_run_window": f"{long_run.index.min()}-{long_run.index.max()}",
                "cma": cash,
            },
            "scenarios": scenario,
            "comparison": {
                "spf_survey": f"{pd.Period(AS_OF, 'M').year}Q1",
                "spf_stock10_real": float(q1["STOCK10"] - q1["CPI10"]),
                "spf_bond10_real": float(q1["BOND10"] - q1["CPI10"]),
                "spf_bill10_real": float(q1["BILL10"] - q1["CPI10"]),
                "spf_cpi10": float(q1["CPI10"]),
                "damodaran_year": erp_year,
                "damodaran_implied_erp": float(erp.loc[erp_year, "implied_erp"]),
                "damodaran_tbond": float(erp.loc[erp_year, "tbond_rate"]),
                "damodaran_expected_real": float(erp.loc[erp_year].sum() - q1["CPI10"]),
                "maa_100_equity": float(history_mix.loc[1.0, "expected_real_return"]),
                "maa_0_equity": float(history_mix.loc[0.0, "expected_real_return"]),
                "jst_median_dividend_yield": float(jst_to_end["eq_dp"].median()),
                **payout,
            },
            "mas_spf_file_saved": mas_spf.exists(),
            "mas_spf_cpi": documents.mas_spf_cpi_medians() if mas_spf.exists() else None,
        }
    )


def real_fx_windows() -> dict[str, float]:
    """Annualised real change of the SGD against the USD (positive = SGD appreciation), from
    FRED EXSIUS and the US (Shiller) and Singapore (SingStat) CPI, over three windows."""
    fx = fred.monthly(["EXSIUS"])["EXSIUS"]
    us, sg = shiller.monthly()["cpi"], singstat.cpi_monthly()
    out = {}
    for start, end in (("1981-12", "2025-12"), ("1995-12", "2025-12"), ("2005-12", "2025-12")):
        years = int(end[:4]) - int(start[:4])
        relative = (fx[start] / fx[end]) * (sg[end] / sg[start]) / (us[end] / us[start])
        out[f"{start[:4]}-{end[:4]}"] = float(relative ** (1 / years) - 1)
    return out


def check_drift(new: dict) -> list[str]:
    """Headline scenario values that moved by more than the tolerance from the committed file."""
    if not FIGURES_JSON.exists():
        return []
    old = json.loads(FIGURES_JSON.read_text())
    moved = []
    for asset, values in new["scenarios"].items():
        for key in ("low", "central", "high"):
            before = old.get("scenarios", {}).get(asset, {}).get(key)
            if before is None:
                continue
            change_bps = abs(values[key] - before) * 1e4
            if change_bps > DRIFT_TOLERANCE_BPS:
                moved.append(f"{asset} {key}: {before:.4f} -> {values[key]:.4f}")
    return moved


def chart() -> None:
    """US validation: the starting yield tracks bond returns; D1 does not track equities."""
    annual = history.shiller_annual(shiller.monthly())
    b1 = methods.shiller_bonds(annual)["B1"].dropna(subset=["forecast", "realised"])
    d1 = methods.shiller_equity(annual)["D1"].dropna(subset=["forecast", "realised"])
    fig, axes = plt.subplots(1, 2, figsize=(8, 3.6), dpi=150, facecolor=SURFACE, sharex=True)
    panels = [
        (axes[0], b1, "Bonds: 10-year yield vs realised\n10-year nominal return"),
        (axes[1], d1, "Equities: D1 forecast vs realised\n10-year real return"),
    ]
    for ax, frame, title in panels:
        ax.set_facecolor(SURFACE)
        ax.plot(frame.index, frame["realised"] * 100, color=BLUE, lw=2, label="Realised")
        ax.plot(frame.index, frame["forecast"] * 100, color=ORANGE, lw=2, ls="--", label="Forecast")
        ax.set_title(title, fontsize=9, color=INK, loc="left")
        ax.set_ylabel("% a year", fontsize=8, color=MUTED)
        ax.set_xlabel("Forecast made at end of year", fontsize=8, color=MUTED)
        ax.tick_params(colors=MUTED, labelsize=7)
        ax.grid(axis="y", color="#e4e3df", lw=0.6)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color("#c3c2b7")
    axes[0].legend(frameon=False, fontsize=8, labelcolor=INK)
    fig.suptitle(
        "Starting yields tracked US bond returns; dividend-based forecasts missed most of the "
        "swings in equities",
        fontsize=9.5,
        color=INK,
        x=0.01,
        ha="left",
    )
    fig.text(
        0.01,
        0.01,
        f"US, forecasts at December {int(b1.index.min())}-{int(b1.index.max())}, each compared "
        "with the following 10 years. Source: Robert Shiller online data; own calculations.",
        fontsize=6.5,
        color=MUTED,
    )
    fig.tight_layout(rect=(0, 0.04, 1, 0.92))
    FIGURES.mkdir(parents=True, exist_ok=True)
    fig.savefig(CHART, facecolor=SURFACE)
    plt.close(fig)


def pct(x: float, dp: int = 1) -> str:
    return f"{x * 100:.{dp}f}%"


def pp(x: float, dp: int = 1) -> str:
    """Signed value in percentage points."""
    return f"{x * 100:+.{dp}f} pp"


def r2(x: float) -> str:
    """Two decimals, or three when the value is within 0.01 of zero (so 0.004 isn't shown as 0.00)."""
    return f"{x:.3f}" if abs(x) < 0.01 else f"{x:.2f}"


def _validation_table(fig: dict) -> str:
    rows = [
        "| Method | Sample | Basis | Origins | Effective n | Bias (HAC s.e.) | RMSE | "
        "Correlation | OOS R² [95% interval] |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for v in fig["validation"]:
        origins = f"{v['first_origin']}–{v['last_origin']} ({v['origins']})"
        rows.append(
            f"| {v['method']} | {v['sample']} | {v['basis']} | {origins} | {v['effective_n']:.1f}"
            f" | {pp(v['bias'])} ({pct(v['bias_hac_se'])}) | {pct(v['rmse'])} | "
            f"{r2(v['correlation'])} | {r2(v['oos_r2'])} [{r2(v['r2_low'])}, {r2(v['r2_high'])}] |"
        )
    return "\n".join(rows)


def _scenario_table(fig: dict) -> str:
    rows = [
        "| Asset class | Low | Central | High | (a) method spread | (b) bootstrap s.e. | "
        "Width set by |",
        "|---|---|---|---|---|---|---|",
    ]
    for key, label in ASSETS.items():
        s = fig["scenarios"][key]
        rows.append(
            f"| {label} | {pct(s['low'])} | **{pct(s['central'])}** | {pct(s['high'])} | "
            f"{pct(s['spread_a'], 2)} | {pct(s['bootstrap_se_b'], 2)} | {s['width_set_by']} |"
        )
    return "\n".join(rows)


def _find(fig: dict, method: str, sample: str) -> dict:
    return next(v for v in fig["validation"] if v["method"] == method and v["sample"] == sample)


def render(fig: dict) -> str:
    """docs/cma.md from the figures dictionary."""
    eq, sgs, cash, cmp_ = fig["equity"], fig["sgs"], fig["cash"], fig["comparison"]
    ph = fig["post_hoc"]
    fx_text = ", ".join(f"{pp(v, 2)[:-3]}% ({k})" for k, v in eq["real_fx_evidence"].items())
    excluded_text = "; ".join(f"{c} ({why})" for c, why in eq["countries_excluded"].items())
    b1_us, b1_jst = _find(fig, "B1", "Shiller US"), _find(fig, "B1", "JST pooled")
    d1_us, d1_jst = _find(fig, "D1", "Shiller US"), _find(fig, "D1", "JST pooled")
    e3_us = _find(fig, "E3", "Shiller US")
    b1_c, b2_c = (
        _find(fig, "B1", "Shiller US, B2 origins"),
        _find(fig, "B2", "Shiller US, B2 origins"),
    )
    dc, bc = fig["validation_by_country"]["D1"], fig["validation_by_country"]["B1"]
    by_country = "\n".join(f"| {c} | {pct(g, 2)} |" for c, g in eq["g_div_by_country"].items())
    eq_s, sgs_s = fig["scenarios"]["global_equity_sgd"], fig["scenarios"]["sgs"]
    spf_cpi = fig.get("mas_spf_cpi")
    mas_spf = (
        f"The median forecast across {spf_cpi['forecasters']} forecasters is {pct(spf_cpi['2026'])} "
        f"CPI-All Items inflation for 2026 and {pct(spf_cpi['2027'])} for 2027, against the "
        f"10-year assumption of {pct(fig['inflation']['cma'], 2)}. This is a near-term cross-check only; it sets "
        "nothing (the assumption is the 30-year historical rate, pre-registered)."
        if spf_cpi
        else "Pending: the workbook must be saved by hand (MAS returns a web page, not the file, "
        "to scripted requests), so no figure is shown yet."
    )
    return f"""# Capital market assumptions

Generated by `make all` from `reports/cma_figures.json`; do not edit by hand. Rules: `docs/decisions.md` (2026-10-28). Most were fixed before any result was computed; changes made after results are logged there and labelled post-hoc (amendments 1–4, the corrections and the Phase 4 review). As-of date: {fig["as_of"]}. All figures are annualised 10-year **real** returns at index level, before fund costs (costs are deducted in the simulation).

## Headline

1. **Starting yields forecast bond returns well, largely by construction.** The 10-year yield at the start explained most of the variation in the next 10 years' nominal bond return: out-of-sample R² {r2(b1_us["oos_r2"])} in the US ({b1_us["first_origin"]}–{b1_us["last_origin"]}) and {r2(b1_jst["oos_r2"])} pooled across {bc["countries"]} JST countries (positive in {bc["positive_r2"]} of {bc["countries"]}). This is mostly arithmetic, not forecasting skill: when a bond's duration is close to the horizon, gains and losses from yield changes are largely offset by reinvesting at the new yield, so the holding-period return stays close to the starting yield. The US test is also partly circular: Shiller's realised bond returns are themselves computed from the same 10-year yield series (they match a 10-year par bond repriced at each month's yield, checked 2026-10-28). It says nothing about the path in between, which the simulation handles separately.
2. **Equity methods add little over the long-run mean internationally.** Across {dc["countries"]} JST countries, dividend yield plus real dividend growth (D1) had a pooled out-of-sample R² of {r2(d1_jst["oos_r2"])} [95% interval {r2(d1_jst["r2_low"])} to {r2(d1_jst["r2_high"])}]: no better than assuming the historical average return. It was positive in {dc["positive_r2"]} of {dc["countries"]} countries (median {r2(dc["median_r2"])}; best {dc["best"][0]} {r2(dc["best"][1])}, worst {dc["worst"][0]} {r2(dc["worst"][1])}). In the US it was {r2(d1_us["oos_r2"])} [{r2(d1_us["r2_low"])}, {r2(d1_us["r2_high"])}].
3. **The best US equity predictor can't be used going forward with free data.** 1/CAPE (E3) did best in the US: R² {r2(e3_us["oos_r2"])} [{r2(e3_us["r2_low"])}, {r2(e3_us["r2_high"])}], the only equity interval that excludes zero. The fund factsheet publishes no CAPE (only a forward, analyst-estimate P/E), so E3 stays validation-only. It is not substituted after seeing these results.

![US validation: bonds vs equities](../reports/figures/cma_validation_us.png)

## Scenarios used by the simulation

Each scenario is simulated separately (never drawn at random on top of the return bootstrap). Low and high = central ∓ the wider of (a) the method spread and (b) the bootstrap standard error of the central estimate. **These ranges describe uncertainty about the expected return, not the range of outcomes:** a single 10-year outcome has historically missed its forecast by far more (RMSE {pct(d1_jst["rmse"])} for D1 across JST countries). The spread of outcomes comes from the simulation, and failed validation tests are reported below rather than built into these ranges.

{_scenario_table(fig)}

- **Equities:** central = D1. The method spread compares D1 with E1 (the US-growth variant); E1 contributes to the spread only, because applying US earnings growth to a global index yield biases the estimate upward.
- **SGS:** central = B1 (starting yield). The spread compares B1 with B2 (B1 plus rolldown); B2 is not central because it lost to B1 on US out-of-sample RMSE ({pct(b2_c["rmse"], 2)} vs {pct(b1_c["rmse"], 2)}).
- **Cash and inflation:** one method each, so the bootstrap standard error sets the width.
- **Equity standard error:** resamples the same blocks of calendar years for every country (amendment 4), so common shocks move all countries together.

**Post-hoc sensitivities (not used; central unchanged):**
- P1, real dividend growth from each country's longest run of 30+ years: median {pct(ph["P1_g_div_longest_run"], 2)} across {ph["P1_countries"]} countries (adds {", ".join(ph["P1_added"]) or "none"}), giving D1 of {pct(ph["P1_D1"], 2)}.
- P2, D1 corrected for its pooled JST out-of-sample bias ({pp(ph["P2_d1_jst_bias"])}): {pct(ph["P2_bias_corrected_D1"], 2)}.

## Assumptions and their sources

**Inflation:** {pct(fig["inflation"]["cma"], 2)} a year: annualised Singapore CPI (All Items) inflation, {fig["inflation"]["window"]} (SingStat table M213751).

**Global equities (SGD, unhedged)**

| Component | Value | Source |
|---|---|---|
| Index dividend yield | {pct(eq["dividend_yield"], 2)} | ACWD factsheet, 30 September 2026, page 2 (`reference/fund_documents.csv`) |
| Real dividend growth (D1) | {pct(eq["g_div"], 2)} | Median of {len(eq["g_div_by_country"])} JST countries' real dividend growth, contiguous runs of 30+ years ending {fig["jst_end_year"]} with positive dividends at both ends |
| Real EPS growth (E1, spread only) | {pct(eq["g_eps"], 2)} | Shiller US real EPS, {eq["g_eps_window"]} |
| Expected real change in SGD | {pct(eq["real_fx_change"], 1)} | Relative purchasing power parity (Rogoff 1996 still to verify). Measured real SGD change against the USD: {fx_text} a year (positive = SGD appreciation; FRED EXSIUS, US and Singapore CPI). Near zero over the longest window but sensitive to the window, and USD-only while the fund holds many currencies |
| **D1 = central** | **{pct(eq["D1"], 2)}** | The forward growth term is the cross-country median over full runs; the validation used each country's own expanding-window growth, so the forward estimate is not exactly the form that was tested |
| E1 | {pct(eq["E1"], 2)} | |

Checks, not used: real GDP per capita growth, median of {eq["gdp_countries"]} JST countries to {fig["jst_end_year"]}: {pct(eq["gdp_per_capita_growth_median"], 2)}. Forward earnings yield (1 / P/E FY1 of {eq["pe_fy1"]}): {pct(eq["forward_earnings_yield"], 2)}, nominal and **based on analyst estimates** of next year's earnings.

Real dividend growth by country (D1 input):

| Country | Real dividend growth |
|---|---|
{by_country}

**SGS:** the yield at {sgs["duration"]} years (the duration of the SGS fund used in `Multi-Asset-Allocation`) interpolated between the 5-year ({pct(sgs["yield_5y"], 2)}) and 10-year ({pct(sgs["yield_10y"], 2)}) benchmark yields on {sgs["curve_date"]}: {pct(sgs["B1_nominal"], 2)} nominal, {pct(sgs["B1_real"], 2)} real (B1). Rolldown adds {pct(sgs["rolldown"], 2)} (B2, spread only).

**SGD cash:** the 3-month compounded SORA at the end of September 2026 ({pct(cash["start_nominal"], 2)} nominal, {pct(cash["start_real"], 2)} real) moving in a straight line to the long-run real 3-month rate ({pct(cash["long_run_real"], 2)}, {cash["long_run_window"]}: interbank to 2013, then compounded SORA); the 10-year average is {pct(cash["cma"], 2)}.

## Validation results

All forecasts use only data available at each origin (expanding windows, 30-year burn-in, a 3-month publication lag on Shiller dividends, earnings and CPI). Each is compared with the realised return over the next 10 years and with the historical-mean forecast (out-of-sample R², Campbell & Thompson 2008). Weak results are reported as found (Goyal & Welch 2008). Effective n = origins / 10, because 10-year windows overlap. R² intervals: moving-block bootstrap, blocks of 10 origins, 2,000 replications, seed 20261028.

{_validation_table(fig)}

Equity rows are real returns; bond rows are nominal (amendment 3). JST data ends in {fig["jst_end_year"]} (amendment 1); Canada and Ireland have no equity data in JST R6. Per-country results: `data/processed/cma_validation_by_country.csv`.

**Where the methods fail:**
- E2 (E1 plus CAPE reversion) did worse than the historical mean in the US (R² {r2(_find(fig, "E2", "Shiller US")["oos_r2"])}).
- D1 is negative in {dc["countries"] - dc["positive_r2"]} of {dc["countries"]} JST countries.
- Every equity method has a wide R² interval: with about {d1_us["effective_n"]:.0f} independent 10-year periods in the US, the data can't separate weak predictors from none.
- D1 forecasts were too low on average (bias {pp(d1_us["bias"])} US, {pp(d1_jst["bias"])} JST pooled), as were E1 ({pp(_find(fig, "E1", "Shiller US")["bias"])}) and E2 ({pp(_find(fig, "E2", "Shiller US")["bias"])}); E3's bias was positive ({pp(e3_us["bias"])}). Each is within about one standard error of zero.

## Known biases and limits of these estimates

- **Buybacks are left out, so the equity central is probably too low.** D1's forward input is the dividend yield only. Companies also return cash through share buybacks: for the S&P 500 in {cmp_["payout_year"]}, Damodaran's data give a dividend yield of {pct(cmp_["us_dividend_yield"], 2)} and a gross buyback yield of {pct(ph["us_gross_buyback_yield"], 2)} (gross: not net of share issuance; no free, citable net series was found). This is consistent with the negative validation bias of D1, E1 and E2. It is disclosed, not corrected: no buyback adjustment was registered. P2 above shows the size of a bias correction.
- **Which countries feed dividend growth.** All {len(eq["g_div_by_country"])} are developed markets with long, continuous data: a sample of markets that came through their crises, not a random draw. JST has no emerging markets, while the fund holds some. Excluded: {excluded_text}. P1 shows the effect of using each country's longest run instead.
- **US data are revised, and the lag is a judgement.** Shiller's file is today's revised history, not what investors could see at the time, and the 3-month lag on dividends, earnings and CPI is Evidence: pending. This affects the US validation (E1–E3, D1), not the forward estimates.

## Comparison with other estimates

| Estimate | Equities, real | Bonds, real | Cash/bills, real |
|---|---|---|---|
| This project, central (SGD) | {pct(eq_s["central"])} | {pct(sgs_s["central"])} | {pct(fig["scenarios"]["sgd_cash"]["central"])} |
| `Multi-Asset-Allocation`, historical global JST portfolio (100% / 0% equity)¹ | {pct(cmp_["maa_100_equity"])} | {pct(cmp_["maa_0_equity"])} | – |
| Philadelphia Fed SPF, {cmp_["spf_survey"]} median 10-year forecasts (US, less CPI10 {pct(cmp_["spf_cpi10"])}) | {pct(cmp_["spf_stock10_real"])} | {pct(cmp_["spf_bond10_real"])} | {pct(cmp_["spf_bill10_real"])} |
| Damodaran implied ERP ({cmp_["damodaran_year"]}) + T-bond rate, less the same CPI10 | {pct(cmp_["damodaran_expected_real"])} | – | – |

¹ Computed in `Multi-Asset-Allocation` from JST data to 2020, including the 2016–2020 years this project excludes (amendment 1). Like the dividend-growth input, it comes from developed markets that came through their crises, a survivor sample, so it is likely to overstate what a random market would have returned.

**Why the forward equity figure is below the historical one:** most of the gap is the starting yield. The index dividend yield today is {pct(eq["dividend_yield"], 2)}; the median JST dividend yield over 1870–{fig["jst_end_year"]} was {pct(cmp_["jst_median_dividend_yield"], 2)}. A building-block estimate passes today's low yield straight through; a historical average assumes the past's higher yields recur. The US survey and implied-premium figures are for US assets in USD and are shown for context only.

**Near-term inflation cross-check (MAS Survey of Professional Forecasters):** {mas_spf} Source: MAS, *Survey of Professional Forecasters*, September 2026 results workbook (`Sep26Q3.xlsx`, sheet Sep26Q3, individual responses), available from mas.gov.sg. Contains information from the MAS Survey of Professional Forecasters, which is made available under the terms of the Monetary Authority of Singapore's Terms of Use of Datasets.

## Sources and licences

- Robert Shiller, online data (`ie_data.xls`): no licence stated; only derived figures are shown.
- Jordà-Schularick-Taylor Macrohistory Database R6; Jordà et al. (2019), *QJE* 134(3). JST-derived figures are licensed CC BY-NC-SA 4.0.
- MAS, *Domestic Interest Rates* and *SGS Benchmark Prices and Yields* statistics, available from mas.gov.sg: contains information from MAS statistics, made available under the terms of the Monetary Authority of Singapore's Terms of Use of Datasets.
- SingStat table M213751 (CPI): terms not confirmed; only derived figures are shown.
- Philadelphia Fed Survey of Professional Forecasters (STOCK10, BOND10, BILL10, CPI10 medians); Damodaran, `histimpl.xls`: cited figures only.
- FRED GS5, GS10: public domain.
- ACWD factsheet (30 September 2026) and SSGA SPDR ETFs Europe I plc annual report (year to 31 March 2026): cited by page; not redistributed.
- Citations with DOIs: `reference/citations.csv`.
"""


def run() -> dict:
    """Compute, check drift against the committed figures, then write JSON, chart and doc."""
    fig = compute()
    moved = check_drift(fig)
    if moved:
        DRIFT_REPORT.parent.mkdir(parents=True, exist_ok=True)
        with DRIFT_REPORT.open("a") as f:
            f.write(
                f"\n## Headline CMAs moved by more than {DRIFT_TOLERANCE_BPS} bps\n\n"
                + "\n".join(f"- {m}" for m in moved)
                + "\n"
            )
        raise SystemExit(
            "Headline CMAs moved beyond the tolerance; see "
            f"{DRIFT_REPORT.relative_to(ROOT)}. Review, then delete reports/cma_figures.json "
            "to accept."
        )
    REPORTS.mkdir(parents=True, exist_ok=True)
    FIGURES_JSON.write_text(json.dumps(fig, indent=2, ensure_ascii=False) + "\n")
    chart()
    CMA_DOC.write_text(render(fig))
    return fig
