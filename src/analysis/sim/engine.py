"""Return draws (stationary bootstrap or Student-t), portfolio paths and their summaries.

Draws are monthly simple real returns with shape (paths, months, assets). Both engines are
re-centred so the mean monthly log return of each asset equals ln(1 + CMA) / 12.
"""

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import special

from analysis.sim import ASSETS, MEAN_BLOCK, PATHS, SEED

DF_GRID = np.round(np.arange(2.5, 30.0001, 0.1), 1)
FAN_PERCENTILES = (5, 10, 25, 50, 75, 90, 95)
DRAWDOWN_PERCENTILES = (5, 25, 50, 75, 95)


def recentre(history: pd.DataFrame, cma: dict[str, float]) -> pd.DataFrame:
    """Monthly log real returns shifted so each asset's mean is ln(1 + CMA) / 12."""
    logs = np.log1p(history[list(ASSETS)])
    target = pd.Series({a: math.log1p(cma[a]) / 12 for a in ASSETS})
    return logs - logs.mean() + target


def mean_block(rule: int | str, n: int) -> int:
    """Mean block length in months: a number, or 'n^(1/3)' = ceil(n^(1/3))."""
    return math.ceil(n ** (1 / 3)) if rule == "n^(1/3)" else int(rule)


def stationary_indices(
    n: int, months: int, block: float, paths: int, rng: np.random.Generator
) -> np.ndarray:
    """Politis-Romano stationary bootstrap: each month continues the current block with
    probability 1 - 1/block, or starts a new block at a random month; wraps at the end."""
    idx = np.empty((paths, months), dtype=np.int64)
    idx[:, 0] = rng.integers(0, n, paths)
    restart = rng.random((paths, months)) < 1 / block
    fresh = rng.integers(0, n, (paths, months))
    for t in range(1, months):
        idx[:, t] = np.where(restart[:, t], fresh[:, t], (idx[:, t - 1] + 1) % n)
    return idx


def bootstrap_draws(
    history: pd.DataFrame,
    cma: dict[str, float],
    months: int,
    block: int | str = MEAN_BLOCK,
    paths: int = PATHS,
    seed: int = SEED,
) -> np.ndarray:
    logs = recentre(history, cma).to_numpy()
    rng = np.random.default_rng(seed)
    idx = stationary_indices(len(logs), months, mean_block(block, len(logs)), paths, rng)
    return np.expm1(logs[idx])


def _t_loglik(x: np.ndarray, mu: np.ndarray, scale: np.ndarray, df: float) -> float:
    d = x.shape[1]
    inv = np.linalg.inv(scale)
    q = np.einsum("ij,jk,ik->i", x - mu, inv, x - mu)
    const = (
        special.gammaln((df + d) / 2)
        - special.gammaln(df / 2)
        - d / 2 * np.log(df * np.pi)
        - 0.5 * np.linalg.slogdet(scale)[1]
    )
    return float(np.sum(const - (df + d) / 2 * np.log1p(q / df)))


def _t_em(x: np.ndarray, df: float, iterations: int = 200) -> tuple[np.ndarray, np.ndarray]:
    """EM estimates of the location and scale of a multivariate t with known df."""
    mu, scale = x.mean(axis=0), np.cov(x, rowvar=False)
    d = x.shape[1]
    for _ in range(iterations):
        q = np.einsum("ij,jk,ik->i", x - mu, np.linalg.inv(scale), x - mu)
        w = (df + d) / (df + q)
        mu_new = (w[:, None] * x).sum(axis=0) / w.sum()
        centred = x - mu_new
        scale_new = (w[:, None, None] * np.einsum("ij,ik->ijk", centred, centred)).mean(axis=0)
        done = np.allclose(mu_new, mu, atol=1e-12) and np.allclose(scale_new, scale, atol=1e-14)
        mu, scale = mu_new, scale_new
        if done:
            break
    return mu, scale


@dataclass(frozen=True)
class TFit:
    df: float
    scale: np.ndarray
    loglik: float


