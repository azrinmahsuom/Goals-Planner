# ruff: noqa: E501  (the docs/simulation.md template below is prose, one paragraph per line)
"""Example investors across CMA sets and engines -> reports/simulation_figures.json, two
figures and docs/simulation.md. Rules: docs/decisions.md (2026-10-28, Phase 2 pre-registration).
"""

import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from analysis.cma.report import FIGURES_JSON as CMA_JSON  # noqa: E402
from analysis.config import DOCS, FIGURES, REPORTS  # noqa: E402
from analysis.sim import MEAN_BLOCK, PATHS, SEED, SGS_DURATION, costs, engine, srs  # noqa: E402
from analysis.sim.history import HISTORIES  # noqa: E402

SIM_JSON = REPORTS / "simulation_figures.json"
SIM_DOC = DOCS / "simulation.md"
FAN_CHART = FIGURES / "simulation_fan_a.png"
GOAL_CHART = FIGURES / "simulation_p_goal.png"
BLUE, ORANGE, AQUA, YELLOW, INK, MUTED, SURFACE, GRID = (
    "#2a78d6",
    "#eb6834",
    "#1baf7a",
    "#eda100",
    "#0b0b0b",
    "#52514e",
    "#fcfcfb",
    "#e4e3df",
)
PROBABILITIES = (0.5, 0.75, 0.9)
WITHDRAWAL_MONTHS = 120

EXAMPLES = {
    "A": {
        "age": 30,
        "initial": 10_000,
        "monthly": 800,
        "growth": 0.02,
        "years": 25,
        "goal": 600_000,
        "equity": 0.88,
    },
    "B": {
        "age": 45,
        "initial": 150_000,
        "monthly": 1_500,
        "growth": 0.0,
        "years": 15,
        "goal": 600_000,
        "equity": 0.59,
    },
    "C": {
        "age": 55,
        "initial": 400_000,
        "monthly": 0,
        "growth": 0.0,
        "years": 10,
        "goal": 500_000,
        "equity": 0.49,
    },
    "D": {
        "age": 40,
        "initial": 0,
        "monthly": 1_275,
        "growth": 0.0,
        "years": 24,
        "goal": 500_000,
        "equity": 0.67,
        "srs": True,
    },
}
D_SRS = srs.SRS(age=40, citizen_or_pr=True, marginal_rate=0.115, other_income_in_retirement=0.0)
ENGINES = {  # name: (history, engine, mean block)
    "Bootstrap, SGD era, 24-month blocks (main)": ("H-SGD", "bootstrap", MEAN_BLOCK),
    "Bootstrap, US 1871-, 24-month blocks": ("H-US", "bootstrap", MEAN_BLOCK),
    "Student-t, SGD era": ("H-SGD", "student-t", None),
    "Bootstrap, SGD era, n^(1/3) blocks": ("H-SGD", "bootstrap", "n^(1/3)"),
    "Bootstrap, SGD era, 60-month blocks": ("H-SGD", "bootstrap", 60),
}
MAIN = next(iter(ENGINES))
SHOWN_SETS = ("central", "P2", "hist_eq_yield", "historical")
SET_LABELS = {
    "low": "Low",
    "central": "Central",
    "high": "High",
    "P2": "Bias-corrected equity (P2, post-hoc)",
    "hist_eq_yield": "Historical equity + yield-based bonds",
    "historical": "Historical global (JST, real USD, 1871–2020)",
}


