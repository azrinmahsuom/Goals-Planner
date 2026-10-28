"""Fund and survey documents: ACWD factsheet, SPDR I annual report, MAS SPF (manual).

Figures from these documents live in reference/fund_documents.csv with page references;
verify_reference() re-reads each cited page and fails if the quoted text isn't there.
"""

import html
import re
from pathlib import Path

import pandas as pd
import pypdf

from analysis.config import REFERENCE
from analysis.sources.base import RawFile, fixed

SSGA = "https://www.ssga.com/library-content/products/"
ISSUER_LICENCE = "Issuer document; downloaded for citation only. Not redistributable."
MAS_SPF_PAGE = "https://www.mas.gov.sg/monetary-policy/mas-survey-of-professional-forecasters"
MAS_SPF_FILE = (
    "https://www.mas.gov.sg/-/media/mas-media-library/monetary-policy/"
    "mas-survey-of-professional-forecasters/2026/sep26q3.xlsx"
)


def describe_pdf(path: Path) -> tuple[int, str, str]:
    return len(pypdf.PdfReader(path).pages), "n/a", "n/a"


def describe_xlsx(path: Path) -> tuple[int, str, str]:
    return len(pd.ExcelFile(path).sheet_names), "n/a", "n/a"


FILES = [
    RawFile(
        source="documents",
        filename="ACWD_factsheet.pdf",
        name="State Street SPDR MSCI All Country World UCITS ETF (Acc), factsheet",
        landing_page=(
            "https://www.ssga.com/uk/en_gb/intermediary/etfs/"
            "state-street-spdr-msci-all-country-world-ucits-etf-acc-spyy-gy"
        ),
        series="Fund document (PDF): monthly factsheet (TER, index dividend yield, P/E FY1)",
        licence=ISSUER_LICENCE + " Marked for professional clients; figures cited by page.",
        redistributable=False,
        units="PDF; figures checked against reference/fund_documents.csv.",
        resolve_url=fixed(SSGA + "factsheets/etfs/emea/factsheet-emea-en_gb-spyy-gy.pdf"),
        describe=describe_pdf,
    ),
    RawFile(
        source="documents",
        filename="SPDR_I_annual_report.pdf",
        name="SSGA SPDR ETFs Europe I plc, annual report and audited financial statements",
        landing_page=(
            "https://www.ssga.com/uk/en_gb/intermediary/etfs/"
            "state-street-spdr-msci-all-country-world-ucits-etf-acc-spyy-gy"
        ),
        series="Fund document (PDF): annual report, financial year ended 31 March 2026",
        licence=ISSUER_LICENCE,
        redistributable=False,
        units="PDF; figures checked against reference/fund_documents.csv.",
        resolve_url=fixed(SSGA + "fund-docs/etfs/emea/1-GENERIC-EN-AR-IRISH-SPDR-I.pdf"),
        describe=describe_pdf,
    ),
    RawFile(
        source="documents",
        filename="MAS_SPF_sep26q3.xlsx",
        name="MAS Survey of Professional Forecasters, September 2026 (near-term cross-check)",
        landing_page=MAS_SPF_PAGE,
        series="Quarterly survey results workbook (CPI-All Items medians)",
        licence="MAS Terms of Use (to confirm for this publication); figures cited with source.",
        redistributable=False,
        units="xlsx as published by MAS.",
        resolve_url=fixed(MAS_SPF_FILE),
        describe=describe_xlsx,
        manual=True,  # MAS returns a web page, not the file, to scripted requests
    ),
]
IRAS = "https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/"
IRAS_PAGES = {
    "IRAS_srs_contributions.html": (
        "SRS contributions and tax relief",
        "special-tax-schemes/srs-contributions",
    ),
    "IRAS_srs_withdrawals.html": (
        "Tax on SRS withdrawals",
        "special-tax-schemes/tax-on-srs-withdrawals",
    ),
    "IRAS_tax_rates.html": (
        "Individual income tax rates",
        "tax-residency-and-tax-rates/individual-income-tax-rates",
    ),
}
FILES += [
    RawFile(
        source="documents",
        filename=filename,
        name=f"IRAS: {title}",
        landing_page=IRAS + path,
        series="Web page (HTML), saved for citation; rules in reference/srs_rules.csv",
        licence="IRAS website content; cited by title. Not redistributed.",
        redistributable=False,
        units="HTML; quoted rules checked by verify_reference().",
        resolve_url=fixed(IRAS + path),
        describe=lambda path: (len(path.read_bytes()), "n/a", "n/a"),
    )
    for filename, (title, path) in IRAS_PAGES.items()
]
FACTSHEET, ANNUAL_REPORT = FILES[0].path, FILES[1].path
CONTRIBUTIONS_PAGE, WITHDRAWALS_PAGE, RATES_PAGE = (FILES[i].path for i in (3, 4, 5))