def fit_student_t(history: pd.DataFrame) -> TFit:
    """Degrees of freedom by maximum likelihood over DF_GRID (EM for the scale at each df)."""
    x = np.log1p(history[list(ASSETS)].to_numpy())
    best = None
    for df in DF_GRID:
        mu, scale = _t_em(x, df)
        ll = _t_loglik(x, mu, scale, df)
        if best is None or ll > best.loglik:
            best = TFit(float(df), scale, ll)
    return best


def student_t_draws(
    fit: TFit, cma: dict[str, float], months: int, paths: int = PATHS, seed: int = SEED
) -> np.ndarray:
    """Independent monthly multivariate-t log returns with the fitted df and scale, centred on
    ln(1 + CMA) / 12 (the t's mean equals its location for df > 1)."""
    rng = np.random.default_rng(seed)
    d = len(ASSETS)
    z = rng.multivariate_normal(np.zeros(d), fit.scale, size=(paths, months))
    chi = rng.chisquare(fit.df, size=(paths, months, 1))
    location = np.array([math.log1p(cma[a]) / 12 for a in ASSETS])
    return np.expm1(location + z / np.sqrt(chi / fit.df))


class DrawFactory:
    """Common random numbers: one set of bootstrap indices (or t innovations) per engine, reused
    for every CMA set, so differences between results come from the inputs, not the draws."""

    def __init__(
        self,
        history: pd.DataFrame,
        engine: str,
        months: int,
        block: int | str = MEAN_BLOCK,
        paths: int = PATHS,
        seed: int = SEED,
    ):
        self.history, self.engine, self.months = history, engine, months
        rng = np.random.default_rng(seed)
        if engine == "bootstrap":
            self.block = mean_block(block, len(history))
            self.idx = stationary_indices(len(history), months, self.block, paths, rng)
        elif engine == "student-t":
            self.fit = fit_student_t(history)
            d = len(ASSETS)
            z = rng.multivariate_normal(np.zeros(d), self.fit.scale, size=(paths, months))
            chi = rng.chisquare(self.fit.df, size=(paths, months, 1))
            self.innovations = z / np.sqrt(chi / self.fit.df)
        else:
            raise ValueError(engine)

    def draws(self, cma: dict[str, float], months: int | None = None) -> np.ndarray:
        months = months or self.months
        if self.engine == "bootstrap":
            logs = recentre(self.history, cma).to_numpy()
            return np.expm1(logs[self.idx[:, :months]])
        location = np.array([math.log1p(cma[a]) / 12 for a in ASSETS])
        return np.expm1(location + self.innovations[:, :months])


# --- portfolio paths ---


@dataclass(frozen=True)
class Plan:
    initial: float
    monthly: float
    growth: float  # real annual growth of the contribution, applied every 12 months
    months: int
    equity_share: float
    batching: str = "monthly"  # or "quarterly"


def contributions(plan: Plan) -> np.ndarray:
    """Planned contribution at the end of each month 1..months (real SGD)."""
    years = np.arange(plan.months) // 12
    return plan.monthly * (1 + plan.growth) ** years


@dataclass
class Paths:
    wealth: np.ndarray  # (paths, months + 1), real SGD, after all costs
    index: np.ndarray  # (paths, months + 1), unit-value portfolio index (no contributions)
    contributed: float
    trading_costs: np.ndarray  # (paths,), total one-off trading costs paid


