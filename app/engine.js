// Goals Planner browser engine: the Phase 2 Student-t engine, costs, SRS and summaries.
// Rules: docs/decisions.md (2026-10-28, Phase 2 and Phase 3 pre-registrations). Plain script,
// no dependencies; runs in the browser and in the Python test suite (quickjs).
//
// Wealth is linear in contributions once each order's cost is known:
//   W_T = I_T * (W_0 + sum_t (a_t - cost(a_t)) / I_t)
// where I_t is the net portfolio index. So one pass over the random draws stores, per path,
// the year-end index and the yearly sums of 1/I_t; every contribution level, the solver, the
// fan chart and SRS withdrawals then follow without redrawing.
(function (root) {
  "use strict";

  // --- random numbers: splitmix32 seeding, xoshiro128** generator ---

  function splitmix32(a) {
    return function () {
      a = (a + 0x9e3779b9) | 0;
      let z = a;
      z = Math.imul(z ^ (z >>> 16), 0x85ebca6b);
      z = Math.imul(z ^ (z >>> 13), 0xc2b2ae35);
      return (z ^ (z >>> 16)) >>> 0;
    };
  }

  function xoshiro128ss(seed) {
    const sm = splitmix32(seed);
    let a = sm(), b = sm(), c = sm(), d = sm();
    return function () {
      const t = b << 9;
      let r = Math.imul(b, 5);
      r = Math.imul((r << 7) | (r >>> 25), 9);
      c ^= a; d ^= b; b ^= c; a ^= d; c ^= t;
      d = (d << 11) | (d >>> 21);
      return (r >>> 0) / 4294967296;
    };
  }

  function makeNormal(uniform) {
    let spare = null;
    return function () {
      if (spare !== null) { const s = spare; spare = null; return s; }
      let u = 0;
      while (u === 0) u = uniform();
      const v = uniform();
      const r = Math.sqrt(-2 * Math.log(u));
      spare = r * Math.sin(2 * Math.PI * v);
      return r * Math.cos(2 * Math.PI * v);
    };
  }

  // Marsaglia-Tsang gamma(shape, 1); chi-square(df) = 2 * gamma(df / 2).
  function gamma(shape, uniform, normal) {
    if (shape < 1) return gamma(shape + 1, uniform, normal) * Math.pow(uniform(), 1 / shape);
    const d = shape - 1 / 3, c = 1 / Math.sqrt(9 * d);
    for (;;) {
      let x, v;
      do { x = normal(); v = 1 + c * x; } while (v <= 0);
      v = v * v * v;
      const u = uniform();
      if (u < 1 - 0.0331 * x * x * x * x) return d * v;
      if (Math.log(u) < 0.5 * x * x + d * (1 - v + Math.log(v))) return d * v;
    }
  }

  function pathRng(seed, path) {
    return xoshiro128ss((seed ^ Math.imul(path + 1, 0x9e3779b1)) | 0);
  }

  // --- costs (Phase 2 section 5) ---

  function nearestMix(share, mixes) {
    let best = null;
    for (const m of mixes) {
      const key = [Math.round(Math.abs(m - share) * 1e10) / 1e10, m];
      if (best === null || key[0] < best[0] || (key[0] === best[0] && key[1] < best[1])) best = key;
    }
    return best[1];
  }

  function annualCost(share, costs) {
    const mixes = Object.keys(costs.mix_trading_bps).map(Number);
    const equity = costs.acwd_ter + costs.acwd_dividend_yield * costs.acwd_withholding;
    const trading = costs.mix_trading_bps[String(nearestMix(share, mixes))] / 1e4;
    return share * equity + (1 - share) * costs.a35_ter + trading;
  }

  function feeRow(rows, component, market) {
    return rows.find((r) => r.component === component && r.market === market);
  }
  function feeRate(rows, component, provider) {
    return rows.find((r) => r.component === component && r.provider === provider).rate;
  }

  function orderCost(amountSgd, share, costs) {
    if (!(amountSgd > 0)) return 0;
    const s = costs.fee_schedule;
    const gst = feeRow(s, "gst", "SG").rate;
    const usdPerSgd = feeRate(s, "usd_per_unit", "SGD");
    const usdPerGbp = feeRate(s, "usd_per_unit", "GBP");
    let total = 0;
    const equityUsd = amountSgd * share * usdPerSgd;
    if (equityUsd > 0) {
      const fx = feeRow(s, "fx_conversion", "FX");
      const commission = feeRow(s, "commission", "LSE");
      const levy = feeRow(s, "ptm_levy", "LSE");
      let cost = Math.max(equityUsd * fx.rate, fx.minimum);
      cost += Math.max(equityUsd * commission.rate, commission.minimum) * (1 + gst);
      if (equityUsd / usdPerGbp >= levy.min_trade_value) cost += levy.rate * usdPerGbp;
      cost += (equityUsd * feeRate(s, "spread", "ACWD (LSE)")) / 2;
      total += cost / usdPerSgd;
    }
    const bond = amountSgd * (1 - share);
    if (bond > 0) {
      let sgx = 0;
      for (const component of ["commission", "platform_fee", "clearing_fee", "trading_access_fee"]) {
        const row = feeRow(s, component, "SGX");
        sgx += Math.max(bond * row.rate, row.minimum === null ? 0 : row.minimum);
      }
      total += sgx * (1 + gst) + (bond * feeRate(s, "spread", "A35 (SGX)")) / 2;
    }
    return total;
  }

  // --- SRS (Phase 2 section 8; statutory age is an input, Phase 3) ---

  function residentTax(income, bands) {
    let tax = 0;
    for (const b of bands) {
      const top = b.band_to === null ? Infinity : b.band_to;
      tax += Math.min(Math.max(income - b.band_from, 0), top - b.band_from) * b.rate;
    }
    return tax;
  }

  function srsCap(srs, rules) {
    return srs.citizenOrPr ? rules.contribution_cap_citizen_pr : rules.contribution_cap_foreigner;
  }

  // Contribution per month, by year, after the SRS cap and with relief reinvested a year later.
  function yearlyAmounts(plan, srs, rules) {
    let monthly = plan.monthly, growth = plan.growth;
    if (srs) {
      const capMonthly = srsCap(srs, rules) / 12;
      if (monthly * Math.pow(1 + growth, plan.years) > capMonthly) growth = 0;
      monthly = Math.min(monthly, capMonthly);
    }
    const base = [], amounts = [];
    for (let y = 0; y < plan.years; y++) base.push(monthly * Math.pow(1 + growth, y));
    for (let y = 0; y < plan.years; y++) {
      const relief = srs && y > 0 ? Math.min(base[y - 1], srsCap(srs, rules) / 12) * srs.marginalRate : 0;
      amounts.push(base[y] + relief);
    }
    return { amounts, base };
  }

  // --- the random pass ---

  // Returns, per assumption set, Float64Arrays: index at each year end (paths x (Y+1)), yearly
  // sums of 1/I_t for monthly and quarterly purchases (paths x years), and max drawdown.
  function drawPaths(P, setKeys, share, years, extraYears, paths, seed) {
    const t = P.student_t, df = t.df, sc = t.scale;
    const l11 = Math.sqrt(sc[0][0]), l21 = sc[1][0] / l11, l22 = Math.sqrt(sc[1][1] - l21 * l21);
    const cf = Math.pow(1 - annualCost(share, P.costs), 1 / 12);
    const totalYears = years + extraYears, months = 12 * totalYears;
    const sets = setKeys.map((k) => ({
      key: k,
      locEq: Math.log1p(P.sets[k].equity) / 12,
      locSgs: Math.log1p(P.sets[k].sgs) / 12,
      ye: new Float64Array(paths * (totalYears + 1)),
      r: new Float64Array(paths * years),
      rq: new Float64Array(paths * years),
      dd: new Float64Array(paths),
    }));
    const I = new Float64Array(sets.length), peak = new Float64Array(sets.length);
    for (let p = 0; p < paths; p++) {
      const uniform = pathRng(seed, p), normal = makeNormal(uniform);
      for (let s = 0; s < sets.length; s++) {
        I[s] = 1; peak[s] = 1;
        sets[s].ye[p * (totalYears + 1)] = 1;
      }
      for (let m = 1; m <= months; m++) {
        const n1 = normal(), n2 = normal();
        const scale = 1 / Math.sqrt((2 * gamma(df / 2, uniform, normal)) / df);
        const e1 = l11 * n1 * scale, e2 = (l21 * n1 + l22 * n2) * scale;
        const y = Math.floor((m - 1) / 12), inHorizon = m <= 12 * years;
        for (let s = 0; s < sets.length; s++) {
          const st = sets[s];
          const gross = share * Math.expm1(st.locEq + e1) + (1 - share) * Math.expm1(st.locSgs + e2);
          I[s] *= (1 + gross) * cf;
          if (inHorizon) {
            st.r[p * years + y] += 1 / I[s];
            if (m % 3 === 0) st.rq[p * years + y] += 1 / I[s];
            if (I[s] > peak[s]) peak[s] = I[s];
            const fall = I[s] / peak[s] - 1;
            if (fall < st.dd[p]) st.dd[p] = fall;
          }
          if (m % 12 === 0) st.ye[p * (totalYears + 1) + m / 12] = I[s];
        }
      }
    }
    const out = {};
    for (const st of sets) out[st.key] = { ye: st.ye, r: st.r, rq: st.rq, dd: st.dd, paths, years, totalYears };
    return out;
  }

  // --- wealth from the stored sums ---

  function cashMonthly(P, key) { return Math.pow(1 + P.sets[key].cash, 1 / 12) - 1; }

  // Investable amount per year after trading costs, and the matching yearly sums.
  function yearlyInvested(P, key, plan, srs) {
    const { amounts } = yearlyAmounts(plan, srs, P.srs);
    const quarterly = plan.batching === "quarterly";
    const c = cashMonthly(P, key), qf = (1 + c) * (1 + c) + (1 + c) + 1;
    return amounts.map((a) => {
      const order = quarterly ? a * qf : a;
      return order - (order > 0 ? orderCost(order, plan.equity, P.costs) : 0);
    });
  }

  // D is the result of drawPaths (all sets); key picks the assumption set.
  function wealthAtYear(D, P, key, plan, srs, Y) {
    const d = D[key];
    const invested = yearlyInvested(P, key, plan, srs);
    const w0 = plan.initial - (plan.initial > 0 ? orderCost(plan.initial, plan.equity, P.costs) : 0);
    const sums = plan.batching === "quarterly" ? d.rq : d.r;
    const out = new Float64Array(d.paths);
    for (let p = 0; p < d.paths; p++) {
      let acc = w0;
      for (let y = 0; y < Y; y++) acc += invested[y] * sums[p * d.years + y];
      out[p] = d.ye[p * (d.totalYears + 1) + Y] * acc;
    }
    return out;
  }

  function terminal(D, P, key, plan, srs) { return wealthAtYear(D, P, key, plan, srs, plan.years); }

  function pGoal(wealth, goal) {
    let n = 0;
    for (let i = 0; i < wealth.length; i++) if (wealth[i] >= goal) n++;
    return n / wealth.length;
  }

  function percentile(sorted, q) {
    const pos = (sorted.length - 1) * (q / 100), lo = Math.floor(pos), hi = Math.ceil(pos);
    return sorted[lo] + (sorted[hi] - sorted[lo]) * (pos - lo);
  }
  function sortedCopy(x) { return Float64Array.from(x).sort(); }

  function requiredMonthly(D, P, key, plan, goal, probability, step, ceiling) {
    step = step || 10; ceiling = ceiling || 100000;
    const ok = (m) => pGoal(terminal(D, P, key, Object.assign({}, plan, { monthly: m }), null), goal) >= probability;
    if (ok(0)) return 0;
    if (!ok(ceiling)) return null;
    let lo = 0, hi = Math.round(ceiling / step);
    while (hi - lo > 1) {
      const mid = Math.floor((lo + hi) / 2);
      if (ok(mid * step)) hi = mid; else lo = mid;
    }
    return hi * step;
  }

  function fan(D, P, key, plan, srs, qs) {
    const rows = [];
    for (let Y = 0; Y <= plan.years; Y++) {
      const s = sortedCopy(wealthAtYear(D, P, key, plan, srs, Y));
      const row = { year: Y };
      for (const q of qs) row[q] = percentile(s, q);
      rows.push(row);
    }
    return rows;
  }

  function worstDecileMedian(D, P, key, plan, srs) {
    const end = terminal(D, P, key, plan, srs);
    const cut = percentile(sortedCopy(end), 10);
    const idx = [];
    for (let p = 0; p < end.length; p++) if (end[p] <= cut) idx.push(p);
    const out = [];
    for (let Y = 0; Y <= plan.years; Y++) {
      const w = wealthAtYear(D, P, key, plan, srs, Y);
      out.push(percentile(Float64Array.from(idx.map((p) => w[p])).sort(), 50));
    }
    return out;
  }

  function cashPath(P, key, plan) {
    const r = cashMonthly(P, key);
    const out = [plan.initial];
    let w = plan.initial;
    for (let y = 0; y < plan.years; y++) {
      const a = plan.monthly * Math.pow(1 + plan.growth, y);
      for (let m = 0; m < 12; m++) w = w * (1 + r) + a;
      out.push(w);
    }
    return out;
  }

  function srsPremature(srs, years) { return srs.age + years < srs.statutoryAge; }

  // After-tax withdrawals (balance stays invested, balance / years remaining each year).
  // D here is one set's draws (drawPaths(...)[key]).
  function withdraw(D, balance, srs, rules, taxed, years) {
    const n = rules.withdrawal_years, out = new Float64Array(D.paths), tax = new Float64Array(D.paths);
    for (let p = 0; p < D.paths; p++) {
      let b = balance[p];
      for (let k = 0; k < n; k++) {
        const tranche = b / (n - k);
        const owed = taxed
          ? residentTax(rules.taxable_share * tranche + srs.otherIncome, rules.tax_bands) - residentTax(srs.otherIncome, rules.tax_bands)
          : 0;
        out[p] += tranche - owed;
        tax[p] += owed;
        if (k < n - 1) {
          const base = p * (D.totalYears + 1) + years + k;
          b = (b - tranche) * (D.ye[base + 1] / D.ye[base]);
        }
      }
    }
    return { afterTax: out, tax };
  }

  function srsOutcome(D, P, key, plan, srs) {
    const rules = P.srs, cappedPlan = Object.assign({}, plan);
    const withSrs = terminal(D, P, key, cappedPlan, srs);
    const noRelief = Object.assign({}, srs, { marginalRate: 0 });
    const without = terminal(D, P, key, cappedPlan, noRelief);
    let srsNet, plainNet, tax;
    if (srsPremature(srs, plan.years)) {
      const keep = 1 - rules.taxable_share_premature * srs.marginalRate - rules.premature_penalty;
      srsNet = withSrs.map((x) => x * keep);
      plainNet = without;
      tax = withSrs.map((x, i) => x - srsNet[i]);
    } else {
      const a = withdraw(D[key], withSrs, srs, rules, true, plan.years);
      const b = withdraw(D[key], without, srs, rules, false, plan.years);
      srsNet = a.afterTax; plainNet = b.afterTax; tax = a.tax;
    }
    let ahead = 0;
    for (let i = 0; i < srsNet.length; i++) if (srsNet[i] > plainNet[i]) ahead++;
    return {
      premature: srsPremature(srs, plan.years),
      pGoal: pGoal(withSrs, plan.goal),
      medianSrs: percentile(sortedCopy(srsNet), 50),
      medianPlain: percentile(sortedCopy(plainNet), 50),
      medianTax: percentile(sortedCopy(tax), 50),
      aheadShare: ahead / srsNet.length,
    };
  }

  root.GoalsEngine = {
    xoshiro128ss, makeNormal, gamma, nearestMix, annualCost, orderCost, residentTax,
    yearlyAmounts, drawPaths, terminal, wealthAtYear, pGoal, percentile, sortedCopy,
    requiredMonthly, fan, worstDecileMedian, cashPath, srsPremature, withdraw, srsOutcome,
  };
})(typeof window !== "undefined" ? window : globalThis);
