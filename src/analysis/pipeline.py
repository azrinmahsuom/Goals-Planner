"""End-to-end run: fetch -> verify -> cma -> report.

Run with: uv run python -m analysis.pipeline [stage]
Stages: fetch, refresh (re-download and accept source updates), verify, upstream (re-vendor the
earlier projects' figures), cma, report, all (default; everything except upstream).

Live sources update over time. A download that differs from the committed snapshot
(data/MANIFEST.yaml) is reported as "changed since snapshot" in data/processed/drift_report.md
and the run continues. Only a missing file stops the run.
"""

import argparse

from analysis import manifest, sources, upstream
from analysis.cma import report as cma_report
from analysis.cma import run as cma_run
from analysis.config import FIGURES, ROOT
from analysis.sources import documents


def fetch(refresh: bool = False) -> None:
    """Download any missing raw files and record them in data/MANIFEST.yaml."""
    manual = []
    for key, status in sources.fetch_all(refresh=refresh).items():
        if status.startswith("manual step needed"):
            manual.append(status)
            continue
        label = "changed since snapshot" if status == "changed" else status
        print(f"{label:>9}  {key}")
    if manual:
        raise SystemExit(
            "\nManual steps before the run can continue:\n  "
            + "\n  ".join(manual)
            + "\nThen run `make all` again; files already downloaded are kept."
        )


def verify() -> None:
    """Check raw files against the snapshot hashes and the vendored upstream tables exist.

    Missing files stop the run; files changed since the snapshot go to the drift report."""
    status = manifest.verify_data()
    print(f"Verified {len(status['ok'])} raw files against data/MANIFEST.yaml.")
    for key in status["changed"]:
        print(f"  changed since snapshot: {key}")
    report = manifest.write_drift_report(status)
    print(f"Wrote {report.relative_to(ROOT)}.")
    for name in ("fund_facts", "mix_costs", "risk_menu", "historical_mix_returns"):
        upstream.load(name)
    print("Found the vendored upstream tables in reference/upstream/.")
    checks = documents.verify_reference()
    print(f"Confirmed {checks} quoted figures on their cited document pages.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    stages = ["fetch", "refresh", "verify", "upstream", "cma", "report", "all"]
    parser.add_argument("stage", nargs="?", default="all", choices=stages)
    stage = parser.parse_args().stage

    FIGURES.mkdir(parents=True, exist_ok=True)
    if stage == "upstream":
        for name, rows in upstream.refresh().items():
            print(f"Wrote reference/upstream/{name}.csv ({rows} rows).")
        return
    if stage in ("fetch", "refresh", "all"):
        fetch(refresh=stage == "refresh")
    if stage in ("verify", "all"):
        verify()
    if stage in ("cma", "all"):
        summary = cma_run.run()
        print(f"Wrote {cma_run.SUMMARY.relative_to(ROOT)} ({len(summary)} rows).")
    if stage in ("report", "all"):
        cma_report.run()
        print(f"Wrote {cma_report.FIGURES_JSON.relative_to(ROOT)} and docs/cma.md.")


if __name__ == "__main__":
    main()