def simulate(
    draws: np.ndarray,
    plan: Plan,
    annual_cost: float,
    order_cost=lambda amount, w: 0.0,
    cash_monthly: float = 0.0,
    extra: np.ndarray | None = None,
) -> Paths:
    """Rebalance monthly to the target mix; deduct the all-in annual cost monthly; buy the
    initial amount and each contribution (or each quarterly batch) at its own trade cost."""
    w = plan.equity_share
    weights = np.array([w, 1 - w])
    gross = draws[:, : plan.months, :] @ weights
    net = (1 + gross) * (1 - annual_cost) ** (1 / 12) - 1
    paths = draws.shape[0]
    wealth = np.empty((paths, plan.months + 1))
    first_cost = order_cost(plan.initial, w) if plan.initial > 0 else 0.0
    wealth[:, 0] = plan.initial - first_cost
    costs = np.full(paths, first_cost)
    buffer = np.zeros(paths)
    amounts = contributions(plan) + (0.0 if extra is None else extra)
    for t in range(1, plan.months + 1):
        current = wealth[:, t - 1] * (1 + net[:, t - 1])
        amount = amounts[t - 1]
        if plan.batching == "quarterly":
            buffer = buffer * (1 + cash_monthly) + amount
            if t % 3 == 0:
                cost = order_cost(buffer[0], w) if buffer[0] > 0 else 0.0  # same on every path
                current = current + buffer - cost
                costs += cost
                buffer = np.zeros(paths)
            wealth[:, t] = current + (buffer if t == plan.months else 0.0)
        else:
            cost = order_cost(amount, w) if amount > 0 else 0.0
            wealth[:, t] = current + amount - cost
            costs += cost
    index = np.concatenate([np.ones((paths, 1)), np.cumprod(1 + net, axis=1)], axis=1)
    return Paths(wealth, index, float(plan.initial + amounts.sum()), costs)


def max_drawdowns(index: np.ndarray) -> np.ndarray:
    """Largest peak-to-trough fall of each path's unit-value index (negative decimals)."""
    return (index / np.maximum.accumulate(index, axis=1) - 1).min(axis=1)


def summarise(p: Paths, goal: float) -> dict:
    terminal = p.wealth[:, -1]
    worst = terminal <= np.percentile(terminal, 10)
    dd = max_drawdowns(p.index)
    return {
        "p_goal": float((terminal >= goal).mean()),
        "terminal_percentiles": {q: float(np.percentile(terminal, q)) for q in FAN_PERCENTILES},
        "fan": {q: np.percentile(p.wealth, q, axis=0) for q in FAN_PERCENTILES},
        "worst_decile_median_path": np.median(p.wealth[worst], axis=0),
        "drawdown_percentiles": {q: float(np.percentile(dd, q)) for q in DRAWDOWN_PERCENTILES},
        "contributed": p.contributed,
        "trading_costs_median": float(np.median(p.trading_costs)),
    }


def required_monthly(
    draws: np.ndarray,
    plan: Plan,
    goal: float,
    probability: float,
    annual_cost: float,
    order_cost=lambda amount, w: 0.0,
    cash_monthly: float = 0.0,
    step: float = 10.0,
    ceiling: float = 100_000.0,
) -> float | None:
    """Smallest monthly contribution (multiple of `step`) with P(goal) >= probability, by
    bisection on the same draws; None if not reachable at `ceiling`."""

    def ok(monthly: float) -> bool:
        p = simulate(draws, _with_monthly(plan, monthly), annual_cost, order_cost, cash_monthly)
        return (p.wealth[:, -1] >= goal).mean() >= probability

    if ok(0.0):
        return 0.0
    if not ok(ceiling):
        return None
    lo, hi = 0, int(ceiling / step)
    while hi - lo > 1:
        mid = (lo + hi) // 2
        lo, hi = (lo, mid) if ok(mid * step) else (mid, hi)
    return hi * step


def _with_monthly(plan: Plan, monthly: float) -> Plan:
    return Plan(plan.initial, monthly, plan.growth, plan.months, plan.equity_share, plan.batching)


def cash_path(plan: Plan, cash_annual: float) -> np.ndarray:
    """Deterministic 'held in cash' reference: same contributions earning the cash CMA."""
    r = (1 + cash_annual) ** (1 / 12) - 1
    out = np.empty(plan.months + 1)
    out[0] = plan.initial
    for t, amount in enumerate(contributions(plan), start=1):
        out[t] = out[t - 1] * (1 + r) + amount
    return out