def cma_sets() -> dict[str, dict[str, float]]:
    """Asset CMAs (real, annual) for each set, from reports/cma_figures.json."""
    fig = json.loads(CMA_JSON.read_text())
    sc, cmp_ = fig["scenarios"], fig["comparison"]
    out = {
        k: {
            "equity": sc["global_equity_sgd"][k],
            "sgs": sc["sgs"][k],
            "cash": sc["sgd_cash"][k],
        }
        for k in ("low", "central", "high")
    }
    out["P2"] = dict(out["central"], equity=fig["post_hoc"]["P2_bias_corrected_D1"])
    out["historical"] = {
        "equity": cmp_["maa_100_equity"],
        "sgs": cmp_["maa_0_equity"],
        "cash": fig["cash"]["long_run_real"],
    }
    # Added at the Phase 2 checkpoint (docs/decisions.md): starting yields forecast bonds well.
    out["hist_eq_yield"] = dict(out["central"], equity=cmp_["maa_100_equity"])
    return out


def plan_for(ex: dict, batching: str = "monthly") -> engine.Plan:
    return engine.Plan(
        ex["initial"], ex["monthly"], ex["growth"], ex["years"] * 12, ex["equity"], batching
    )


def _cash_monthly(cma: dict) -> float:
    return (1 + cma["cash"]) ** (1 / 12) - 1


def run_case(
    draws: np.ndarray, ex: dict, cma: dict, batching: str = "monthly"
) -> tuple[engine.Paths, dict]:
    plan = plan_for(ex, batching)
    w = ex["equity"]
    paths = engine.simulate(draws, plan, costs.annual_cost(w), costs.order_cost, _cash_monthly(cma))
    return paths, engine.summarise(paths, ex["goal"])


def _brief(summary: dict) -> dict:
    t, d = summary["terminal_percentiles"], summary["drawdown_percentiles"]
    return {
        "p_goal": summary["p_goal"],
        "terminal_p10": t[10],
        "terminal_p50": t[50],
        "terminal_p90": t[90],
        "drawdown_median": d[50],
        "drawdown_p5": d[5],
        "contributed": summary["contributed"],
        "trading_costs_median": summary["trading_costs_median"],
    }


def srs_outcome(draws: np.ndarray, ex: dict, cma: dict) -> dict:
    """Example D with and without SRS, identical draws, contributions and withdrawal schedule."""
    plan = plan_for(ex)
    w = ex["equity"]
    c = costs.annual_cost(w)
    capped = srs.capped_plan(plan, D_SRS)
    relief = srs.relief_schedule(capped, D_SRS)
    with_srs = engine.simulate(draws, capped, c, costs.order_cost, _cash_monthly(cma), extra=relief)
    without = engine.simulate(draws, capped, c, costs.order_cost, _cash_monthly(cma))
    later = draws[:, plan.months : plan.months + WITHDRAWAL_MONTHS, :] @ np.array([w, 1 - w])
    net = (1 + later) * (1 - c) ** (1 / 12)
    annual = net.reshape(net.shape[0], -1, 12).prod(axis=2) - 1
    premature = srs.premature(D_SRS, plan.months)
    if premature:
        srs_net = srs.premature_net(with_srs.wealth[:, -1], D_SRS)
        plain_net = without.wealth[:, -1]
        tax = with_srs.wealth[:, -1] - srs_net
    else:
        srs_w = srs.withdraw(with_srs.wealth[:, -1], annual, D_SRS, taxed=True)
        plain_w = srs.withdraw(without.wealth[:, -1], annual, D_SRS, taxed=False)
        srs_net, plain_net, tax = (
            srs_w["after_tax_withdrawals"],
            plain_w["after_tax_withdrawals"],
            srs_w["tax_paid"],
        )
    return {
        "premature": premature,
        "relief_total": float(relief.sum()),
        "balance_at_goal_median_srs": float(np.median(with_srs.wealth[:, -1])),
        "balance_at_goal_median_plain": float(np.median(without.wealth[:, -1])),
        "p_goal_srs": float((with_srs.wealth[:, -1] >= ex["goal"]).mean()),
        "after_tax_withdrawals_median_srs": float(np.median(srs_net)),
        "withdrawals_median_plain": float(np.median(plain_net)),
        "tax_median": float(np.median(tax)),
        "srs_better_share": float((srs_net > plain_net).mean()),
    }


