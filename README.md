# Goals Planner (SGD)

> **One line:** an educational calculator for the chance of reaching a savings goal in Singapore dollars. It shows several reasonable return assumptions side by side, because that choice moves the answer far more than anything else.

![CI](https://github.com/azrinmahsuom/Goals-Planner/actions/workflows/ci.yml/badge.svg)

## Summary

| | |
|---|---|
| **Question** | If I invest S$X now and S$Y a month in a mix of global shares and Singapore government bonds, how likely am I to reach S$G (in today's money) by year T? How much would I need to save each month for a chosen likelihood? |
| **What it does** | Builds return assumptions from their parts (yields, growth, valuation), tests how well each method would have forecast the past, then simulates 10,000 possible futures in real SGD after fund and trading costs |
| **Assets** | Global equities held in SGD (unhedged), Singapore Government Securities, SGD cash; inflation as Singapore CPI |
| **App** | **[azrinmahsuom.github.io/Goals-Planner](https://azrinmahsuom.github.io/Goals-Planner/)**: a static page from [`app/`](app/); it also opens locally from `app/index.html` |
| **Status** | Complete: built, independently reviewed, review findings addressed ([docs/decisions.md](docs/decisions.md)), published |

## Key findings

As of 30 September 2026; real (after inflation), annualised over 10 years.

1. **Starting bond yields predicted the next 10 years' bond returns closely** (out-of-sample R² 0.91 in the US, 0.78 across 16 countries). This is mostly arithmetic rather than skill: a bond held for about its duration earns close to its starting yield. ([docs/cma.md](docs/cma.md))
2. **The equity methods did little better than the long-run average** (R² 0.004 across 16 countries). The best US method, 1/CAPE, can't be applied going forward with free data. ([docs/cma.md](docs/cma.md))
3. **So the answer depends mostly on the equity assumption.** The four example investors' chances of reaching their goals, under each assumption set:

   | Example | Central (2.4% equities) | Bias-corrected equity | Historical equity + yield-based bonds* | Historical global (reference) |
   |---|---|---|---|---|
   | A: age 30, S$800/month, 25 years | 16% | 24% | 60% | 63% |
   | B: age 45, S$150,000 + S$1,500/month, 15 years | 23% | 31% | 61% | 76% |
   | C: age 55, S$400,000, 10 years | 41% | 47% | 69% | 85% |
   | D: age 40, S$1,275/month, 24 years (without SRS) | 40% | 49% | 80% | 88% |

   Across the three plausible sets, the chance moves by 28–44 percentage points. Different simulation engines move it by 3–9 points. ([docs/simulation.md](docs/simulation.md))

\*Added after the Phase 2 results were seen; labelled post-hoc. The central equity figure leaves out buybacks and is probably too low.

## Limitations

The main ones, in full in [docs/limitations.md](docs/limitations.md):

- The equity methods show little forecasting power.
- The historical figures come from developed markets that came through their crises.
- The simulation's ups and downs come from 1998–2026 history.
- SRS and fees are simplified.
- Behaviour and taxes outside SRS aren't modelled.

## Reproduce it

You need [uv](https://docs.astral.sh/uv/) (it installs Python) and git.

```bash
git clone https://github.com/azrinmahsuom/Goals-Planner.git
cd Goals-Planner
uv sync --locked   # the pinned environment
make all           # download, verify, rebuild every output and the app's parameters, run the tests (about 8 minutes)
```

- **Changed sources:** a source that changed since the recorded snapshot is listed in `data/processed/drift_report.md` and the run continues. The run stops if a file is missing, or if a headline assumption or chance moves beyond its tolerance.
- **Optional manual step:** MAS's Survey of Professional Forecasters workbook can't be downloaded by script. To include the inflation cross-check, save it from mas.gov.sg as `data/raw/documents/Sep26Q3.xlsx`.
- **Browser tests** run if Playwright's browser is installed (`uv run playwright install chromium`).
- **iCloud:** on macOS, keep the project outside iCloud-synced folders, or put the environment in a folder iCloud skips: `uv venv .venv.nosync && ln -s .venv.nosync .venv && uv sync --locked`.

## Repository layout

```
├── app/               The planner: a static page that ships parameters only, no data series
├── data/              MANIFEST.yaml (committed): URL, date, licence and hash of every source; the data itself is git-ignored
├── docs/              Brief, decision log, return assumptions, simulation, app guide, limitations
├── reference/         Hand-researched inputs with sources; upstream/ holds figures reused from the earlier projects, with commit
├── reports/           The numbers behind every document, and the figures
├── src/analysis/      Code: sources, manifest, return assumptions, simulation, app parameters
└── tests/             Tests, including the browser engine checked against the Python engine
```

## Earlier projects reused

Fund costs, withholding-tax drag, the trading fee schedule, the risk-menu mixes and historical per-mix returns come from two earlier projects, read at fixed commits and stored in `reference/upstream/` with their source on every row:

- [`ETF-vehicle-selection`](https://github.com/azrinmahsuom/ETF-vehicle-selection) @ `4103576`
- [`Multi-Asset-Allocation`](https://github.com/azrinmahsuom/Multi-Asset-Allocation) @ `a92a325` (checked unchanged at `5fbf585`)

## Sources and licences

Every source is checked against its primary page and recorded in `data/MANIFEST.yaml`, with notes in `reference/source_checks.csv`.

- **Code:** MIT.
- **JST data:** figures derived from the Jordà-Schularick-Taylor Macrohistory Database are licensed CC BY-NC-SA 4.0. See [LICENSE](LICENSE) for the data terms.
- **No raw data is redistributed.**
- **MAS:** contains information from MAS statistics and the MAS Survey of Professional Forecasters (available from mas.gov.sg), made available under the terms of the Monetary Authority of Singapore's Terms of Use of Datasets.

## Built with Claude Code

This project was built with Claude Code, an AI coding assistant, working under the rules in [docs/decisions.md](docs/decisions.md): every method written down before its results, every number generated by code or cited, and an independent review before publishing. The research questions, judgements and final decisions are the author's.

## Disclaimer

A personal educational project; not affiliated with any financial institution; not financial advice. It is built on publicly available data and doesn't represent the views of any employer. Projections are uncertain, past returns are an imperfect guide, and fee schedules are used as cost data, not as broker recommendations.
