# Limitations

A living list, completed in Phase 4. Each limitation says what it affects and, where possible, how large the effect is.

## Capital market assumptions (model risk)
- **Global inputs, US-validated methods.** The equity methods are validated mainly on US history (Shiller) and the JST country panel, but applied to one global fund's factsheet inputs. Out-of-sample performance on US data need not carry over to a global index.
- **Weak predictability is expected.** Valuation and yield signals have historically had limited out-of-sample power over some horizons and samples. Each method's results are reported as found in `docs/cma.md` (Phase 1).
- **Regime dependence.** TBD (Phase 4).

## Inputs reused from earlier projects
- **ACWD's fund-level withholding rate** isn't committed in either earlier project; Phase 1 measures it from ACWD's audited annual report (`docs/decisions.md`, 2026-10-28).
- **Trading costs** for mixes other than the four committed in `Multi-Asset-Allocation` aren't interpolated; the nearest committed mix is used.

## Simplifications
- **Taxes, fees and behaviour:** TBD (Phase 2 and Phase 4).
- **SRS module:** simplified and optional (Phase 2).

## What a real planning tool would add
TBD (Phase 4).