def compute() -> tuple[dict, dict]:
    sets = cma_sets()
    months = max(
        ex["years"] * 12 + (WITHDRAWAL_MONTHS if ex.get("srs") else 0) for ex in EXAMPLES.values()
    )
    histories = {name: f() for name, f in HISTORIES.items()}
    out = {
        "paths": PATHS,
        "seed": SEED,
        "histories": {
            k: {"start": str(h.index[0]), "end": str(h.index[-1]), "months": len(h)}
            for k, h in histories.items()
        },
        "cma_sets": sets,
        "annual_cost": {k: costs.annual_cost(ex["equity"]) for k, ex in EXAMPLES.items()},
        "examples": {k: dict(ex) for k, ex in EXAMPLES.items()},
        "grid": {},
        "required_monthly": {},
        "batching": {},
        "srs": {},
        "engines": {},
        "srs_assumptions": {
            "marginal_rate": D_SRS.marginal_rate,
            "statutory_retirement_age": srs.rules()["statutory_retirement_age"],
            "contribution_cap": srs.annual_cap(D_SRS),
            "relief_cap": srs.rules()["personal_relief_cap"],
        },
        "sgs_duration": SGS_DURATION,
    }
    charts = {}
    for name, (hist, kind, block) in ENGINES.items():
        factory = engine.DrawFactory(histories[hist], kind, months, block or MEAN_BLOCK)
        out["engines"][name] = (
            {"history": hist, "mean_block": factory.block}
            if kind == "bootstrap"
            else {"history": hist, "student_t_df": factory.fit.df}
        )
        for set_name, cma in sets.items():
            draws = factory.draws(cma)
            for key, ex in EXAMPLES.items():
                paths, summary = run_case(draws, ex, cma)
                out["grid"].setdefault(key, {}).setdefault(name, {})[set_name] = _brief(summary)
                if name != MAIN or set_name not in SHOWN_SETS:
                    continue
                if key == "A" and set_name == "central":
                    charts["fan"] = (summary, engine.cash_path(plan_for(ex), cma["cash"]))
                plan = plan_for(ex)
                out["required_monthly"].setdefault(key, {})[set_name] = {
                    str(p): engine.required_monthly(
                        draws,
                        plan,
                        ex["goal"],
                        p,
                        costs.annual_cost(ex["equity"]),
                        costs.order_cost,
                        _cash_monthly(cma),
                    )
                    for p in PROBABILITIES
                }
                if ex.get("srs"):
                    out["srs"][set_name] = srs_outcome(draws, ex, cma)
                if set_name == "central" and ex["monthly"] > 0:
                    _, quarterly = run_case(draws, ex, cma, "quarterly")
                    out["batching"][key] = {
                        "monthly": _brief(summary),
                        "quarterly": _brief(quarterly),
                    }
    return out, charts


def _style(ax) -> None:
    ax.set_facecolor(SURFACE)
    ax.tick_params(colors=MUTED, labelsize=7)
    ax.grid(axis="y", color=GRID, lw=0.6)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#c3c2b7")


