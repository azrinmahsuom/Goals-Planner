# Limitations

A living list, completed in Phase 4. Each item says what it affects. The numbers behind them are in `docs/cma.md`.

## Capital market assumptions (model risk)
- **Equity methods predict little.** Dividend yield plus real dividend growth (D1, the equity central) did no better than the historical average across 16 JST countries. The best US predictor (1/CAPE) can't be used going forward, because no free source publishes a global CAPE. The equity central should be read as one reasonable estimate, not a forecast with demonstrated skill.
- **Buybacks are left out.** The forward equity estimate uses the dividend yield only. Share buybacks also return cash to shareholders, so the equity central is probably biased downward. This is consistent with the negative validation bias of D1, E1 and E2. It is disclosed and shown as a post-hoc sensitivity, not corrected.
- **The countries behind dividend growth are a selected sample.** They are developed markets with long continuous data: markets that came through their crises. JST has no emerging markets, while the fund holds some.
- **US data are revised.** Shiller's file is today's revised history, and the 3-month publication lag is a judgement (Evidence: pending). This affects the US validation only.
- **Bond validation is partly circular.** Shiller's US bond returns are computed from the same yield series used as the forecast. With duration close to the 10-year horizon, the starting yield matching the realised return is largely arithmetic.
- **Global inputs, mainly US-validated methods.** The equity methods are validated on US history and JST's developed markets, but applied to one global fund's factsheet inputs.
- **The ranges are for the expected return, not outcomes.** A single 10-year outcome has historically missed its forecast by several percentage points a year. The simulation (Phase 2) provides the spread of outcomes.
- **Zero real currency change is an assumption.** Measured real SGD changes against the USD range from slightly negative to about +0.9% a year depending on the window, and the fund holds many currencies.
- **Regime dependence.** TBD (Phase 4).

## Inputs reused from earlier projects
- **Trading costs** for mixes other than the four committed in `Multi-Asset-Allocation` aren't interpolated; the nearest committed mix is used.
- **Historical comparison figures** from `Multi-Asset-Allocation` use JST data to 2020, including years this project excludes.

## Simplifications
- **Taxes, fees and behaviour:** TBD (Phase 2 and Phase 4).
- **SRS module:** simplified and optional (Phase 2).

## What a real planning tool would add
TBD (Phase 4).
