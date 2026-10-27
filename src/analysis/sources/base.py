"""Shared pieces for the source modules: the RawFile record and download helpers."""

import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import requests

from analysis.config import DATA_RAW

TIMEOUT = 120
RETRIES = 3  # FRED occasionally times out on the first request (reference/source_checks.csv)
HEADERS = {"User-Agent": "Goals-Planner research (github.com/azrinmahsuom)"}


def get(url: str) -> requests.Response:
    """GET with the project's user agent, retrying timeouts, failing on any HTTP error."""
    for attempt in range(1, RETRIES + 1):
        try:
            response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            response.raise_for_status()
            return response
        except (requests.Timeout, requests.ConnectionError):
            if attempt == RETRIES:
                raise
            time.sleep(5 * attempt)
    raise AssertionError("unreachable")


def default_download(url: str) -> bytes:
    return get(url).content


@dataclass(frozen=True)
class RawFile:
    """One file to download, with the provenance written to the manifest."""

    source: str  # folder under data/raw
    filename: str
    name: str
    landing_page: str
    series: str
    licence: str
    redistributable: bool
    units: str
    resolve_url: Callable[[], str]
    describe: Callable[[Path], tuple[int, str, str]]  # (rows, start, end)
    download: Callable[[str], bytes] = default_download
    manual: bool = False  # owner downloads it in a browser; fetch only records it

    @property
    def path(self) -> Path:
        return DATA_RAW / self.source / self.filename


def link_on_page(page: str, pattern: str) -> Callable[[], str]:
    """Resolver that finds the first href matching pattern on a landing page."""

    def resolve() -> str:
        html = get(page).text
        match = re.search(rf'href="([^"]*{pattern}[^"]*)"', html)
        if not match:
            raise RuntimeError(
                f"No link matching {pattern!r} on {page}. The source may have moved."
            )
        href = match.group(1).replace("&amp;", "&")
        if href.startswith("//"):
            return "https:" + href
        if href.startswith("/"):
            return re.match(r"https?://[^/]+", page).group(0) + href
        return href

    return resolve


def fixed(url: str) -> Callable[[], str]:
    """Resolver for a URL that doesn't change."""
    return lambda: url
