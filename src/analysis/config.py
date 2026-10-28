"""Project paths and settings. Import from here rather than hardcoding paths."""

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
DATA_RAW = ROOT / "data" / "raw"
DATA_EXTERNAL = ROOT / "data" / "external"
DATA_PROCESSED = ROOT / "data" / "processed"
MANIFEST = ROOT / "data" / "MANIFEST.yaml"  # committed: provenance and hashes of data/raw
DRIFT_REPORT = DATA_PROCESSED / "drift_report.md"
REFERENCE = ROOT / "reference"  # committed, hand-researched inputs
UPSTREAM = REFERENCE / "upstream"  # committed, derived figures vendored from the earlier projects
REPORTS = ROOT / "reports"
FIGURES = REPORTS / "figures"
DOCS = ROOT / "docs"

load_dotenv(ROOT / ".env")

# Fresh-clone rebuild tolerance (docs/decisions.md, 2026-10-28): a re-download may move a
# headline annual CMA (central, low or high) by at most this much before `verify` fails.
DRIFT_TOLERANCE_BPS = 10
# Same for the main engine's headline chances (docs/decisions.md, 2026-10-28, Phase 4).
SIM_DRIFT_TOLERANCE_PP = 1.0

TRADING_DAYS = 252


def get_secret(name: str) -> str:
    """Return an API key from the environment, failing clearly if it's missing."""
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} is not set. Copy .env.example to .env and add it.")
    return value
