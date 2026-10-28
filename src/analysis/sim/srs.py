"""Simplified, optional SRS module: capped contributions, tax relief reinvested a year later,
and withdrawal tax (docs/decisions.md, 2026-10-28, Phase 2 pre-registration, section 8).

Rules come from reference/srs_rules.csv and reference/iras_resident_tax_rates.csv (IRAS pages,
saved and hashed). Brackets are held constant in real terms.
"""

from dataclasses import dataclass
from functools import cache

import numpy as np
import pandas as pd

from analysis.config import REFERENCE
from analysis.sim.engine import Plan, contributions


@cache
def rules() -> pd.Series:
    return pd.read_csv(REFERENCE / "srs_rules.csv").set_index("rule")["value"].astype(float)


@cache
def tax_bands() -> pd.DataFrame:
    return pd.read_csv(REFERENCE / "iras_resident_tax_rates.csv")


def resident_tax(income: float | np.ndarray) -> np.ndarray:
    """IRAS resident income tax on chargeable income (YA 2024 onwards schedule)."""
    income = np.asarray(income, dtype=float)
    tax = np.zeros_like(income)
    for _, band in tax_bands().iterrows():
        top = np.inf if pd.isna(band["band_to"]) else band["band_to"]
        tax += np.clip(income - band["band_from"], 0, top - band["band_from"]) * band["rate"]
    return tax


@dataclass(frozen=True)
class SRS:
    age: int
    citizen_or_pr: bool
    marginal_rate: float  # at contribution, entered by the user (used for relief)
    other_income_in_retirement: float = 0.0
    statutory_age: float | None = None  # fixed at the first contribution; default from IRAS

    def retirement_age(self) -> float:
        return self.statutory_age or rules()["statutory_retirement_age"]


def annual_cap(srs: SRS) -> float:
    r = rules()
    return r["contribution_cap_citizen_spr" if srs.citizen_or_pr else "contribution_cap_foreigner"]


@dataclass(frozen=True)
class Split:
    """Monthly flows of an SRS plan (docs/decisions.md, 2026-10-28, Phase 4)."""

    into_srs: np.ndarray  # each month's planned saving up to the cap / 12
    outside: np.ndarray  # saving above the cap, plus relief reinvested a year later
    final_relief: float  # relief on the last 12 months' contributions, counted at the goal date
    relief_total: float


def split(plan: Plan, srs: SRS) -> Split:
    """Cap applied month by month (so year by year): up to cap / 12 goes into SRS, the excess
    is invested outside SRS. Relief, a tax saving rather than an SRS contribution, is invested
    outside SRS 12 months after the contribution; the final year's relief counts at the goal."""
    planned = contributions(plan)
    into_srs = np.minimum(planned, annual_cap(srs) / 12)
    relief = into_srs * srs.marginal_rate
    outside = planned - into_srs
    outside[12:] += relief[: plan.months - 12]
    final_relief = float(relief[max(0, plan.months - 12) :].sum())
    return Split(into_srs, outside, final_relief, float(relief.sum()))


def premature(srs: SRS, months: int) -> bool:
    """True if the goal date falls before the statutory retirement age for the account."""
    return srs.age + months / 12 < srs.retirement_age()


def withdraw(balance_paths: np.ndarray, annual_returns: np.ndarray, srs: SRS, taxed: bool) -> dict:
    """Withdraw over the 10-year period, the rest staying invested: each year balance / years
    remaining. Returns total after-tax withdrawals per path (real SGD).

    annual_returns: (paths, 10) net annual portfolio returns during the withdrawal period."""
    r = rules()
    years = int(r["withdrawal_period"])
    balance = balance_paths.copy()
    after_tax = np.zeros_like(balance)
    taxes = np.zeros_like(balance)
    for k in range(years):
        tranche = balance / (years - k)
        tax = (
            resident_tax(r["taxable_share_penalty_free"] * tranche + srs.other_income_in_retirement)
            - resident_tax(srs.other_income_in_retirement)
            if taxed
            else np.zeros_like(tranche)
        )
        after_tax += tranche - tax
        taxes += tax
        balance = (balance - tranche) * (1 + annual_returns[:, k]) if k < years - 1 else 0.0
    return {"after_tax_withdrawals": after_tax, "tax_paid": taxes}


def premature_net(balance: np.ndarray, srs: SRS) -> np.ndarray:
    """Full withdrawal before the statutory retirement age: the whole balance is taxable income,
    taxed progressively at IRAS resident rates on top of other income, plus the 5% penalty."""
    r = rules()
    other = srs.other_income_in_retirement
    tax = resident_tax(r["taxable_share_premature"] * balance + other) - resident_tax(other)
    return balance - tax - r["premature_penalty"] * balance
