"""Monthly goals simulation in real SGD (Phase 2).

Rules are pre-registered in docs/decisions.md (2026-10-28, "Phase 2 pre-registration").
"""

PATHS = 10_000
SEED = 20261028
MEAN_BLOCK = 24  # stationary bootstrap, main case (months)
SENSITIVITY_BLOCKS = ("n^(1/3)", 60)
SGS_DURATION = 8.18  # A35 duration, reference/upstream/fund_facts.csv
ASSETS = ("equity", "sgs")
