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
    marginal_rate: float  # at contribution, entered by the user
    other_income_in_retirement: float = 0.0


def annual_cap(srs: SRS) -> float:
    r = rules()
    return r["contribution_cap_citizen_spr" if srs.citizen_or_pr else "contribution_cap_foreigner"]


def capped_plan(plan: Plan, srs: SRS) -> Plan:
    """The plan with each year's contributions limited to the SRS cap (monthly = cap / 12)."""
    monthly_cap = annual_cap(srs) / 12
    return Plan(
        plan.initial,
        min(plan.monthly, monthly_cap),
        plan.growth
        if plan.monthly * (1 + plan.growth) ** (plan.months // 12) <= monthly_cap
        else 0.0,
        plan.months,
        plan.equity_share,
        plan.batching,
    )


def relief_schedule(plan: Plan, srs: SRS) -> np.ndarray:
    """Tax relief on each month's contribution, reinvested 12 months later (length = months)."""
    relief = np.zeros(plan.months)
    paid = np.minimum(contributions(plan), annual_cap(srs) / 12) * srs.marginal_rate
    relief[12:] = paid[: plan.months - 12]
    return relief


def premature(srs: SRS, months: int) -> bool:
    """True if the goal date falls before the statutory retirement age."""
    return srs.age + months / 12 < rules()["statutory_retirement_age"]


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
    """Full withdrawal before the statutory retirement age: taxed in full at the marginal rate
    plus the 5% penalty."""
    r = rules()
    return balance * (1 - r["taxable_share_premature"] * srs.marginal_rate - r["premature_penalty"])