def fan_chart(summary: dict, cash: np.ndarray, ex: dict) -> None:
    fan = summary["fan"]
    years = np.arange(len(fan[50])) / 12
    fig, ax = plt.subplots(figsize=(8, 4), dpi=150, facecolor=SURFACE)
    _style(ax)
    ax.fill_between(
        years,
        fan[5] / 1e3,
        fan[95] / 1e3,
        color=BLUE,
        alpha=0.12,
        lw=0,
        label="5th–95th percentile",
    )
    ax.fill_between(
        years,
        fan[25] / 1e3,
        fan[75] / 1e3,
        color=BLUE,
        alpha=0.25,
        lw=0,
        label="25th–75th percentile",
    )
    ax.plot(years, fan[50] / 1e3, color=BLUE, lw=2, label="Median")
    ax.plot(
        years,
        summary["worst_decile_median_path"] / 1e3,
        color=ORANGE,
        lw=2,
        ls="--",
        label="Median of the worst 10% of paths",
    )
    ax.plot(years, cash / 1e3, color=MUTED, lw=1.5, ls=":", label="Same savings held in cash")
    ax.axhline(ex["goal"] / 1e3, color=INK, lw=0.8)
    ax.text(
        years[-1],
        ex["goal"] / 1e3,
        f"Goal S${ex['goal'] / 1e3:.0f}k ",
        fontsize=7,
        color=INK,
        va="bottom",
        ha="right",
    )
    ax.set_xlabel("Years from today", fontsize=8, color=MUTED)
    ax.set_ylabel("Wealth, S$ thousands (today's money)", fontsize=8, color=MUTED)
    ax.legend(frameon=False, fontsize=7, loc="upper left", labelcolor=INK)
    fig.suptitle(
        "The range of outcomes widens with time: example A, central assumptions",
        fontsize=9.5,
        color=INK,
        x=0.01,
        ha="left",
    )
    fig.text(
        0.01,
        0.01,
        f"{PATHS:,} simulated paths; stationary bootstrap of SGD-era returns (1998–2026), re-centred on the CMAs; after costs. Hypothetical example, not advice.",
        fontsize=6.5,
        color=MUTED,
    )
    fig.tight_layout(rect=(0, 0.04, 1, 0.94))
    fig.savefig(FAN_CHART, facecolor=SURFACE)
    plt.close(fig)


def goal_chart(out: dict) -> None:
    fig, ax = plt.subplots(figsize=(8, 3.4), dpi=150, facecolor=SURFACE)
    _style(ax)
    keys = list(EXAMPLES)
    colours = {"central": BLUE, "P2": ORANGE, "hist_eq_yield": AQUA, "historical": YELLOW}
    markers = {"central": "o", "P2": "s", "hist_eq_yield": "^", "historical": "D"}
    for i, set_name in enumerate(SHOWN_SETS):
        values = [out["grid"][k][MAIN][set_name]["p_goal"] * 100 for k in keys]
        x = np.arange(len(keys)) + (i - 1.5) * 0.18
        ax.scatter(
            x,
            values,
            s=40,
            color=colours[set_name],
            marker=markers[set_name],
            label=SET_LABELS[set_name],
            zorder=3,
            edgecolor=SURFACE,
            linewidth=1.5,
        )
    for j, k in enumerate(keys):
        lo, hi = (out["grid"][k][MAIN][s]["p_goal"] * 100 for s in ("low", "high"))
        ax.plot([j - 0.27, j - 0.27], [lo, hi], color=BLUE, lw=1.5, zorder=2)
    ax.set_xticks(range(len(keys)), [f"Example {k}" for k in keys])
    ax.set_ylim(0, 100)
    ax.set_ylabel("Chance of reaching the goal (%)", fontsize=8, color=MUTED)
    ax.legend(
        frameon=False,
        fontsize=7,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.12),
        ncol=2,
        labelcolor=INK,
    )
    fig.suptitle(
        "The answer depends heavily on the return assumptions",
        fontsize=9.5,
        color=INK,
        x=0.01,
        ha="left",
    )
    fig.text(
        0.01,
        0.01,
        "Blue line: central set's low-high range. Main engine; after costs. Hypothetical examples, not advice.",
        fontsize=6.5,
        color=MUTED,
    )
    fig.tight_layout(rect=(0, 0.04, 1, 0.92))
    fig.savefig(GOAL_CHART, facecolor=SURFACE)
    plt.close(fig)


def _clean(value):
    if isinstance(value, dict):
        return {str(k): _clean(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_clean(v) for v in value]
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float):
        return round(value, 6)
    return value


def pct(x: float, dp: int = 0) -> str:
    return f"{x * 100:.{dp}f}%"


