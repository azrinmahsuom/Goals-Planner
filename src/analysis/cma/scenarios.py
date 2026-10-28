"""Low / central / high scenarios: central -/+ the wider of (a) the method spread and (b) the
moving-block bootstrap standard error of the central estimate (docs/decisions.md, 2026-10-28).
"""

import math

import numpy as np
import pandas as pd

from analysis.cma.validate import REPLICATIONS, SEED, block_indices


def block_length(n: int) -> int:
    """ceil(n^(1/3)) (Hall, Horowitz & Jing 1995)."""
    return math.ceil(n ** (1 / 3))


def resample(series: pd.Series, rng: np.random.Generator) -> np.ndarray:
    values = series.to_numpy()
    return values[block_indices(len(values), block_length(len(values)), rng)]


def compound_rate(rates: np.ndarray) -> float:
    """Annualised rate from a sequence of annual rates."""
    return float(np.exp(np.log1p(rates).mean()) - 1)


def inflation_draws(annual: pd.Series, reps: int = REPLICATIONS, seed: int = SEED) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return np.array([compound_rate(resample(annual, rng)) for _ in range(reps)])


def dividend_growth_draws(
    annual_by_country: dict[str, pd.Series], reps: int = REPLICATIONS, seed: int = SEED
) -> np.ndarray:
    """Cross-country median of real dividend growth, resampling the same blocks of calendar
    years for every country (amendment 4, docs/decisions.md): a drawn year outside a country's
    run contributes nothing for that country."""
    years = sorted(set().union(*(s.index for s in annual_by_country.values())))
    rng = np.random.default_rng(seed)
    draws = []
    for _ in range(reps):
        drawn = [years[i] for i in block_indices(len(years), block_length(len(years)), rng)]
        growth = []
        for s in annual_by_country.values():
            rates = s.reindex(drawn).dropna().to_numpy()
            if len(rates):
                growth.append(compound_rate(rates))
        draws.append(np.median(growth))
    return np.array(draws)


def mean_draws(series: pd.Series, reps: int = REPLICATIONS, seed: int = SEED) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return np.array([resample(series, rng).mean() for _ in range(reps)])


def scenario(central: float, spread: float, se: float) -> dict[str, float | str]:
    """Low and high = central -/+ max(spread, se); records which one set the width."""
    width = max(spread, se)
    return {
        "low": central - width,
        "central": central,
        "high": central + width,
        "spread_a": spread,
        "bootstrap_se_b": se,
        "width_set_by": "(a) method spread" if spread >= se else "(b) bootstrap standard error",
    }
