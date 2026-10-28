# Decision log

Append an entry whenever a methodology choice is made. Newest at the bottom. Every rule is applied mechanically by the code and cites its evidence; if none has been found yet, write `Evidence: pending` and add it to the brief's Open questions. Rules for a result are written here before that result is computed; anything changed after seeing results is labelled **post-hoc**, with the reason.

---

### 2026-10-28 — Scope
**Context:** Start of the project, the third in a series after `ETF-vehicle-selection` and `Multi-Asset-Allocation`.
**Rule:** Build a goals-based planning tool for an SGD investor, in four phases:
1. Capital market assumptions (CMAs), validated out of sample.
2. A monthly simulation in real SGD.
3. A plain-English app.
4. An independent review.

Each phase ends at a checkpoint for the owner's approval. Asset classes: global equities in SGD (unhedged), SGS, SGD cash; inflation as Singapore CPI. The tool is educational and gives no recommendations.
**Evidence:** Owner's project brief (`docs/brief.md`).
**Alternatives considered:** A single-answer optimiser, rejected because it mechanically selects a corner solution (e.g. the riskiest feasible mix).
**What would change my mind:** The owner widening the scope.

### 2026-10-28 — External CMA benchmarks are non-manager sources only
**Context:** Comparing against published CMAs from asset managers was considered. The brief forbids referencing, naming or imitating any asset manager, robo-advisor or wealth platform, or their materials.
**Rule:** The forward CMAs are compared only with:
- the Philadelphia Fed Survey of Professional Forecasters 10-year expectations
- Damodaran's implied equity risk premium (NYU)
- the historical per-mix returns from `Multi-Asset-Allocation`