def sgd(x: float | None) -> str:
    return "not reachable" if x is None else f"S${x:,.0f}"


def render(out: dict) -> str:
    sets, g, rm = out["cma_sets"], out["grid"], out["required_monthly"]
    rows = []
    for k, ex in out["examples"].items():
        m = g[k][MAIN]
        rows.append(
            f"| {k} | {ex['age']} | {sgd(ex['initial'])} + {sgd(ex['monthly'])}/month"
            f"{' (+' + pct(ex['growth']) + ' a year)' if ex['growth'] else ''} | {ex['years']} | {sgd(ex['goal'])} | {pct(ex['equity'])} | "
            f"**{pct(m['central']['p_goal'])}** ({pct(m['low']['p_goal'])}–{pct(m['high']['p_goal'])}) | **{pct(m['P2']['p_goal'])}** | **{pct(m['hist_eq_yield']['p_goal'])}** | {pct(m['historical']['p_goal'])} |"
        )
    req = []
    for k in out["examples"]:
        for s in SHOWN_SETS:
            r = rm[k][s]
            req.append(
                f"| {k} | {SET_LABELS[s]} | {sgd(r['0.5'])} | {sgd(r['0.75'])} | {sgd(r['0.9'])} |"
            )
    eng = []
    for name, info in out["engines"].items():
        detail = (
            f"{info['mean_block']} months"
            if "mean_block" in info
            else f"fitted df {info['student_t_df']:.1f}"
        )
        vals = " | ".join(pct(g[k][name]["central"]["p_goal"]) for k in out["examples"])
        eng.append(f"| {name} | {detail} | {vals} |")
    outcomes = []
    for k in out["examples"]:
        c = g[k][MAIN]["central"]
        outcomes.append(
            f"| {k} | {sgd(c['contributed'])} | {sgd(c['terminal_p10'])} | {sgd(c['terminal_p50'])} | {sgd(c['terminal_p90'])} | {pct(c['drawdown_median'])} | {pct(c['drawdown_p5'])} |"
        )
    bat = []
    for k, b in out["batching"].items():
        bat.append(
            f"| {k} | {sgd(b['monthly']['trading_costs_median'])} | {sgd(b['quarterly']['trading_costs_median'])} | {pct(b['monthly']['p_goal'])} | {pct(b['quarterly']['p_goal'])} |"
        )
    srs_rows = []
    for s in SHOWN_SETS:
        r = out["srs"][s]
        srs_rows.append(
            f"| {SET_LABELS[s]} | {sgd(r['relief_total'])} | {sgd(r['after_tax_withdrawals_median_srs'])} | {sgd(r['withdrawals_median_plain'])} | {sgd(r['tax_median'])} | {pct(r['srs_better_share'])} |"
        )
    h = out["histories"]
    hist_gap = out["historical_sgs_gap"]
    sp = out["headline_spread"]
    spread_sentence = (
        f"Assumption choice moves the result far more than the engine or market randomness: across the four sets the chance differs by {sp['set_min']:.0f}–{sp['set_max']:.0f} percentage points depending on the example, "
        f"against {sp['engine_min']:.0f}–{sp['engine_max']:.0f} points across the five engines (central assumptions) and at most ±{sp['noise_max']:.1f} points of simulation sampling noise (one standard error with {out['paths']:,} paths)."
    )
    return f"""# Simulation results (Phase 2)

Generated by `make all` from `reports/simulation_figures.json`; do not edit by hand. Rules: `docs/decisions.md` (2026-10-28, Phase 2 pre-registration), fixed before any simulation. **Hypothetical examples for education, not advice.** All amounts are in today's Singapore dollars (real), after fund costs and trading costs.

## How it works

- {out["paths"]:,} simulated monthly paths per case, seed {out["seed"]}. Monthly real returns are resampled from history in random-length blocks (stationary bootstrap, Politis & Romano 1994; mean block 24 months), then shifted so each asset's long-run compound return equals the assumption being tested.
- **Main history:** SGD-era returns, {h["H-SGD"]["start"]} to {h["H-SGD"]["end"]} ({h["H-SGD"]["months"]} months): developed-market equities converted to SGD, and a constant {out["sgs_duration"]}-year SGS bond, both after Singapore inflation. This supplies the ups and downs (volatility, crashes, how shares and bonds move together), not the average return.
- The portfolio is rebalanced monthly. Costs: an all-in holding cost of {pct(out["annual_cost"]["B"], 2)} to {pct(out["annual_cost"]["A"], 2)} a year depending on the mix (fund fees, withholding tax inside the equity fund, rebalancing), plus each purchase's actual broker, exchange, currency and spread costs, including minimum fees.
- The examples' share mixes are `Multi-Asset-Allocation`'s risk-menu mixes (59% the binding menu mix; 49%, 67% and 88% its SGD-era sensitivity mixes). **They are not age-based advice.**

## Chance of reaching the goal

**There is no single headline probability.** The headline is the chance under each assumption set, side by side. {spread_sentence}

| Example | Age | Saving | Years | Goal | Equity share | Central (low–high) | Bias-corrected equity (P2) | Historical equity + yield-based bonds | Historical global (reference) |
|---|---|---|---|---|---|---|---|---|---|
{chr(10).join(rows)}

![Chance of reaching the goal under four assumption sets](../reports/figures/simulation_p_goal.png)

What the sets assume (real, a year): central equities {pct(sets["central"]["equity"], 1)}, SGS {pct(sets["central"]["sgs"], 1)}; P2 equities {pct(sets["P2"]["equity"], 1)} with central SGS; historical equity + yield-based bonds: historical global equities {pct(sets["hist_eq_yield"]["equity"], 1)} with the forward SGS ({pct(sets["hist_eq_yield"]["sgs"], 1)}) and cash assumptions, because starting yields forecast bond returns well (`docs/cma.md`); historical global equities {pct(sets["historical"]["equity"], 1)}, bonds {pct(sets["historical"]["sgs"], 1)}, kept as a reference. **The historical bond figure is a global JST bond return (real USD, 1871–2020), not a historical SGS return:** it is {pct(hist_gap, 1)} a year above the SGS forward assumption, because today's SGS starting yield is low relative to the average real return of developed-market bonds over 1871–2020, a period that includes 1981–2020's long fall in yields.

**What "chance of reaching the goal" means:** the share of the {out["paths"]:,} simulated futures in which wealth at the goal date is at least the goal. It is only as good as the assumptions behind it, which is why three sets are shown.

## The range of outcomes (central assumptions)

| Example | Total saved | Wealth at goal date: 10th percentile | Median | 90th percentile | Typical largest fall | Largest fall, worst 5% of paths |
|---|---|---|---|---|---|---|
{chr(10).join(outcomes)}

![Example A fan chart](../reports/figures/simulation_fan_a.png)

**Why outcomes spread, and why the fan widens with time:** returns vary from month to month, and good or bad stretches compound. The longer the horizon, the more these stretches accumulate, so the gap between good and bad outcomes grows. The orange line follows the median of the worst 10% of futures; the dotted line shows the same savings held in cash.

**Largest fall** is the biggest peak-to-trough drop in the portfolio's value (ignoring new savings) at any point along a path, after inflation. It shows how deep a slump an investor would have had to sit through.

## Monthly saving needed for a chosen chance

The smallest monthly amount (to S$10) that reaches the goal with the stated probability, holding the initial amount, growth and horizon fixed.

| Example | Assumptions | 50% chance | 75% chance | 90% chance |
|---|---|---|---|---|
{chr(10).join(req)}

## How much the engine matters (central assumptions)

| Engine | Mean block or df | {" | ".join("Example " + k for k in out["examples"])} |
|---|---|---|---|---|---|
{chr(10).join(eng)}

The Student-t draws are independent month to month: fat tails, but no clustering of bad months. The US long-run history has no currency risk and uses a modelled bond.

## Investing monthly or quarterly (central assumptions)

Minimum broker fees make small purchases expensive; batching three months into one purchase reduces them.

| Example | Trading costs, monthly purchases (median total) | Quarterly purchases | Chance, monthly | Chance, quarterly |
|---|---|---|---|---|
{chr(10).join(bat)}

## SRS (example D, simplified)

Example D contributes the citizen cap through SRS. Tax relief at a {pct(out["srs_assumptions"]["marginal_rate"], 1)} marginal rate is reinvested a year later. From the goal date (age {out["srs_assumptions"]["statutory_retirement_age"]:.0f}, the statutory retirement age for a first contribution from 1 July 2026) the balance stays invested and is withdrawn over 10 years, half of each withdrawal taxed at IRAS resident rates with no other income. The comparison invests the same amounts outside SRS (no relief, no withdrawal tax) and withdraws on the same schedule.

| Assumptions | Total relief reinvested | After-tax withdrawals, SRS (median) | Withdrawals without SRS (median) | Tax paid (median) | Paths where SRS comes out ahead |
|---|---|---|---|---|---|
{chr(10).join(srs_rows)}

**The comparison doesn't value the loss of access:** money in SRS can't be withdrawn before the statutory retirement age without full tax and a 5% penalty, while money outside SRS can be used at any time. That flexibility has value the table leaves out.

Simplifications: the {sgd(out["srs_assumptions"]["relief_cap"])} overall relief cap is assumed not to bind; tax brackets and fee minimums are held constant in today's money; withdrawing before the statutory retirement age is taxed in full plus a 5% penalty (the app will warn when the goal date is earlier).

## Limits

- The equity central leaves out buybacks and is probably too low (`docs/cma.md`); P2 shows a bias-corrected alternative.
- The SGD-era history is short ({h["H-SGD"]["months"]} months) and starts in {h["H-SGD"]["start"]} because MAS's 10-year SGS benchmark begins in June 1998; developed markets only (no emerging markets).
- The ACWD spread is a default (0.10%), not measured; the fee schedules are one broker pair's published rates, used as cost data, not a recommendation.
- Taxes outside SRS, behaviour (stopping contributions after a fall) and changes in circumstances are not modelled.

*Contains information from MAS statistics (available from mas.gov.sg), made available under the terms of the Monetary Authority of Singapore's Terms of Use of Datasets. JST-derived figures are licensed CC BY-NC-SA 4.0.*
"""


