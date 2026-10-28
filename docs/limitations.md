# Limitations

What each limitation affects, and where the figures behind it are (`docs/cma.md`, `docs/simulation.md`).

## Model risk in the return assumptions
- **The equity methods predict little.** Dividend yield plus real dividend growth (the equity central) did no better than the historical average across JST countries. The best US predictor (1/CAPE) can't be used going forward, because no free source publishes a global CAPE. Treat the equity central as one reasonable estimate, not a forecast with demonstrated skill. That is why the headline shows several assumption sets side by side.
- **Buybacks are left out.** The forward equity estimate uses the dividend yield only. Share buybacks also return cash, so the central is probably too low. This is consistent with the negative validation bias of three of the four equity methods. It is shown as a post-hoc bias-corrected set, not corrected in the central.
- **The forward estimate isn't exactly the validated form.** Validation used each country's own expanding-window dividend growth; the forward estimate uses the cross-country median over full runs.
- **Selected samples.** The dividend-growth input and the historical equity figure both come from developed markets with long, continuous data: markets that came through their crises. They probably overstate what a randomly chosen market would have delivered. JST has no emerging markets, while the fund holds some.
- **Revised data.** Shiller's file is today's revised history, and the 3-month publication lag is a judgement. This affects the US validation only.
- **Bond validation is partly circular.** Shiller's US bond returns are computed from the same yield series used as the forecast, and with duration close to the 10-year horizon a good fit is largely arithmetic.
- **Ranges describe the expected return, not outcomes.** The spread of outcomes comes from the simulation.
- **Currency.** Zero real change in SGD is assumed. Measured real changes against the USD vary with the window, and the fund holds many currencies.

## Regime dependence
- **The simulation's ups and downs come from 1998–2026.** That window includes two deep equity falls and a long decline in yields, then a sharp rise. The US long-run history (from 1871) and a fat-tailed model are sensitivities. A future with a different pattern (long stagnation, high inflation, a lasting change in how shares and bonds move together) is not represented beyond what these histories contain.
- **Starting yields matter more than history for bonds.** If yields jump or collapse, the bond assumptions change at the next rebuild. The assumptions are dated (as of 30 September 2026) and aren't updated automatically.
- **Each assumption set is held for the whole horizon.** Real returns don't settle on one long-run figure; the low–high range and the side-by-side sets are the only treatment of that uncertainty.

## Simplifications: taxes, fees, behaviour
- **Taxes outside SRS** aren't modelled, beyond the withholding tax inside the equity fund, which is included as a cost. IRAS states that foreign-sourced income received by individuals is generally not taxable (verified in `Multi-Asset-Allocation`); personal circumstances can differ.
- **SRS is simplified:**
  - The S$80,000 overall relief cap is assumed not to bind.
  - Today's tax brackets are held constant in real terms.
  - Relief is invested outside SRS a year after each contribution.
  - Withdrawals are equal shares of the balance over 10 years.
  - The comparison doesn't value losing access before the statutory retirement age.
  - The statutory age is an input, because it's fixed at the first contribution.
- **Fees** are one broker pair's published schedules, used as cost data. Minimum fees are held constant in today's money. The equity fund's spread is a default, not measured. There is no platform or custody fee, and no SGD-to-USD conversion markup beyond the broker's stated charge.
- **Rebalancing** is monthly in the simulation, with a yearly rebalancing cost taken from the earlier project's mixes.
- **Behaviour** isn't modelled: no stopped contributions after a fall, no selling at the bottom, no changes in saving, income or goals.

## Inputs reused from earlier projects
- **Trading costs** for mixes other than the four committed in `Multi-Asset-Allocation` aren't interpolated; the nearest committed mix is used.
- **Historical comparison figures** from `Multi-Asset-Allocation` use JST data to 2020, including years this project excludes.

## The app
- **It runs a simplified engine** (fat-tailed, months independent). For the four examples its chances were mostly a little lower than the main engine's; the page shows the measured gap.
- **Everything is in today's money and before tax outside SRS.** The goal date is the only date that matters to the result; spending during or after the horizon isn't modelled.

## What a real planning tool would add
- Your whole balance sheet: CPF, property, insurance, existing holdings, debts, and spending in retirement, not just one goal.
- Cash flows that change over time: career income, breaks, lump sums, drawdown in retirement and longevity risk.
- Personal tax, and the CPF interactions with SRS and voluntary contributions.
- Regular updating as yields and valuations move, and stress tests chosen with you.
- Regulated, personal advice that weighs your circumstances, which this educational page doesn't provide.

*Education, not advice. A personal educational project; not affiliated with any financial institution; not financial advice.*