Building-block research (Grinold & Kroner 2002; Ibbotson & Chen 2003) is cited as published research for the model's form only, after each citation is verified against the publication.
**Evidence:** Owner's decision, 2026-10-28.
**Alternatives considered:** Named comparison to manager CMAs (rejected by the owner); a private sanity check against them (rejected: numbers that shape the work but can't be shown break the no-unsourced-numbers rule).
**What would change my mind:** The owner amending the brief.

### 2026-10-28 — Reuse of the earlier projects: vendor derived figures at pinned commits
**Context:** The brief asks to reuse the earlier projects' committed, derived outputs, with the commit recorded, and not to copy raw data. Both repos are currently private.
**Rule:** `analysis.upstream` reads only committed derived files at pinned commits:
- `Multi-Asset-Allocation` @ `a92a325`: `reference/etf_costs.csv`, `reference/bond_durations.csv`, `reports/headline_figures.json`, `docs/backtest_results.md`, `docs/strategy_design.md`
- `ETF-vehicle-selection` @ `4103576`: `reports/2026-Q4/ranking.csv`

It writes `reference/upstream/{fund_facts,mix_costs,risk_menu,historical_mix_returns}.csv`, with repo, commit, path and locator on every row. These CSVs are committed, so the build runs offline. `make upstream` refreshes them, reading the public raw URL first and falling back to the signed-in GitHub CLI while the repos are private.

Figures that aren't committed upstream are not recomputed silently. They are listed here and in the brief's Open questions:
- ACWD's fund-level withholding rate
- the risk menu at limits other than −50%, where no mix qualifies upstream

**Evidence:** Owner's brief; the vendored files reconcile (`tests/test_upstream.py`):
- Each all-in cost equals its components within the 0.01 bp upstream rounding (20.48 + 15.01 + 0.88 = 36.37 vs 36.38 for the 88% mix).
- The TER component equals the weighted fund TERs.

**Alternatives considered:** Reading the repos live at build time (rejected: a fresh clone and CI can't reach private repos); copying the earlier projects' raw data (forbidden by the brief).
**What would change my mind:** An upstream correction. In that case, bump the pinned commit and log the change here.

### 2026-10-28 — Equity fund: ACWD, reconciled with ISAC (approved by the owner, 2026-10-28)
**Context:** The two earlier projects use different MSCI ACWI funds:
- `ETF-vehicle-selection` ranks SPDR MSCI All Country World UCITS ETF USD Unhedged (Acc) (ACWD, LSE, ISIN IE00B44Z5B48) first, at an annual holding cost of 0.12%.
- `Multi-Asset-Allocation` builds its mixes with iShares MSCI ACWI UCITS ETF (ISAC, LSE, TER 0.20%). Its decision log gives no reason for preferring ISAC over ACWD.

**Rule:** Use the fund ranked first by `ETF-vehicle-selection`: the equity sleeve holds the fund ranked first for MSCI ACWI in that project's latest committed ranking, currently **ACWD**. The ranking is that project's purpose, and this tool needs no fund price history, which is the main thing a backtest gains from an older fund. No reason for `Multi-Asset-Allocation`'s choice of ISAC was recorded in its decision log (checked at `a92a325`).

**What ACWD's 0.12% is:** in `ranking.csv`, ACWD has:
- `expense_ratio` 0.0012
- `withholding_drag` 0.0
- `annual_holding_cost` 0.0012, the sum of the two

The 0.12% is therefore the TER. The withholding in that file is the tax on distributions paid to a Singapore investor, which is zero for an accumulating Irish fund. Withholding inside the fund isn't modelled there, as `ETF-vehicle-selection`'s README states. Adding a fund-level withholding drag to the TER therefore doesn't count it twice.

Before any cost figure is computed, Phase 1 confirms the TER against ACWD's current factsheet (`ETF-vehicle-selection` cites the SSGA factsheet, status `verified`, checked 2026-10-25).

Costs for any mix with equity weight w are:

all-in bps = w × (ACWD TER + trailing dividend yield × fund-level withholding rate) + (1 − w) × A35 TER + trading bps

Inputs:
- ACWD TER 0.12% (`ETF-vehicle-selection`).
- A35 TER 0.24% and trailing dividend yield 1.42% (`Multi-Asset-Allocation`).
- Fund-level withholding rate: ACWD's effective rate, measured in Phase 1 from its audited annual report (non-reclaimable withholding tax ÷ the dividend income it falls on, at cited pages). The measured rate replaces ISAC's 11.98%. ISAC's rate stays a placeholder only, and is not used in any computed figure.
- Trading bps: taken from `Multi-Asset-Allocation`'s four mixes (ISAC on LSE; ACWD also trades on LSE). They aren't interpolated for other weights; the nearest committed mix is used and disclosed.

`Multi-Asset-Allocation`'s ISAC-based all-in costs are kept as a cross-check, and the app can show both. The forward dividend yield and P/E come from ACWD's dated factsheet. Phase 1 first confirms that the factsheet publishes them. If it doesn't, the owner decides at the Phase 1 checkpoint; nothing is substituted silently.
**Evidence:** `reference/upstream/fund_facts.csv` (ranking and TERs, both `verified` upstream); `reference/upstream/mix_costs.csv`. Evidence: pending for ACWD's fund-level withholding rate and for its factsheet fields.
**Alternatives considered:** ISAC, for consistency with `Multi-Asset-Allocation`'s committed mix costs. It is rejected as the default because it is 0.08% a year dearer on TER with no offsetting benefit for a forward-looking tool.
**What would change my mind:** ACWD's measured withholding rate making its all-in cost higher than ISAC's, or its factsheet lacking the forward inputs while ISAC's has them.

### 2026-10-28 — Forward equity inputs from the fund factsheet; history validates methods only
**Context:** Free primary sources for global dividend yield, valuation and earnings growth are thin. Shiller covers the US, and JST covers its own country panel.
**Rule:**
- Historical data (Shiller US; JST countries) is used only to test each method's out-of-sample forecasting power.
- The forward CMA applies each validated method to current global inputs from the chosen fund's dated, hashed factsheet: dividend yield, and P/E if published.
- The gap is stated in `docs/cma.md` and `docs/limitations.md`: methods validated mainly on US history are applied to global inputs.

**Evidence:** Owner's decision, 2026-10-28.
**Alternatives considered:**
- US inputs as a proxy for global equities: rejected for the forward estimate, because US valuations differ from global ones.
- Hand-entered index factsheet figures: not needed if the fund factsheet carries them.

**What would change my mind:** A free, redistributable primary source of global index yield and valuation history.

### 2026-10-28 — Licence of JST-derived parameters
**Rule:** Any parameter derived from the JST Macrohistory Database is labelled "CC BY-NC-SA 4.0" with the required citation wherever it is shown, including in the app, and the app ships only derived parameters, never JST data.
**Evidence:** JST licence terms (macrohistory.net). The URL and text are to be saved and hashed in Phase 1, as `Multi-Asset-Allocation` did.
**Alternatives considered:** Excluding JST from the app, rejected because it is the main multi-country validation source.
**What would change my mind:** A licence change by the JST authors.

### 2026-10-28 — CMA scenarios: low / central / high, each simulated separately (pre-registered)
**Context:** Each CMA needs a range, and the range must reach the simulation. Ten-year forecast errors already contain the noise of realised returns, which the simulation adds again through the bootstrap.
**Rule:**
- Each asset class's low and high CMA = central ∓ the wider of:
  - (a) the spread across the method variants that have forward inputs (half the max − min of their central estimates), and
  - (b) the bootstrap standard error of the central forecast's mean, from a moving-block bootstrap of the input series. Block length = ceil(n^(1/3)) observations for a series of n observations, 2,000 replications, seed 20261028.
- `docs/cma.md` states, for each asset class, which methods enter (a) and whether (a) or (b) set the width.
- Out-of-sample error percentiles are reported as validation statistics only. They are not used as ranges.
- In Phase 2 each scenario is simulated separately. Scenarios are never drawn at random on top of the bootstrap, because that would count realised-return noise twice.

**Evidence:**
- Moving-block bootstrap: Künsch (1989), *Annals of Statistics*.
- Block-length rate n^(1/3): Hall, Horowitz & Jing (1995), *Biometrika*.

Both are Evidence: pending until verified against the publications in Phase 1.
**Alternatives considered:**
- Ranges from out-of-sample error percentiles: rejected, because they double-count realised noise when combined with the bootstrap.
- Random draws of the mean per path: rejected for the same reason.

**What would change my mind:** Evidence that the method spread and the estimation error together understate parameter uncertainty, for example persistent out-of-sample bias beyond both.

### 2026-10-28 — Fresh-clone rebuild tolerance: 10 bps a year
**Context:** Live sources (Shiller, MAS, FRED) revise and extend their data, so a fresh clone's downloads will differ from the snapshot. Drift is expected and must be reported, not treated as failure.
**Rule:**
- `make all` on a fresh clone passes if drift is reported in `data/processed/drift_report.md` and no headline CMA (central, low or high, at the pinned as-of date) moves by more than **10 bps a year** from the committed `reports/cma_figures.json`.
- A larger move is listed in the drift report and fails `make verify`.
- A missing source file stops the run.

**Evidence:** Judgement, Evidence: pending. The reasoning: 10 bps is the smallest step at which the CMAs are reported (0.1%), so a revision that doesn't change a reported figure passes, and one that does is surfaced for review.
**Alternatives considered:** Exact equality (rejected: live sources always revise); no tolerance (rejected: silent drift).
**What would change my mind:** Routine data revisions moving the CMAs by more than 10 bps, which would suggest the as-of pinning isn't working.

### 2026-10-28 — "Built with Claude Code" section in the README
**Context:** The project template forbids mentioning AI tools in committed files. The owner's brief asks for a README section on AI assistance.
**Rule:** The README has one section headed "Built with Claude Code". There are no attribution lines in commits or pull requests, and no AI mentions elsewhere in the code or docs.
**Evidence:** Owner's decision, 2026-10-28.

### 2026-10-28 — Environment outside iCloud's reach
**Context:** The repo lives in `~/Documents`, which iCloud may sync. Syncing a virtual environment can corrupt it.
**Rule:** The environment is created in `.venv.nosync` (which iCloud skips) and symlinked to `.venv`.
**Evidence:** Template README guidance; owner's decision.

### 2026-10-28 — Phase 1 source and citation checks (before any rule below)
**Context:** Plan step 1: every source and citation is checked against its primary page before code depends on it.
**Findings:**
- **Source checks:** `reference/source_checks.csv`, one row per source.
- **Citations:** `reference/citations.csv`. Eight are verified against Crossref. Grinold & Kroner (2002) is confirmed only by secondary sources and stays `to_verify`, so the building-block form rests on Ibbotson & Chen (2003).
- **ACWD figures:** `reference/fund_documents.csv`, with page references.
- **JST R6 has no earnings variable.** By the owner's rule (2026-10-28), E1–E3 are validated on Shiller US only, and D1 on Shiller US and all 18 JST countries.
- **ACWD's factsheet** (30 September 2026) publishes the TER (0.12%, confirming the upstream ranking), the index dividend yield and a *forward* P/E (FY1, analyst estimates). It publishes no trailing P/E or CAPE, so no forward input exists for E2 or E3.
- **ACWD's fund-level withholding** is computed from the audited FY2026 annual report (page 799; dividend income gross of non-recoverable withholding tax, note 1(j)). It replaces the ISAC stand-in.
- **Licence terms:** SingStat's and the Philadelphia Fed's terms pages gave no usable text, so both are treated as not redistributable. The app shows only figures derived from them, with citation.

### 2026-10-28 — Phase 1 pre-registration: CMA methods, validation and forward inputs (FINAL)
**Context:** Plan step 2. These rules are fixed and committed before any CMA or validation result is computed. Any later change is labelled post-hoc.

The owner approved the draft on 2026-10-28 with these changes, all made before any result was computed:
- (a) The equity central is D1, and E1 is the US-growth variant.
- (b) The forward earnings yield is reported as a sanity check only.
- (c) The MAS Survey of Professional Forecasters is added as a near-term inflation cross-check.
- (d) A public or retail ACWD factsheet was searched for; none was found (see "Forward inputs").

**General**
- **Units.** All CMAs are annualised geometric (compound) *real* returns over 10 years, at index level before fund costs. Fund costs are deducted in the simulation (Phase 2).
- **As-of date: 2026-09-30.** This is the month-end of the latest ACWD factsheet. Every forward input is taken at or before this date.
- **Validation layout.**
  - Origins are annual. For Shiller, the origin is the December value; JST is annual.
  - Each forecast is compared with the realised annualised real return over the next 10 years. The windows overlap.
  - Every parameter a method estimates (growth rates, CAPE anchor, historical mean) uses only data dated at or before the origin, on an expanding window.
  - The first forecast is made after 30 years of data (burn-in).
- **Publication lag (Shiller).** At a December origin, the forecast uses that December's price and the dividends, earnings and CPI as of the previous September (a 3-month lag). Evidence: pending. Shiller interpolates quarterly S&P figures, and the latest months of the file carry no D or E (`reference/source_checks.csv`), so the true lag is at least one quarter.

**Equity methods.** Here *y* is the trailing dividend yield, *g* is real growth, and CAPE is Shiller's P/E10.
- **E1 = y + g_EPS.** g_EPS is the annualised real EPS growth over the expanding window.
- **E2 = E1 + (CAPE_anchor / CAPE_t)^(1/10) − 1.** CAPE_anchor is the expanding-window median CAPE.
- **E3 = 1 / CAPE_t.**
- **D1 = y + g_div.** g_div is the annualised real dividend growth over the expanding window.
  - For JST, the dividend index is built from `eq_dp` × the price index cumulated from `eq_capgain`. Real figures deflate by `cpi`.
  - Validation uses local-currency real returns per country.
- **Where each is validated.** E1–E3 on Shiller US. D1 on Shiller US and on each JST country, also pooled.
- **Forward estimate.**
  - E2 and E3 have no forward input and are **validation-only**: ACWD publishes a forward P/E, which isn't comparable to the CAPE history. Their results are still reported.
  - D1 forward = ACWD index dividend yield + forward g_div.
  - E1 forward = ACWD index dividend yield + forward g_EPS. This is labelled the **US-growth variant**.
  - The equity **central** CMA = **D1 forward**.
  - E1 forward contributes only to the scenario spread: spread (a) = half of |E1 − D1|.
  - **Why E1 isn't central:** its growth term is US EPS growth. Applying US growth to a global index's yield biases the estimate upward, because US real earnings growth is one market's history; the cross-country dividend-growth median isn't tied to any one market.
  - **Sanity check, not used:** the forward earnings yield = 1 / ACWD's P/E FY1 (23.84 at 30 September 2026). It is reported next to the CMA, labelled as based on analyst estimates of next year's earnings. It sets no figure and no range.
- **Forward inputs: factsheet edition.** The cited ACWD factsheet is SSGA's EMEA English edition, marked for professional clients. A public or retail edition was searched for on 2026-10-28 and none was found:
  - The SSGA UK "individual" route redirects to a general investor page.
  - SSGA Singapore lists the fund only on its institutional pages.
  - Guessed retail file names returned HTTP 404.

  The professional edition is cited by figure and page only, never reproduced. If a retail edition appears, it replaces this citation, and the figures are checked to match.
- **Forward real growth term (fixed source and window).**
  - g_EPS = annualised real EPS growth on Shiller US, from the first full year (1871) to the last year with reported earnings before the as-of date.
  - g_div = the median, across the 18 JST countries, of each country's annualised real dividend growth over its full sample (to 2020).
  - Alternative not chosen: real GDP-per-capita growth. It is reported alongside as a check, not used.

**Bond methods (SGS)**
- **B1 forward.** The SGS yield at A35's duration, 8.18 years (vendored), linearly interpolated between the MAS benchmark tenors on the as-of date, minus the inflation CMA.
- **B1 validation.**
  - US: Shiller GS10 at the origin vs the realised 10-year real total bond return (Shiller's bond-return column).
  - JST: `ltrate` at the origin vs the realised annualised `bond_tr`, both deflated by `cpi`.
- **B2 = B1 + rolldown.**
  - Rolldown = (yield at duration − yield at duration − 1 year) × (duration − 1), with the curve from FRED constant-maturity yields (US validation, from 1953 where GS5/GS10 exist).
  - B2 is adopted for the forward SGS CMA only if its US out-of-sample RMSE is lower than B1's over the same origins. Otherwise B1 is used and B2 is reported.

**Cash (SGD)**
- **Start.** The 3-month compounded SORA (MAS) on the as-of date, minus the inflation CMA.
- **Long run.** The average real SGD 3-month interbank rate (MAS, from 1988) over 1988 to the last full year, deflated by SingStat CPI.
- **CMA.** The average of a linear path from the start rate to the long-run rate over 10 years.

**Inflation (Singapore CPI)**
- The annualised SingStat CPI (All Items) inflation over the 30 full calendar years before the as-of date (1996–2025).
- Alternative not chosen: no primary Singapore source publishes a 10-year inflation forecast that could be found. The Philadelphia Fed SPF's CPI10 is US-only and is reported for context only.
- **Near-term cross-check, not the assumption:** the median CPI-All Items forecasts for the current and next calendar year from the latest MAS Survey of Professional Forecasters. MAS publishes them quarterly as an `.xlsx` (the September 2026 file is `sep26q3.xlsx`, available from mas.gov.sg).
  - MAS returns a web page instead of the file to scripted requests, so it is a **manual download**: the owner saves it from a browser, and `make fetch` records it in the manifest with its hash.
  - The figures are shown next to the inflation CMA with the survey date, and set nothing.

**FX (global equity held in SGD, unhedged)**
- The expected real change in SGD against the fund's currency mix is zero (relative PPP).
- Evidence: pending, with Rogoff (1996, *Journal of Economic Literature*) on the slow mean reversion of real exchange rates to be verified before it is cited.

**Validation statistics** (each method, sample and country):
- Bias (mean of forecast − realised), MAE, RMSE, and correlation.
- Out-of-sample R² = 1 − Σ(realised − forecast)² / Σ(realised − historical mean)² (Campbell & Thompson 2008). The historical mean at each origin uses only 10-year windows completed by that origin.
- The 10th and 90th percentiles of errors.
- The HAC (Newey-West, 9 lags) standard error of the bias, and the effective number of independent observations = number of origins / 10.
- Weak, zero or negative results are reported as found (Goyal & Welch 2008). No method is dropped or re-tuned after its results are seen without a post-hoc label.

**Comparison (descriptive only):**
- the forward CMAs
- `Multi-Asset-Allocation`'s historical per-mix real returns (vendored)
- the SPF 2026 Q1 STOCK10, BOND10 and BILL10, made real with the matching CPI10
- Damodaran's latest implied ERP plus the US 10-year yield, made real the same way

**Evidence:** `reference/citations.csv` and `reference/source_checks.csv`. Evidence: pending for:
- the Shiller lag
- Rogoff (1996), which has no DOI in Crossref and needs checking against the journal
- the cash glide-path shape (linear, chosen for simplicity)

**What would change my mind:**
- A primary-source 10-year Singapore inflation forecast.
- A public source of global index earnings history, which would let E1–E3 be validated beyond the US.
- A retail ACWD factsheet whose figures differ from the professional edition.

### 2026-10-28 — Amendments to the Phase 1 pre-registration, made before any result (owner-approved)
**Context:** These issues were found while building the loaders, after the pre-registration was committed (`b0485c6`) and before any CMA or validation result was computed. Each was decided by the owner before validation ran on real data.

**1. JST sample ends in 2015 for every country.**
- **Rule:** JST data after 2015 is excluded from validation and from the forward g_div median.
- **Evidence:** JST's US equity total returns match Shiller's December-to-December returns to within about 0.2 percentage points in every year to 2015. They then diverge in 2016–2020 (2016 −8.1 pp, 2018 +16.0 pp, 2019 −18.0 pp, 2020 −6.0 pp). 2015 is the end of the sample in Jordà et al. (2019).
- **Alternatives:** Using data to 2020 as registered (rejected: known divergence). Dropping only the US extension (rejected: no second source to check the other countries' extension years).

**2. Long-run real cash rate: interbank, then compounded SORA.**
- **Rule:** MAS discontinued the 3-month interbank series on 1 January 2014. The long-run window (1988 to the last full year) uses the month-end 3-month interbank rate for 1988–2013 and the MAS 3-month compounded SORA for 2014 onward, deflated by SingStat CPI.
- **Disclosed difference:** compounded SORA is backward-looking (realised overnight rates over the past 3 months), while the interbank rate was a forward-looking quote.
- **Alternative:** Interbank only, 1988–2013 (rejected: leaves out a full rate cycle).

**3. Bond methods are validated in nominal terms.**
- **Rule:** B1 = the starting yield and B2 = B1 + rolldown, each compared with the realised *nominal* annualised 10-year bond total return. This tests the yield method alone.
- **Forward SGS CMA:** this is unchanged and stays real: the yield minus the inflation CMA.
- **Why:** The registered text compared with real returns but set no inflation forecast at past origins. Adding one would test two assumptions at once.
- **Alternative:** Yield minus trailing 10-year inflation against real returns (rejected for the reason above).

**Implementation notes (fixed before results):**
- JST series with gaps (missing years) are split into contiguous runs. Growth rates, levels and realised returns never span a gap, and the 30-year burn-in restarts with each run.
- For pooled JST statistics, the HAC standard error of the bias and the effective number of observations use the cross-country average error per origin year. Errors from different countries in the same year are therefore not treated as independent.
- B2's rolldown uses FRED December monthly-average GS5 and GS10: rolldown = (GS10 − GS5) / 5 × 9, the one-year roll from 10 to 9 years on a linear 5–10-year curve. It is compared with B1 over the origins where both exist (from 1953).

### 2026-10-28 — Rules for the R² intervals and forward CMAs, fixed before computing them
**Context:** The validation statistics are computed (`a2171db`). The owner asked for bootstrap intervals on each method's out-of-sample R². The forward CMAs need the implementation details below. All are fixed here before either is computed.

**Bootstrap 95% intervals for out-of-sample R²**
- **Method:** moving-block bootstrap over origins, 2,000 replications, seed 20261028, 2.5th–97.5th percentile interval.
- **Block length: 10 origins**, the forecast horizon. Consecutive 10-year windows share up to 9 years, so the errors are dependent at up to 9 lags, and a block of 10 keeps that dependence intact. The n^(1/3) rule used for the scenario standard errors would give blocks of about 5 here, which would cut through that overlap.
- **JST pooled:** blocks of origin years are resampled, and each drawn year keeps every country's error for that year, so cross-country correlation within a year is preserved.
- **Resampling unit:** each replication resamples (forecast, realised, historical mean) triples and recomputes R² = 1 − SSE(forecast) / SSE(historical mean).

**Forward CMA inputs**
- **Inflation:** Dec 1995 to Dec 2025 SingStat CPI All Items, (CPI_Dec2025 / CPI_Dec1995)^(1/30) − 1.
- **D1 growth (g_div):**
  - For each JST country, the annualised real dividend growth over its contiguous run of data ending in 2015. Growth never spans a gap.
  - g_div is the median across the countries with such a run of at least 30 years.
- **E1 growth (g_EPS):** Shiller real EPS (E / CPI, monthly) from January 1871 to the last month with reported earnings, annualised by elapsed months / 12.
- **GDP check (reported, not used):** the median across JST countries of annualised real GDP per capita growth (`rgdpmad`), 1870 to 2015.
- **SGS yield:** the yield at 8.18 years, linearly interpolated between the 5-year and 10-year MAS benchmark yields on 2026-09-30.
- **Cash:**
  - Long-run real rate = the mean over 1988–2025 of each year's average month-end 3-month rate (interbank to 2013, then compounded SORA), minus that year's Dec-to-Dec CPI inflation.
  - Start rate = the 3-month compounded SORA at the end of September 2026, minus the inflation CMA.
  - CMA = the midpoint of the start and long-run rates, which is the average of a linear 10-year path between them.

**Scenario standard errors (rule (b)):** n^(1/3) blocks as registered, 2,000 replications, seed 20261028.
- **Equity:** resample each country's annual real dividend growth rates within its run, then recompute the cross-country median. The yield is observed and adds no error.
- **Inflation:** resample the 30 annual inflation rates.
- **SGS:** the inflation CMA's standard error (the yield is observed).
- **Cash:** resample the annual real rates and the inflation series independently, then recompute the midpoint.

**Scenario spread (rule (a)):**
- **Equity:** half of |E1 − D1|.
- **SGS:** half of |B2 − B1|. B2 is a registered variant with forward inputs; the adoption rule decides only the central estimate, and B1 stays central because B2 lost on RMSE.
- **Cash and inflation:** 0 (one method each).

**Comparison:**
- The SPF 2026 Q1 STOCK10, BOND10 and BILL10, each minus the CPI10 median in the same survey.
- Damodaran's latest year: implied ERP (FCFE) + T.Bond rate, minus the same CPI10.
- `Multi-Asset-Allocation`'s per-mix figures: the 0% and 100% equity rows.

**MAS citations:**
- MAS datasets (rates, SGS yields, the survey workbook) carry MAS's prescribed notice: "Contains information from {dataset} accessed on {date}, which is made available under the terms of the Monetary Authority of Singapore's Terms of Use of Datasets."
- MAS's terms page (updated 27 August 2026) asks for permission before linking to internal pages. Documents cite MAS sources by title and file name; whether to hyperlink is an owner decision.

### 2026-10-28 — Bias review: amendment, correction and post-hoc sensitivities (logged before re-running)
**Context:** `/bias-check` on the first full Phase 1 build. The owner chose the fixes below on 2026-10-28. The first build's figures are superseded by the re-run; they were not committed.

**Amendment 4 (registered rule changed before re-running): the equity bootstrap resamples calendar years jointly.**
- **Rule:** the bootstrap standard error of g_div resamples the same moving blocks of calendar years for every country, so common shocks (wars, 1970s inflation) move all countries together.
  - Block length: ceil(n^(1/3)), where n is the number of distinct years across the countries' runs.
  - A drawn year that lies outside a country's run contributes nothing for that country.
  - Each country's annualised growth is recomputed from its drawn years, then the cross-country median is taken.
- **Why:** the first build resampled countries independently. That treats correlated countries as independent and understates the standard error.

**Correction (a bug, not a method change): Shiller bond-return timing.**
- Shiller's "Monthly Total Bond Returns" in row *t* is the return from month *t* to *t*+1. This was reverse-engineered on 2026-10-28: it matches a 10-year par bond with semi-annual coupons repriced at the next month's GS10, with correlation 0.99999 and a mean absolute gap of 0.57 bp a month.
- The first build treated row *t* as the return into month *t*, so each bond window ran January to January instead of December to December. No future data entered any forecast.
- **Fix:** shift the column one month so row *t* is the return into *t*.
- **Same finding, for the record:** the US realised bond returns are *computed from the GS10 yield series* itself. The US bond validation is therefore partly circular, and `docs/cma.md` says so.

**Brief §14 aligned with the approved scenario rule.** Failed validation tests are reported as found. They don't widen the scenarios: the ranges cover uncertainty in the expected return only, and the spread of realised outcomes comes from the simulation.

**Post-hoc sensitivities (labelled post-hoc wherever shown; the central estimates don't change):**
- **P1, g_div from each country's longest run.** Each country's longest contiguous run of at least 30 years ending by 2015 replaces the run ending in 2015. This brings back countries whose latest run is short (bias-check #2).
- **P2, bias-corrected D1.** Forward D1 minus D1's pooled JST out-of-sample bias (bias = forecast − realised, so a negative bias raises the figure).
- **Context only:** S&P 500 gross buyback yield from Damodaran's dividends-plus-buybacks series. It is gross, not net of share issuance; no free, citable net series was found.

**Disclosures added to `docs/cma.md` and `docs/limitations.md`:**
- D1's forward input is the dividend yield only, excluding buybacks. This probably biases the forward equity CMA downward. That is consistent with the negative validation bias of D1, E1 and E2 (E3's bias was positive).
- Country selection for g_div (survivors; developed markets only).
- Revised Shiller data, with the 3-month lag Evidence: pending.
- The ranges describe the expected return, not outcomes.
- The real SGD/USD change in three windows, as evidence for zero real FX change.
- `Multi-Asset-Allocation`'s historical figures use JST data to 2020.

**Carried to Phase 2:** the SGS real return uses the Fisher approximation (nominal yield − inflation). The bootstrap must be re-centred so the *geometric* mean matches each CMA.

**Correction (a coding error against the registered rule): zero-dividend years.** The first build dropped any country whose run ending in 2015 contained a zero-dividend year. That excluded Germany (unbroken run 1870–2015, 2 zero years) and Spain (1900–2015, 3 zero years). The registered rule needs annualised growth between the run's endpoints, which needs positive values only at the start and end.
- **Fix:** a run is used when its first and last values are positive.
- **Bootstrap:** year-on-year changes into or out of a zero dividend are undefined and are dropped from the resampled rates.
- **Record:** an earlier message said Germany, Spain and Portugal were excluded for gaps. Only Portugal (runs 1871–1987 and 2005–2015) is excluded for that reason.

### 2026-10-28 — Phase 1 approved; MAS citations; Phase 3 requirement
**MAS citations:** MAS sources are cited by title with "available from mas.gov.sg", without hyperlinks, per MAS's terms (updated 27 August 2026), which ask for permission before linking to internal pages.
- Datasets also carry MAS's prescribed Terms of Use notice.
- Download URLs stay in the code and in `data/MANIFEST.yaml` / `reference/source_checks.csv` as provenance records. These are rendered as plain text, not links.

**Phase 3 requirement (owner, 2026-10-28):**
- **Default view:** the app's assumption switcher shows three sets side by side: the central CMAs, the bias-corrected equity estimate (P2) and the historical averages. One line says why they differ.
- **Headline:** the headline output (probability of reaching the goal) must not rest on the central assumptions alone.