def headline_spread(out: dict) -> dict[str, float]:
    """Percentage-point spread of P(goal) across assumption sets and across engines, and the
    largest Monte Carlo standard error, for the headline sentence."""
    sets, engines, noise = [], [], []
    for k in out["examples"]:
        p = [out["grid"][k][MAIN][s]["p_goal"] for s in SHOWN_SETS]
        e = [out["grid"][k][name]["central"]["p_goal"] for name in ENGINES]
        sets.append((max(p) - min(p)) * 100)
        engines.append((max(e) - min(e)) * 100)
        noise += [np.sqrt(x * (1 - x) / out["paths"]) * 100 for x in p]
    return {
        "set_min": min(sets),
        "set_max": max(sets),
        "engine_min": min(engines),
        "engine_max": max(engines),
        "noise_max": max(noise),
    }


def run() -> dict:
    out, charts = compute()
    FIGURES.mkdir(parents=True, exist_ok=True)
    fan_chart(*charts["fan"], EXAMPLES["A"])
    goal_chart(out)
    out["historical_sgs_gap"] = (
        out["cma_sets"]["historical"]["sgs"] - out["cma_sets"]["central"]["sgs"]
    )
    out["headline_spread"] = headline_spread(out)
    out = _clean(out)
    SIM_JSON.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    SIM_DOC.write_text(render(out))
    return out