# (document, PDF page (1-based), text that must appear on it, reference fields it supports).
# The annual report's PDF page 802 is printed page 799; PDF page 1136 is printed page 1133.
CHECKS = [
    (FACTSHEET, 1, "TER 0.12%", ["ter"]),
    (FACTSHEET, 2, "Index Dividend Yield 1.57%", ["index_dividend_yield"]),
    (FACTSHEET, 2, "Price/Earnings Ratio FY1 23.84", ["pe_fy1"]),
    (
        ANNUAL_REPORT,
        802,
        "Dividend income 140,163,819 73,093,049",
        ["dividend_income_fy2026", "dividend_income_fy2025"],
    ),
    (
        ANNUAL_REPORT,
        802,
        "Withholding tax on investment income 2 (17,687,265) (9,147,920)",
        ["withholding_tax_fy2026", "withholding_tax_fy2025"],
    ),
    (ANNUAL_REPORT, 1136, "Dividend income is shown gross of any", []),
    (CONTRIBUTIONS_PAGE, None, "$15,300", ["contribution_cap_citizen_spr"]),
    (CONTRIBUTIONS_PAGE, None, "$35,700", ["contribution_cap_foreigner"]),
    (
        CONTRIBUTIONS_PAGE,
        None,
        "personal income tax relief cap of $80,000",
        ["personal_relief_cap"],
    ),
    (
        WITHDRAWALS_PAGE,
        None,
        "statutory retirement age (64 effective from 1 Jul 2026)",
        ["statutory_retirement_age"],
    ),
    (WITHDRAWALS_PAGE, None, "50% of withdrawal sum", ["taxable_share_penalty_free"]),
    (WITHDRAWALS_PAGE, None, "100% of withdrawal sum", ["taxable_share_premature"]),
    (
        WITHDRAWALS_PAGE,
        None,
        "early withdrawals are fully subject to tax and attract a 5% penalty",
        ["premature_penalty"],
    ),
    (WITHDRAWALS_PAGE, None, "over 10 years", ["withdrawal_period"]),
    (RATES_PAGE, None, "In excess of $1,000,000", ["resident tax bands"]),
]


def _normalise(text: str) -> str:
    return " ".join(text.split())


def page_text(path: Path, page: int | None) -> str:
    """Whitespace-normalised text of one PDF page (1-based), or of a whole HTML page."""
    if page is None:
        raw = path.read_text(encoding="utf-8", errors="ignore")
        raw = re.sub(r"<script.*?</script>|<style.*?</style>", " ", raw, flags=re.S)
        return _normalise(html.unescape(re.sub(r"<[^>]+>", " ", raw)))
    return _normalise(pypdf.PdfReader(path).pages[page - 1].extract_text() or "")


def fund_documents(path: Path = REFERENCE / "fund_documents.csv") -> pd.DataFrame:
    return pd.read_csv(path)


def verify_reference() -> int:
    """Check every quoted figure is on its cited page; return the number of checks passed."""
    for doc, page, needle, _fields in CHECKS:
        if _normalise(needle) not in page_text(doc, page):
            where = doc.name if page is None else f"{doc.name} page {page}"
            raise ValueError(f"{where} no longer contains {needle!r}")
    return len(CHECKS)


def withholding_rate(fund: str = "ACWD", year: str = "fy2026") -> float:
    """Effective fund-level withholding rate: withholding tax / gross dividend income."""
    ref = fund_documents().query("fund == @fund").set_index("field")["value"]
    return float(ref[f"withholding_tax_{year}"]) / float(ref[f"dividend_income_{year}"])
