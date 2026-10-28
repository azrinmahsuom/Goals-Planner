# Project brief

Filled in at the start of the project and read before every task. Update it whenever the scope changes, and log why in `docs/decisions.md`.

## 1. Name
Goals-Planner

## 2. Type
Tool. The capital market assumptions (CMAs) are rebuilt by hand when the sources are refreshed; the planner runs on demand in an app.

## 3. Goal
Give a Singapore-dollar (SGD) investor a plain-English answer to: "If I invest S$X now and S$Y a month, in mix Z, what is the probability of reaching S$G (in today's money) by year T? What monthly saving would I need for a given probability?"

The answers rest on forward-looking CMAs built from components (yields, growth, valuation), each tested out of sample against history before it is used, and projected with realistic uncertainty: fat tails, sequence risk and inflation.

It is the third project in a series, after `ETF-vehicle-selection` (which fund to hold) and `Multi-Asset-Allocation` (which equity/bond mix), and reuses their committed, derived outputs.

## 4. Audience
General readers and retail investors in Singapore using the app, and anyone checking the method on GitHub. The tool is educational: it gives no recommendations, and the app and README carry a disclaimer.

## 5. Hypothesis (research only)
Not applicable (Tool). The CMA validation in Phase 1 is still run as a test with pre-registered rules (`docs/decisions.md`); see §14 for what would show a method doesn't work.

## 6. Universe, period, frequency, currency
- Universe: three asset classes and inflation:
  - global equities held in SGD, unhedged, through one Irish-domiciled MSCI ACWI fund (choice in `docs/decisions.md`)
  - Singapore Government Securities (SGS) at the duration of the SGS fund used in `Multi-Asset-Allocation`
  - SGD cash
  - Singapore CPI inflation
- Period:
  - Validation history: Shiller US data (from 1871), and the Jordà-Schularick-Taylor (JST) Macrohistory Database from 1870 to 2015. JST years after 2015 are excluded (`docs/decisions.md`, amendment 1).
  - Forward CMAs: as of 2026-09-30 (`src/analysis/cma/__init__.py`).
  - Projection horizons: user-chosen.
- Frequency: monthly simulation; annual and monthly history for validation.
- Currency: real SGD (after Singapore CPI) · Returns: total (income reinvested), after all-in fund costs.

## 7. Benchmark
The CMAs are compared against:
- the historical per-mix real returns from `Multi-Asset-Allocation` (JST, vendored in `reference/upstream/historical_mix_returns.csv`)
- the Philadelphia Fed Survey of Professional Forecasters 10-year expectations
- Damodaran's implied equity risk premium

Each CMA method is validated against the historical-mean forecast (out-of-sample R²). No asset manager's, robo-advisor's or wealth platform's CMAs or materials are referenced.

## 8. Data and sources
One source per line, with whether results derived from it can be published. Every URL, series ID and licence was checked against the primary page on 2026-10-28 (`reference/source_checks.csv`). The MAS Survey of Professional Forecasters workbook (near-term inflation cross-check) is a manual browser download.

| Data | Source | Script | Pulled on | Publishable? |
|---|---|---|---|---|
| US prices, dividends, earnings, CPI, CAPE (validation) | Robert Shiller, online data | `analysis.sources.shiller` | 2026-10-28 | To confirm in Phase 1; app ships derived parameters only |
| Multi-country returns, yields, CPI (validation) | JST Macrohistory Database R6 | `analysis.sources.jst` | 2026-10-28 | Derived parameters, CC BY-NC-SA 4.0 with citation |
| USD/SGD, US CPI, US 10-year yield | FRED | `analysis.sources.fred` | 2026-10-28 | Public-domain series yes (checked per series) |
| SGS benchmark yields, SORA | MAS | `analysis.sources.mas` | 2026-10-28 | To confirm in Phase 1 |
| Singapore CPI | SingStat | `analysis.sources.singstat` | 2026-10-28 | Licence to confirm (open question) |
| 10-year stock, bond and bill expectations | Philadelphia Fed SPF | `analysis.sources.spf` | 2026-10-28 | To confirm in Phase 1 |
| Implied equity risk premium | Damodaran (NYU) | `analysis.sources.damodaran` | 2026-10-28 | No licence stated; treat as not redistributable |
| Equity fund dividend yield, P/E (forward inputs) | Fund factsheet (dated, hashed) | `analysis.sources.documents` | 2026-10-28 | Cite figures only |
| SRS caps, relief, withdrawal tax (Phase 2) | IRAS, MOF, CPF Board pages | `analysis.sources` (saved pages) | | Cite rules only |
| Fund costs, withholding, risk menu, historical mix returns | `Multi-Asset-Allocation` @ a92a325, `ETF-vehicle-selection` @ 4103576 | `analysis.upstream` | 2026-10-28 | Yes (derived, committed upstream); JST-derived rows CC BY-NC-SA 4.0 |

