// Test helpers for tests/test_app_engine.py (loaded into quickjs after params.js and engine.js).
(function (root) {
  "use strict";
  const P0 = root.GOALS_PARAMS;

  // Every fee and fund cost set to zero (FX rates kept), so only returns remain.
  function costFree() {
    const P = JSON.parse(JSON.stringify(P0));
    for (const k of Object.keys(P.costs.mix_trading_bps)) P.costs.mix_trading_bps[k] = 0;
    P.costs.acwd_ter = 0;
    P.costs.a35_ter = 0;
    P.costs.acwd_withholding = 0;
    for (const row of P.costs.fee_schedule) {
      if (row.component !== "usd_per_unit" && row.rate !== null) row.rate = 0;
      if (row.minimum !== null) row.minimum = 0;
    }
    return P;
  }

  // Terminal wealth with a (numerically) zero scale matrix: every month earns ln(1 + r) / 12.
  function zeroVolTerminal(rAnnual, years, initial, monthly) {
    const P = costFree();
    P.student_t.scale = [[1e-300, 0], [0, 1e-300]];
    P.sets = { x: { equity: rAnnual, sgs: rAnnual, cash: 0 } };
    const D = root.GoalsEngine.drawPaths(P, ["x"], 0.6, years, 0, 3, 1);
    const plan = { initial, monthly, growth: 0, years, equity: 0.6, batching: "monthly" };
    return Array.from(root.GoalsEngine.terminal(D, P, "x", plan, null));
  }

  // Chance of reaching a preset example's goal under the central set.
  function presetChance(example, paths) {
    const ex = P0.presets[example];
    const plan = {
      initial: ex.initial, monthly: ex.monthly, growth: ex.growth,
      years: ex.years, equity: ex.equity, batching: "monthly",
    };
    const D = root.GoalsEngine.drawPaths(P0, ["central"], ex.equity, ex.years, 0, paths, P0.seed);
    return root.GoalsEngine.pGoal(root.GoalsEngine.terminal(D, P0, "central", plan, null), ex.goal);
  }

  root.TestHelpers = { zeroVolTerminal, presetChance };
})(globalThis);
