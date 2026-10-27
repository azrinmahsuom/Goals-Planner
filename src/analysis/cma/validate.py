"""Out-of-sample forecast evaluation for 10-year return forecasts made at annual origins.

Each method supplies, per origin year, a forecast made with data up to that origin and the
realised annualised return over the next HORIZON years. The benchmark is the historical mean
of realised HORIZON-year returns whose windows had *ended* by the origin (no look-ahead).
"""

import numpy as np
import pandas as pd

from analysis.cma import HAC_LAGS, HORIZON


def annualised(growth: pd.Series, years: int = HORIZON) -> pd.Series:
    """Annualised return from a gross growth factor over `years`."""
    return growth ** (1 / years) - 1


def forward_return(level: pd.Series, years: int = HORIZON) -> pd.Series:
    """Realised annualised return from each year t to t + years, for an annual index level.

    NaN where the window runs past the data or the series has a gap."""
    future = level.reindex(level.index + years).to_numpy()
    return annualised(pd.Series(future, index=level.index) / level, years)


def historical_mean(realised: pd.Series, years: int = HORIZON) -> pd.Series:
    """At each origin t, the mean realised return of windows that had ended by t
    (origins <= t - years)."""
    out = {}
    for t in realised.index:
        done = realised[(realised.index <= t - years)].dropna()
        out[t] = done.mean() if len(done) else np.nan
    return pd.Series(out, name="historical_mean")


def newey_west_se(errors: pd.Series, lags: int = HAC_LAGS) -> float:
    """HAC (Newey-West, Bartlett weights) standard error of the mean of errors."""
    e = errors.dropna().to_numpy()
    n = len(e)
    if n < 2:
        return np.nan
    d = e - e.mean()
    variance = d @ d / n
    for lag in range(1, min(lags, n - 1) + 1):
        variance += 2 * (1 - lag / (lags + 1)) * (d[lag:] @ d[:-lag]) / n
    return float(np.sqrt(variance / n))


def evaluate(frame: pd.DataFrame, lags: int = HAC_LAGS) -> dict[str, float]:
    """Statistics on origins that have a forecast, a realised return and a benchmark.

    frame: columns forecast, realised, historical_mean, indexed by origin year."""
    df = frame[["forecast", "realised", "historical_mean"]].dropna()
    error = df["forecast"] - df["realised"]
    benchmark_sse = ((df["realised"] - df["historical_mean"]) ** 2).sum()
    n = len(df)
    return {
        "first_origin": int(df.index.min()) if n else np.nan,
        "last_origin": int(df.index.max()) if n else np.nan,
        "origins": n,
        "effective_n": n / HORIZON,
        "bias": error.mean(),
        "bias_hac_se": newey_west_se(error, lags),
        "mae": error.abs().mean(),
        "rmse": float(np.sqrt((error**2).mean())),
        "correlation": df["forecast"].corr(df["realised"]),
        "oos_r2": 1 - (error**2).sum() / benchmark_sse if benchmark_sse > 0 else np.nan,
        "error_p10": error.quantile(0.10),
        "error_p90": error.quantile(0.90),
    }


def evaluate_pooled(frames: dict[str, pd.DataFrame], lags: int = HAC_LAGS) -> dict[str, float]:
    """Pooled statistics across countries. The bias standard error uses the cross-country
    average error per origin year, so errors that are correlated across countries in the
    same year are not counted as independent."""
    stacked = pd.concat(frames, names=["country", "origin"])
    stats = evaluate(stacked.reset_index(level="country", drop=True).reset_index(drop=True))
    df = stacked[["forecast", "realised", "historical_mean"]].dropna()
    by_year = (df["forecast"] - df["realised"]).groupby(level="origin").mean()
    stats.update(
        {
            "first_origin": int(df.index.get_level_values("origin").min()),
            "last_origin": int(df.index.get_level_values("origin").max()),
            "countries": int(df.index.get_level_values("country").nunique()),
            "effective_n": len(by_year) / HORIZON,
            "bias_hac_se": newey_west_se(by_year, lags),
        }
    )
    return stats
