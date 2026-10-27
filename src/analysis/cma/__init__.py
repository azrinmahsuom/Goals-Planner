"""Capital market assumptions: historical forecasts, validation, forward estimates, scenarios.

Rules are pre-registered in docs/decisions.md (2026-10-28, "Phase 1 pre-registration").
"""

HORIZON = 10  # years: every CMA is a 10-year annualised geometric real return
BURN_IN = 30  # years of data before the first forecast
HAC_LAGS = HORIZON - 1  # overlapping 10-year windows share up to 9 years
AS_OF = "2026-09-30"  # forward inputs are taken at or before this date
JST_END_YEAR = 2015  # amendment 1, docs/decisions.md (2026-10-28)
