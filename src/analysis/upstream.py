"""Vendor derived figures from the earlier projects into reference/upstream/.

Only committed, derived outputs are read (fund costs, withholding drag, the risk menu, per-mix
costs and the historical per-mix real returns), each at a pinned commit, and every row keeps
the repo, commit, path and locator it came from. No raw data is copied.

Refresh with `make upstream`; the build itself reads only the committed CSVs, so it runs offline.
"""

import io
import json
import re
import subprocess

import pandas as pd
import requests

from analysis.config import UPSTREAM

OWNER = "azrinmahsuom"
MAA = "Multi-Asset-Allocation"
EVS = "ETF-vehicle-selection"
COMMITS = {
    MAA: "a92a32588501face1813dc2adeb2ceca542593ec",
    EVS: "4103576234dadb1b17aa0cec863124c3c24332cd",
}
PROVENANCE = ["repo", "commit", "path", "locator"]
# Later commits checked: every vendored field re-extracted and found identical, so the tables
# keep their original commit (docs/decisions.md, 2026-10-28).
CHECKED = {MAA: [("5fbf585eee0d26ce9e8299d610d25331f43e5855", "2026-10-28", "identical")]}


def read_file(repo: str, path: str) -> str:
    """Text of one file at the pinned commit: public raw URL first, then the signed-in gh CLI
    (needed while the repo is private)."""
    commit = COMMITS[repo]
    url = f"https://raw.githubusercontent.com/{OWNER}/{repo}/{commit}/{path}"
    response = requests.get(url, timeout=60)
    if response.ok:
        return response.text
    result = subprocess.run(
        [
            "gh",
            "api",
            "-H",
            "Accept: application/vnd.github.raw",
            f"repos/{OWNER}/{repo}/contents/{path}?ref={commit}",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Could not read {repo}/{path} at {commit[:7]}: {result.stderr}")
    return result.stdout


def percent(text: str) -> float:
    """'59.0%' -> 0.59 (rounded to drop float noise from the division)."""
    return round(float(text.strip().rstrip("%")) / 100, 10)


def markdown_tables(text: str, header_contains: str) -> list[pd.DataFrame]:
    """Every markdown table whose header row contains header_contains, as string DataFrames
    (first column renamed 'label')."""
    tables, lines = [], text.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("|") and header_contains in line:
            header = [c.strip() for c in line.strip().strip("|").split("|")]
            header[0] = "label"
            rows = []
            for row in lines[i + 2 :]:
                if not row.startswith("|"):
                    break
                rows.append([c.strip() for c in row.strip().strip("|").split("|")])
            tables.append(pd.DataFrame(rows, columns=header))
    return tables


def _row(repo: str, path: str, locator: str, **values) -> dict:
    return {**values, "repo": repo, "commit": COMMITS[repo][:7], "path": path, "locator": locator}


def fund_facts(
    etf_costs_csv: str,
    headline_json: str,
    backtest_md: str,
    bond_durations_csv: str,
    ranking_csv: str,
) -> pd.DataFrame:
    """Per-fund figures: TER, withholding, dividend yield, duration, all-in holding cost."""
    rows = []
    costs = pd.read_csv(io.StringIO(etf_costs_csv))
    for _, r in costs.iterrows():
        rows.append(
            _row(
                MAA,
                "reference/etf_costs.csv",
                f"ticker={r['ticker']}",
                field="ter",
                ticker=r["ticker"],
                value=float(r["ter"]),
                unit="decimal a year",
                status=r["status"],
            )
        )
    key = "ISAC effective withholding rate"
    rows.append(
        _row(
            MAA,
            "reports/headline_figures.json",
            key,
            field="effective_withholding_rate",
            ticker="ISAC.L",
            value=float(json.loads(headline_json)[key]),
            unit="decimal of dividends",
            status="derived",
        )
    )
    match = re.search(r"trailing dividend yield ([\d.]+)%", backtest_md)
    if not match:
        raise ValueError("Dividend yield sentence not found in backtest_results.md")
    rows.append(
        _row(
            MAA,
            "docs/backtest_results.md",
            "Implementation table note: 'trailing dividend yield'",
            field="trailing_dividend_yield",
            ticker="ISAC.L",
            value=percent(match.group(1)),
            unit="decimal a year",
            status="derived",
        )
    )
    durations = pd.read_csv(io.StringIO(bond_durations_csv))
    for _, r in durations.iterrows():
        rows.append(
            _row(
                MAA,
                "reference/bond_durations.csv",
                f"share_class={r['share_class']}",
                field="effective_duration",
                ticker=r["share_class"].split(" ")[0],
                value=float(r["effective_duration_years"]),
                unit="years",
                status=r["status"],
            )
        )
    ranking = pd.read_csv(io.StringIO(ranking_csv))
    ranked_equity = ranking[(ranking["sleeve"] == "equity") & ranking["rank"].notna()]
    for _, r in ranked_equity.iterrows():
        for field in ("expense_ratio", "withholding_drag", "annual_holding_cost", "rank"):
            rows.append(
                _row(
                    EVS,
                    "reports/2026-Q4/ranking.csv",
                    f"sleeve=equity, ticker={r['ticker']}, exchange={r['exchange']}",
                    field=field,
                    ticker=f"{r['ticker']} ({r['exchange']})",  # ACWI trades on two exchanges
                    value=round(float(r[field]), 10),
                    unit="rank" if field == "rank" else "decimal a year",
                    status=r["status"],
                )
            )
    return pd.DataFrame(rows)


def mix_costs(backtest_md: str) -> pd.DataFrame:
    """All-in annual cost of each committed menu mix, by component, in bps."""
    (table,) = markdown_tables(backtest_md, "all_in_annual_bps")
    numeric = ["ter_bps", "wht_drag_bps", "trading_bps", "all_in_annual_bps"]
    numeric.append("one_off_purchase_bps")
    rows = []
    for _, r in table.iterrows():
        rows.append(
            _row(
                MAA,
                "docs/backtest_results.md",
                f"Implementation table, row '{r['label']}'",
                mix=r["label"],
                basis=r["basis"],
                equity_share=percent(r["ISAC.L_weight"]),
                **{c: float(r[c]) for c in numeric},
            )
        )
    return pd.DataFrame(rows)


def risk_menu(headline_json: str) -> pd.DataFrame:
    """Equity share per horizon and drawdown limit; -1 upstream means no mix qualifies."""
    rows = []
    pattern = re.compile(r"menu (short|medium|long) (-\d+)%: equity share")
    for key, value in json.loads(headline_json).items():
        if match := pattern.fullmatch(key):
            rows.append(
                _row(
                    MAA,
                    "reports/headline_figures.json",
                    key,
                    horizon=match.group(1),
                    drawdown_limit=int(match.group(2)) / 100,
                    equity_share=None if value == -1 else float(value),
                    feasible=value != -1,
                )
            )
    return pd.DataFrame(rows)


def historical_mix_returns(strategy_md: str) -> pd.DataFrame:
    """Long-run JST real return per mix (identical across the three horizon frontiers)."""
    tables = markdown_tables(strategy_md, "| mix | expected_real_return")
    if not tables:
        raise ValueError("No frontier table found in strategy_design.md")
    first = tables[0][["label", "expected_real_return"]]
    for other in tables[1:]:
        if not other[["label", "expected_real_return"]].equals(first):
            raise ValueError("Frontier expected returns differ across horizons; check upstream")
    rows = []
    for _, r in first.iterrows():
        rows.append(
            _row(
                MAA,
                "docs/strategy_design.md",
                f"Frontier table, row '{r['label']}'",
                equity_share=percent(r["label"].split(" ")[0]),
                expected_real_return=percent(r["expected_real_return"]),
                licence="CC BY-NC-SA 4.0 (derived from the JST Macrohistory Database)",
            )
        )
    return pd.DataFrame(rows)


FEE_ROWS = {  # (component, provider) rows of Multi-Asset-Allocation's trading_costs.csv used here
    ("commission", "IBKR (LSE, USD-denominated, Fixed)"),
    ("ptm_levy", "LSE levies"),
    ("gst", "Singapore GST"),
    ("commission", "moomoo SG (SGX)"),
    ("platform_fee", "moomoo SG (SGX)"),
    ("clearing_fee", "SGX exchange fees"),
    ("trading_access_fee", "SGX exchange fees"),
}
FEE_COLUMNS = ["component", "provider", "market", "rate", "per", "minimum", "currency"]
FEE_COLUMNS += ["min_trade_value", "gst", "status"]


def fee_schedule(
    trading_costs_csv: str,
    broker_fees_csv: str,
    spread_snapshot_csv: str,
    ranking_csv: str,
    fx_rates_csv: str,
) -> pd.DataFrame:
    """Per-order fee rows, spreads and FX rates for the contribution cost model."""
    rows = []
    costs = pd.read_csv(io.StringIO(trading_costs_csv))
    for _, r in costs.iterrows():
        if (r["component"], r["provider_or_instrument"]) in FEE_ROWS:
            values = {c: r[c] for c in FEE_COLUMNS if c in r} | {
                "provider": r["provider_or_instrument"]
            }
            rows.append(
                _row(
                    MAA,
                    "reference/trading_costs.csv",
                    f"{r['component']}: {values['provider']}",
                    **values,
                )
            )
    broker = pd.read_csv(io.StringIO(broker_fees_csv))
    fx = broker[(broker["broker"] == "IBKR") & (broker["market"] == "FX")].iloc[0]
    rows.append(
        _row(
            EVS,
            "reference/broker_fees.csv",
            "IBKR Pro Tiered FX",
            component="fx_conversion",
            provider="IBKR (SGD to USD)",
            market="FX",
            rate=float(fx["rate"]),
            per="trade_value",
            minimum=float(fx["minimum"]),
            currency=fx["currency"],
            gst="no",
            status=fx["status"],
        )
    )
    snap = pd.read_csv(io.StringIO(spread_snapshot_csv)).set_index("ticker").loc["A35.SI"]
    mid = (snap["bid"] + snap["ask"]) / 2
    rows.append(
        _row(
            MAA,
            "reference/spread_snapshot.csv",
            f"A35.SI bid {snap['bid']} ask {snap['ask']} at {snap['quote_time']}",
            component="spread",
            provider="A35 (SGX)",
            market="SGX",
            rate=round((snap["ask"] - snap["bid"]) / mid, 10),
            per="trade_value",
            currency="SGD",
            status=snap["status"],
        )
    )
    ranking = pd.read_csv(io.StringIO(ranking_csv))
    acwd = ranking[ranking["ticker"] == "ACWD"].iloc[0]
    rows.append(
        _row(
            EVS,
            "reports/2026-Q4/ranking.csv",
            f"ACWD spread (spread_source = {acwd['spread_source']})",
            component="spread",
            provider="ACWD (LSE)",
            market="LSE",
            rate=float(acwd["spread"]),
            per="trade_value",
            currency="USD",
            status="default, not measured",
        )
    )
    fx_rates = pd.read_csv(io.StringIO(fx_rates_csv))
    for _, r in fx_rates[fx_rates["currency"].isin(["GBP", "SGD"])].iterrows():
        rows.append(
            _row(
                MAA,
                "reference/fx_rates.csv",
                f"{r['currency']} as of {r['as_of']}",
                component="usd_per_unit",
                provider=r["currency"],
                rate=float(r["usd_per_unit"]),
                currency="USD",
                status=r["status"],
            )
        )
    return pd.DataFrame(rows)


def refresh() -> dict[str, int]:
    """Read the pinned upstream files and rewrite reference/upstream/*.csv."""
    headline = read_file(MAA, "reports/headline_figures.json")
    backtest = read_file(MAA, "docs/backtest_results.md")
    tables = {
        "fund_facts": fund_facts(
            read_file(MAA, "reference/etf_costs.csv"),
            headline,
            backtest,
            read_file(MAA, "reference/bond_durations.csv"),
            read_file(EVS, "reports/2026-Q4/ranking.csv"),
        ),
        "mix_costs": mix_costs(backtest),
        "risk_menu": risk_menu(headline),
        "historical_mix_returns": historical_mix_returns(read_file(MAA, "docs/strategy_design.md")),
        "fee_schedule": fee_schedule(
            read_file(MAA, "reference/trading_costs.csv"),
            read_file(EVS, "reference/broker_fees.csv"),
            read_file(MAA, "reference/spread_snapshot.csv"),
            read_file(EVS, "reports/2026-Q4/ranking.csv"),
            read_file(MAA, "reference/fx_rates.csv"),
        ),
    }
    UPSTREAM.mkdir(parents=True, exist_ok=True)
    for name, df in tables.items():
        df.to_csv(UPSTREAM / f"{name}.csv", index=False)
    return {name: len(df) for name, df in tables.items()}


def load(name: str) -> pd.DataFrame:
    """One vendored table from reference/upstream/."""
    path = UPSTREAM / f"{name}.csv"
    if not path.exists():
        raise FileNotFoundError(f"{path} not found. Run `make upstream`.")
    return pd.read_csv(path)
