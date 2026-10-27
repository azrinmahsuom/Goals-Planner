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
