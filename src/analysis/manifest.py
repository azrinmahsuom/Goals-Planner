"""Provenance record for data/raw: one MANIFEST.yaml entry per downloaded file.

The manifest is committed; the data is not. data_status() re-hashes every file so a live
source that changed since the snapshot is reported as drift, and a missing file stops the run.
Adapted from Multi-Asset-Allocation (commit a92a325, src/analysis/manifest.py).
"""

import hashlib
from pathlib import Path

import yaml

from analysis.config import DATA_RAW, DRIFT_REPORT, MANIFEST


class DataVerificationError(RuntimeError):
    """Raised when a raw file listed in the manifest is missing."""


def sha256(path: Path) -> str:
    """SHA-256 hex digest of a file."""
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load(manifest_path: Path = MANIFEST) -> dict[str, dict]:
    """Manifest entries keyed by path relative to data/raw (empty if no manifest yet)."""
    if not manifest_path.exists():
        return {}
    content = yaml.safe_load(manifest_path.read_text()) or {}
    return content.get("files") or {}


def save(entries: dict[str, dict], manifest_path: Path = MANIFEST) -> None:
    """Write entries to the manifest, sorted by path so diffs stay readable."""
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    header = (
        "# Provenance of every file in data/raw. Written by analysis.sources; don't edit by hand.\n"
        "# Raw files are not committed; verify with: make verify\n"
    )
    body = yaml.safe_dump(
        {"files": dict(sorted(entries.items()))}, sort_keys=False, allow_unicode=True
    )
    manifest_path.write_text(header + body)


def record(
    path: Path, meta: dict, manifest_path: Path = MANIFEST, raw_root: Path = DATA_RAW
) -> dict:
    """Add or replace the manifest entry for one raw file, hashing it now."""
    key = path.relative_to(raw_root).as_posix()
    entry = {**meta, "sha256": sha256(path)}
    entries = load(manifest_path)
    entries[key] = entry
    save(entries, manifest_path)
    return entry


def data_status(manifest_path: Path = MANIFEST, raw_root: Path = DATA_RAW) -> dict[str, list]:
    """Each manifest entry's state: 'ok', 'missing' or 'changed' (the file's hash differs from
    the snapshot recorded in the manifest, e.g. a live source updated since it was taken)."""
    status: dict[str, list] = {"ok": [], "missing": [], "changed": []}
    for key, entry in load(manifest_path).items():
        path = raw_root / key
        if not path.exists():
            status["missing"].append(key)
        elif sha256(path) != entry["sha256"]:
            status["changed"].append(key)
        else:
            status["ok"].append(key)
    return status


def write_drift_report(
    status: dict[str, list], manifest_path: Path = MANIFEST, report_path: Path = DRIFT_REPORT
) -> Path:
    """List the files that differ from the snapshot, with the date each snapshot was taken.

    The effect of the drift on the headline CMAs is appended by the CMA stage (Phase 1)."""
    entries = load(manifest_path)
    lines = ["# Drift report", ""]
    if status["changed"]:
        lines += [
            "These raw files differ from the snapshot in data/MANIFEST.yaml:",
            "",
            "| File | Snapshot retrieved | Source |",
            "|---|---|---|",
        ]
        for key in status["changed"]:
            entry = entries[key]
            lines.append(f"| {key} | {entry.get('retrieved', '?')} | {entry.get('source', '?')} |")
    else:
        lines.append("No raw file differs from the snapshot.")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n")
    return report_path


def verify_data(manifest_path: Path = MANIFEST, raw_root: Path = DATA_RAW) -> dict[str, list]:
    """Check every manifest entry against its file and return the status.

    Missing files raise DataVerificationError; changed files are only reported."""
    status = data_status(manifest_path, raw_root)
    if status["missing"]:
        raise DataVerificationError(
            "Missing raw files (run `make fetch`): " + ", ".join(status["missing"])
        )
    return status