## 9. Processing steps
1. `make fetch`: download every source into `data/raw/`, recording each in `data/MANIFEST.yaml`.
2. `make verify`: re-hash the files. Changed files go to `data/processed/drift_report.md`; a missing file stops the run.
3. CMA stage (Phase 1): build each pre-registered method, validate it out of sample, and set low/central/high scenarios by the pre-registered rule.
4. Report stage: write `reports/cma_figures.json` and figures, and render `docs/cma.md` from them.
5. Simulation (Phase 2) and app (Phase 3) read only the generated figures and licence-compliant parameters.

## 10. Outputs
- `docs/cma.md`: assumptions, validation and scenarios
- `docs/simulation.md`
- `docs/app_guide.md`
- `docs/limitations.md`
- `reports/cma_figures.json` and `reports/figures/*.png`
- An interactive app (host decided in Phase 3, deployed only with the owner's approval)
- README with a one-screen summary

## 11. Run cadence (tool only)
By hand, when the owner refreshes the sources (`make refresh`, then `make all`). The app recomputes projections on demand from the committed CMAs.

## 12. Limits, assumptions and things to avoid
Each threshold or default cites its evidence, or says `Evidence: pending` (and is listed under Open questions).
- **No unsourced numbers.** Every figure is computed by code from manifest-recorded data, or cited with page or table.
- **Rules before results:** methods, parameters and comparison rules go in `docs/decisions.md` before their results are computed; later changes are labelled post-hoc.
- **No corner-solution decision rules:** the tool presents trade-offs and ranges; the user chooses.
- **Not advice:** no "you should" language.
- **Transaction costs and fees:** all-in cost per mix from the vendored fund and mix costs (`reference/upstream/`), using the rule in `docs/decisions.md` (2026-10-28); no flat fallback.
- **Risk-free rate:** 3M SORA (MAS), used as the cash CMA's starting point.
- **Fresh-clone tolerance:** 10 bps a year on any headline CMA, decision of 2026-10-28.
- **Global equity inputs** come from one fund's factsheet, while the methods are validated mainly on US history: a disclosed gap.
- **No asset-manager CMAs** or materials. The building-block literature is cited as published research only.

## 13. How we know the code is correct
- The zero-volatility simulation matches the annuity formula exactly (Phase 2).
- A fixed seed reproduces results exactly, and costs reduce returns by exactly the stated amount.
- Building-block arithmetic is checked by hand on small examples.
- The validator recovers out-of-sample R² ≈ 1 on a synthetic series it should predict, and ≈ 0 on noise.
- No look-ahead: perturbing future data leaves past forecasts unchanged.
- Vendored upstream costs reconcile: components sum to the all-in figure, and the TER component equals the weighted fund TERs.
- Every number in `docs/cma.md` appears in `reports/cma_figures.json`.

## 14. What would show the hypothesis is wrong
For each CMA method: out-of-sample R² at or below zero against the historical mean, or forecast errors with a bias larger than their spread. Such results are reported as found and methods are not quietly dropped. They do not widen the scenarios: the low/central/high ranges cover uncertainty in the expected return only (method spread or estimation error, `docs/decisions.md`), and the spread of realised outcomes comes from the simulation.

## 15. Open questions
- **Prior repos are private.** The owner will make `ETF-vehicle-selection` and `Multi-Asset-Allocation` public; until then `analysis.upstream` reads them through the signed-in GitHub CLI.
- **MAS Survey of Professional Forecasters workbook:** the owner saves it by hand. Its CPI medians are then added to `docs/cma.md` as a cross-check.
- **Linking to MAS pages:** MAS's terms (updated 27 August 2026) ask for permission before hyperlinking to internal pages. Documents cite MAS sources by title for now.
- **SingStat and Philadelphia Fed licence terms:** not confirmed; only derived or cited figures are shown.
- **Evidence still pending:** the Shiller 3-month publication lag; Rogoff (1996); Grinold & Kroner (2002) primary source; the linear cash glide path.
- **Multi-Asset-Allocation's Shiller bond-return timing** probably has the same one-month offset corrected here (`docs/decisions.md`, 2026-10-28); to raise in that repo.
- **Hedging:** the equity sleeve is unhedged in SGD. A hedged variant is out of scope unless requested.
- **App host** (Streamlit Community Cloud vs a static GitHub Pages site): Phase 3.
