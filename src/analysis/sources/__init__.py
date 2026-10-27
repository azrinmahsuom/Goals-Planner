"""Download public data sources to data/raw/<source>/ and record each file in the manifest.

Each source module (shiller, jst, fred, ...) lists its RawFile entries in FILES and parses its
raw files into tidy tables. Every URL, series ID and licence was checked against the primary
page on 2026-10-28 (reference/source_checks.csv).

A file already on disk is not re-downloaded. If a fresh download differs from the hash in the
committed manifest, it is kept and reported as changed since snapshot; accept the new version
only via fetch_all(refresh=True). Adapted from Multi-Asset-Allocation (commit a92a325,
src/analysis/sources.py).
"""

import pandas as pd

from analysis import manifest
from analysis.config import DATA_RAW
from analysis.sources import damodaran, documents, fred, jst, mas, shiller, singstat, spf
from analysis.sources.base import RawFile

REGISTRY: list[RawFile] = [
    *shiller.FILES,
    *jst.FILES,
    *fred.FILES,
    *mas.FILES,
    *singstat.FILES,
    *spf.FILES,
    *damodaran.FILES,
    *documents.FILES,
]


def fetch(raw: RawFile, refresh: bool = False) -> str:
    """Download one file and record it. Returns 'skipped', 'recorded', 'unchanged' or 'changed'.

    'changed' means a new download differs from the committed manifest hash: the new file is
    kept on disk and the manifest (the snapshot) is left alone until accepted with refresh.

    Manual files are never downloaded. A missing one raises with the URL to fetch it from; a
    present one is recorded on first sight (or on refresh), dated by the file's save time.
    """
    key = raw.path.relative_to(DATA_RAW).as_posix()
    url = raw.resolve_url()
    if raw.manual:
        if not raw.path.exists():
            raise FileNotFoundError(
                f"{raw.name} must be downloaded by hand. "
                f"Download {url} in a browser and save it as {raw.path}."
            )
        if key in manifest.load() and not refresh:
            return "skipped"
        retrieved = pd.Timestamp.fromtimestamp(raw.path.stat().st_mtime).strftime("%Y-%m-%d")
    else:
        if raw.path.exists() and not refresh:
            return "skipped"
        content = raw.download(url)
        raw.path.parent.mkdir(parents=True, exist_ok=True)
        raw.path.write_bytes(content)
        retrieved = pd.Timestamp.today().strftime("%Y-%m-%d")
        previous = manifest.load().get(key)
        if previous and not refresh:
            same = previous["sha256"] == manifest.sha256(raw.path)
            return "unchanged" if same else "changed"

    rows, start, end = raw.describe(raw.path)
    manifest.record(
        raw.path,
        {
            "source": raw.name,
            "url": url,
            "landing_page": raw.landing_page,
            "series": raw.series,
            "retrieved": retrieved,
            "manual_download": raw.manual,
            "licence": raw.licence,
            "redistributable": raw.redistributable,
            "rows": rows,
            "start": start,
            "end": end,
            "units": raw.units,
        },
    )
    return "recorded"


def fetch_all(refresh: bool = False) -> dict[str, str]:
    """Fetch every registered file; returns each file's status keyed by its data/raw path."""
    results = {}
    for raw in REGISTRY:
        key = raw.path.relative_to(DATA_RAW).as_posix()
        try:
            results[key] = fetch(raw, refresh)
        except FileNotFoundError as err:  # a manual download not yet saved
            results[key] = f"manual step needed: {err}"
    return results
