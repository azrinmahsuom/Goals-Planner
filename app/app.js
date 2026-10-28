// Goals Planner page: inputs, recalculation, headline, charts and sources. Every number shown
// comes from params.js (generated from the project's committed outputs) or from the engine.
(function () {
  "use strict";
  const P = JSON.parse(JSON.stringify(window.GOALS_PARAMS));
  P.sets.low = Object.assign({}, P.central_range.low);
  P.sets.high = Object.assign({}, P.central_range.high);
  const E = window.GoalsEngine;
  const SHOWN = ["central", "P2", "hist_eq_yield", "historical"];
  const RUN = ["central", "low", "high", "P2", "hist_eq_yield", "historical"];
  const ACCENT = { central: "var(--series-1)", P2: "var(--series-2)", hist_eq_yield: "var(--series-3)", historical: "var(--series-4)" };
  const FAN_QS = [5, 25, 50, 75, 95];
  const $ = (id) => document.getElementById(id);

  const state = { chartSet: "central", draws: null, drawKey: "", preset: null };

  // --- formatting ---
  const pct = (x, dp = 0) => `${(x * 100).toFixed(dp)}%`;
  const pts = (x, dp = 1) => `${(x * 100).toFixed(dp)}`;
  const sgd = (x) => (x === null || x === undefined ? "not reachable" : "S$" + Math.round(x).toLocaleString("en-SG"));
  const sgdK = (x) => "S$" + Math.round(x / 1000).toLocaleString("en-SG") + "k";
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

  // --- inputs ---
  function readPlan() {
    const num = (id) => Number($(id).value);
    return {
      initial: Math.max(0, num("initial")),
      monthly: Math.max(0, num("monthly")),
      growth: Math.max(0, num("growth")) / 100,
      years: Math.min(40, Math.max(1, Math.round(num("years")))),
      goal: Math.max(1, num("goal")),
      equity: num("equity") / 100,
      batching: document.querySelector('input[name="batching"]:checked').value,
    };
  }
  function readSrs() {
    if (!$("srs-on").checked) return null;
    return {
      age: Number($("age").value),
      citizenOrPr: $("residency").value === "citizen",
      marginalRate: Number($("rate").value) / 100,
      otherIncome: Math.max(0, Number($("other-income").value)),
      statutoryAge: Number($("sra").value),
    };
  }

  function setInputs(ex) {
    $("initial").value = ex.initial;
    $("monthly").value = ex.monthly;
    $("growth").value = (ex.growth * 100).toFixed(1).replace(/\.0$/, "");
    $("years").value = ex.years;
    $("goal").value = ex.goal;
    $("equity").value = Math.round(ex.equity * 100);
    $("srs-on").checked = ex.srs;
    if (ex.srs) {
      $("age").value = ex.age;
      $("residency").value = "citizen";
      $("rate").value = 11.5;
      $("other-income").value = 0;
      $("sra").value = String(P.srs.statutory_retirement_age_default);
    }
  }

  function matchingPreset(plan, srs) {
    for (const [k, ex] of Object.entries(P.presets)) {
      const same =
        plan.initial === ex.initial && plan.monthly === ex.monthly && Math.abs(plan.growth - ex.growth) < 1e-9 &&
        plan.years === ex.years && plan.goal === ex.goal && Math.abs(plan.equity - ex.equity) < 1e-9 &&
        plan.batching === "monthly" && Boolean(srs) === false;
      if (same) return k;
    }
    return null;
  }

  function buildControls() {
    const presets = $("preset-buttons");
    for (const k of Object.keys(P.presets)) {
      const b = document.createElement("button");
      b.type = "button"; b.className = "chip"; b.textContent = `Example ${k}`;
      b.setAttribute("aria-pressed", "false");
      b.addEventListener("click", () => { setInputs(P.presets[k]); syncOutputs(); schedule(); });
      presets.appendChild(b);
    }
    const mixes = $("mix-buttons");
    for (const m of P.risk_menu_mixes) {
      const b = document.createElement("button");
      b.type = "button"; b.className = "chip"; b.textContent = pct(m);
      b.addEventListener("click", () => { $("equity").value = Math.round(m * 100); syncOutputs(); schedule(); });
      mixes.appendChild(b);
    }
    const sra = $("sra");
    for (const a of P.srs.statutory_retirement_age_options) {
      const o = document.createElement("option");
      o.value = String(a); o.textContent = String(a);
      sra.appendChild(o);
    }
    sra.value = String(P.srs.statutory_retirement_age_default);
    $("sra-note").textContent =
      `${P.srs.statutory_retirement_age_default} if your first SRS contribution is on or after 1 July 2026. ` +
      "The age is fixed at your first contribution, so it may be earlier for an existing account; check with your SRS operator.";
    const sw = $("set-switch");
    for (const k of SHOWN) {
      const b = document.createElement("button");
      b.type = "button"; b.className = "chip"; b.setAttribute("role", "radio");
      b.dataset.set = k; b.textContent = P.sets[k].label;
      b.addEventListener("click", () => { state.chartSet = k; render(); });
      sw.appendChild(b);
    }
    document.querySelectorAll("#inputs input, #inputs select").forEach((el) =>
      el.addEventListener("input", () => { syncOutputs(); schedule(); }));
    $("srs-on").addEventListener("change", () => { syncOutputs(); schedule(); });
    const fill = { paths: P.paths.toLocaleString("en-SG"), penalty: pct(P.srs.premature_penalty), "relief-cap": sgd(P.srs.relief_cap) };
    document.querySelectorAll("[data-param]").forEach((el) => { el.textContent = fill[el.dataset.param]; });
  }

  function syncOutputs() {
    $("equity-out").textContent = `${$("equity").value}%`;
    $("target-out").textContent = `${$("target").value}%`;
    $("target-label").textContent = `a ${$("target").value}%`;
    $("srs-fields").hidden = !$("srs-on").checked;
    const plan = readPlan(), srs = readSrs();
    state.preset = matchingPreset(plan, srs);
    document.querySelectorAll("#preset-buttons .chip").forEach((b) =>
      b.setAttribute("aria-pressed", String(b.textContent === `Example ${state.preset}`)));
    document.querySelectorAll("#mix-buttons .chip").forEach((b) =>
      b.setAttribute("aria-pressed", String(b.textContent === `${$("equity").value}%`)));
  }

  // --- recalculation ---
  let timer = null;
  function schedule() {
    clearTimeout(timer);
    $("results").setAttribute("aria-busy", "true");
    $("status").textContent = "Calculating…";
    timer = setTimeout(recalc, 250);
  }

  function recalc() {
    const plan = readPlan(), srs = readSrs();
    const extra = srs ? P.srs.withdrawal_years : 0;
    const key = [plan.years, plan.equity, extra].join("|");
    if (key !== state.drawKey) {
      state.draws = E.drawPaths(P, RUN, plan.equity, plan.years, extra, P.paths, P.seed);
      state.drawKey = key;
    }
    state.plan = plan; state.srs = srs;
    state.results = {};
    for (const k of RUN) {
      const w = E.terminal(state.draws, P, k, plan, srs);
      state.results[k] = { p: E.pGoal(w, plan.goal) };
    }
    const target = Number($("target").value) / 100;
    for (const k of SHOWN) state.results[k].required = E.requiredMonthly(state.draws, P, k, plan, plan.goal, target);
    render();
    $("results").setAttribute("aria-busy", "false");
    $("status").textContent = `${P.paths.toLocaleString("en-SG")} simulated futures per assumption set, after fund and trading costs, in today's money.`;
  }

  // --- rendering ---
  function render() {
    const plan = state.plan, r = state.results;
    if (!plan) return;
    const preset = state.preset ? P.presets[state.preset] : null;
    $("headline").innerHTML = SHOWN.map((k) => {
      const s = P.sets[k];
      const range = k === "central" ? `<p class="sub">Low–high assumptions: ${pct(r.low.p)}–${pct(r.high.p)}</p>` : "";
      const full = preset
        ? `<p class="sub">Full engine: ${pct(preset.full_engine[k])} (simplified engine ${pts(Math.abs(preset.gap[k]))} points ${preset.gap[k] < 0 ? "lower" : "higher"})</p>`
        : "";
      return `<div class="card${s.plausible ? "" : " reference"}" style="--accent:${ACCENT[k]}">
        <p class="label">${esc(s.label)}${s.plausible ? "" : " (reference)"}</p>
        <p class="value">${pct(r[k].p)}</p>${range}${full}
        <p class="sub">${esc(s.note)}</p></div>`;
    }).join("");

    const plausible = SHOWN.filter((k) => P.sets[k].plausible).map((k) => r[k].p);
    const spread = Math.max(...plausible) - Math.min(...plausible);
    const all = SHOWN.map((k) => r[k].p);
    const noise = Math.max(...all.map((p) => Math.sqrt((p * (1 - p)) / P.paths)));
    $("spread").innerHTML =
      `<strong>There is no single answer.</strong> Assumption choice moves the result far more than the engine or market randomness: ` +
      `across the three plausible assumption sets the chance differs by ${pts(spread, 0)} percentage points, against ` +
      `${P.engine_spread.min.toFixed(0)}–${P.engine_spread.max.toFixed(0)} points across ${P.engine_spread.engines} simulation engines in the project's tests ` +
      `and about ±${pts(noise)} points of sampling noise. The reference set (long-run global history for bonds too) gives ${pct(r.historical.p)}.`;
    const g = P.engine_gap;
    $("engine-note").textContent = preset
      ? `These results use a simplified engine (Student-t, each month drawn independently). Example ${state.preset} matches a project example, so the full engine's result (resampled history) is shown on each card with the measured gap.`
      : `Simplified engine (Student-t, each month drawn independently). For the project's four examples, its chances were between ${pts(g.min)} and +${pts(g.max)} points of the full engine's (lower in ${g.lower_count} of ${g.count} cases).`;

    $("required").innerHTML = SHOWN.map((k) =>
      `<div class="card${P.sets[k].plausible ? "" : " reference"}" style="--accent:${ACCENT[k]}"><p class="label">${esc(P.sets[k].label)}</p><p class="value">${sgd(r[k].required)}</p><p class="sub">a month</p></div>`
    ).join("");

    document.querySelectorAll("#set-switch .chip").forEach((b) => b.setAttribute("aria-checked", String(b.dataset.set === state.chartSet)));
    $("set-note").textContent = `${P.sets[state.chartSet].label}: ${P.sets[state.chartSet].note}`;
    renderFan(); renderDrawdown(); renderSrs();
  }

  // --- charts (hand-written SVG) ---
  // Charts are drawn at the container's own width so 12px labels stay 12px on phones.
  function dims(host) {
    const W = Math.max(300, Math.min(900, host.clientWidth || 720));
    return { W, narrow: W < 520, M: { l: W < 520 ? 52 : 64, r: 12, t: 12, b: 36 } };
  }
  function niceMax(v) { const m = Math.pow(10, Math.floor(Math.log10(v))); return Math.ceil(v / m) * m; }

  function renderFan() {
    const k = state.chartSet, plan = state.plan, srs = state.srs;
    const rows = E.fan(state.draws, P, k, plan, srs, FAN_QS);
    const worst = E.worstDecileMedian(state.draws, P, k, plan, srs);
    const cash = E.cashPath(P, k, plan);
    const { W, M } = dims($("fan"));
    const H = W < 520 ? 260 : 300;
    const yMax = niceMax(Math.max(plan.goal * 1.1, rows[rows.length - 1][95], ...cash));
    const x = (yr) => M.l + (yr / plan.years) * (W - M.l - M.r);
    const y = (v) => H - M.b - (v / yMax) * (H - M.t - M.b);
    const area = (lo, hi) => rows.map((d, i) => `${i ? "L" : "M"}${x(d.year)},${y(d[hi])}`).join("") +
      rows.slice().reverse().map((d) => `L${x(d.year)},${y(d[lo])}`).join("") + "Z";
    const line = (vals) => vals.map((v, i) => `${i ? "L" : "M"}${x(i)},${y(v)}`).join("");
    const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => f * yMax);
    const xticks = [];
    const step = plan.years <= 10 ? 1 : plan.years <= 20 ? 5 : 10;
    for (let t = 0; t <= plan.years; t += step) xticks.push(t);
    $("fan").innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Fan chart of simulated wealth by year">
      <g class="axis">${ticks.map((v) => `<line class="gridline" x1="${M.l}" x2="${W - M.r}" y1="${y(v)}" y2="${y(v)}"/><text x="${M.l - 8}" y="${y(v) + 4}" text-anchor="end">${sgdK(v)}</text>`).join("")}
      ${xticks.map((t) => `<text x="${x(t)}" y="${H - M.b + 18}" text-anchor="middle">${t}</text>`).join("")}
      <text x="${(W + M.l) / 2}" y="${H - 2}" text-anchor="middle">Years from today</text></g>
      <path d="${area(5, 95)}" fill="var(--band-outer)"/><path d="${area(25, 75)}" fill="var(--band-inner)"/>
      <path d="${line(rows.map((d) => d[50]))}" fill="none" stroke="var(--series-1)" stroke-width="2"/>
      <path d="${line(worst)}" fill="none" stroke="var(--series-2)" stroke-width="2" stroke-dasharray="6 4"/>
      <path d="${line(cash)}" fill="none" stroke="var(--text-secondary)" stroke-width="1.5" stroke-dasharray="2 3"/>
      <line x1="${M.l}" x2="${W - M.r}" y1="${y(plan.goal)}" y2="${y(plan.goal)}" stroke="var(--text-primary)" stroke-width="1"/>
      <text x="${W - M.r}" y="${y(plan.goal) - 6}" text-anchor="end" fill="var(--text-primary)" font-size="12">Goal ${sgdK(plan.goal)}</text>
      <line id="fan-cross" x1="0" x2="0" y1="${M.t}" y2="${H - M.b}" stroke="var(--text-secondary)" stroke-width="1" visibility="hidden"/>
      <rect id="fan-hit" x="${M.l}" y="${M.t}" width="${W - M.l - M.r}" height="${H - M.t - M.b}" fill="transparent" tabindex="0" aria-label="Move along the chart to read values"/>
    </svg>
    <p class="hint"><span style="color:var(--series-1)">━</span> Median &nbsp; <span style="color:var(--series-2)">╍</span> Middle of the worst 10% &nbsp; <span style="color:var(--text-secondary)">┅</span> Held in cash &nbsp; Bands: middle 50% and 90% of futures</p>`;
    const svg = $("fan").querySelector("svg"), hit = $("fan-hit"), cross = $("fan-cross");
    const show = (yr, cx, cy) => {
      const d = rows[yr];
      cross.setAttribute("x1", x(yr)); cross.setAttribute("x2", x(yr)); cross.setAttribute("visibility", "visible");
      tip(`<strong>Year ${yr}</strong><br>Median ${sgd(d[50])}<br>Middle 50%: ${sgd(d[25])}–${sgd(d[75])}<br>Middle 90%: ${sgd(d[5])}–${sgd(d[95])}<br>Worst 10% (middle): ${sgd(worst[yr])}<br>Held in cash: ${sgd(cash[yr])}`, cx, cy);
    };
    hit.addEventListener("pointermove", (ev) => {
      const pt = svg.createSVGPoint(); pt.x = ev.clientX; pt.y = ev.clientY;
      const loc = pt.matrixTransform(svg.getScreenCTM().inverse());
      const yr = Math.max(0, Math.min(plan.years, Math.round(((loc.x - M.l) / (W - M.l - M.r)) * plan.years)));
      show(yr, ev.clientX, ev.clientY);
    });
    let focusYear = plan.years;
    hit.addEventListener("focus", () => { const b = hit.getBoundingClientRect(); show(focusYear, b.right - 40, b.top + 20); });
    hit.addEventListener("keydown", (ev) => {
      if (ev.key === "ArrowLeft" || ev.key === "ArrowRight") {
        focusYear = Math.max(0, Math.min(plan.years, focusYear + (ev.key === "ArrowRight" ? 1 : -1)));
        const b = hit.getBoundingClientRect(); show(focusYear, b.left + (focusYear / plan.years) * b.width, b.top + 20); ev.preventDefault();
      }
    });
    const hide = () => { cross.setAttribute("visibility", "hidden"); tip(null); };
    hit.addEventListener("pointerleave", hide); hit.addEventListener("blur", hide);
    $("fan-table").innerHTML = table(["Year", "5th", "25th", "Median", "75th", "95th", "Worst 10% (middle)", "Held in cash"],
      rows.map((d, i) => [d.year, sgd(d[5]), sgd(d[25]), sgd(d[50]), sgd(d[75]), sgd(d[95]), sgd(worst[i]), sgd(cash[i])]));
  }

  function renderDrawdown() {
    const rowsData = SHOWN.map((k) => {
      const s = E.sortedCopy(state.draws[k].dd);
      return { k, q: [5, 25, 50, 75, 95].map((q) => E.percentile(s, q)) };
    });
    const lo = Math.min(...rowsData.map((d) => d.q[0])), xMin = Math.floor(lo * 10) / 10;
    const { W, M, narrow } = dims($("drawdown"));
    const rowH = narrow ? 56 : 44, h = M.t + rowsData.length * rowH + 30, left = narrow ? 16 : 210;
    const x = (v) => left + ((v - xMin) / (0 - xMin)) * (W - left - M.r);
    const ticks = [];
    const tickStep = narrow ? 0.2 : 0.1;
    for (let v = 0; v >= xMin - 1e-9; v -= tickStep) ticks.unshift(Math.round(v * 10) / 10);
    $("drawdown").innerHTML = `<svg viewBox="0 0 ${W} ${h}" role="img" aria-label="Largest fall along the way under each assumption set">
      <g class="axis">${ticks.map((v) => `<line class="gridline" x1="${x(v)}" x2="${x(v)}" y1="${M.t}" y2="${h - 26}"/><text x="${x(v)}" y="${h - 10}" text-anchor="middle">${pct(v)}</text>`).join("")}</g>
      ${rowsData.map((d, i) => {
        const cy = M.t + i * rowH + rowH / 2 + (narrow ? 8 : 0);
        return `<g class="dd-row" tabindex="0" data-i="${i}" aria-label="${esc(P.sets[d.k].label)}: typical largest fall ${pct(d.q[2])}, worst 5% beyond ${pct(d.q[0])}">
          <text x="${narrow ? left : 0}" y="${narrow ? cy - 14 : cy + 4}" font-size="12" fill="var(--text-primary)">${esc(P.sets[d.k].label.split(" (")[0])}</text>
          <line x1="${x(d.q[0])}" x2="${x(d.q[4])}" y1="${cy}" y2="${cy}" stroke="${ACCENT[d.k]}" stroke-width="2"/>
          <rect x="${x(d.q[1])}" y="${cy - 8}" width="${Math.max(2, x(d.q[3]) - x(d.q[1]))}" height="16" rx="4" fill="${ACCENT[d.k]}" opacity="0.35"/>
          <circle cx="${x(d.q[2])}" cy="${cy}" r="5" fill="${ACCENT[d.k]}" stroke="var(--surface-1)" stroke-width="2"/>
          <rect x="0" y="${cy - rowH / 2}" width="${W}" height="${rowH}" fill="transparent"/></g>`;
      }).join("")}
    </svg>
    <p class="hint">Dot: typical (median) largest fall. Bar: middle half of futures. Line: from the worst 5% to the mildest 5%.</p>`;
    $("drawdown").querySelectorAll(".dd-row").forEach((g) => {
      const d = rowsData[Number(g.dataset.i)];
      const text = `<strong>${esc(P.sets[d.k].label)}</strong><br>Typical largest fall: ${pct(d.q[2])}<br>Middle half: ${pct(d.q[1])} to ${pct(d.q[3])}<br>Worst 5%: beyond ${pct(d.q[0])}`;
      g.addEventListener("pointermove", (ev) => tip(text, ev.clientX, ev.clientY));
      g.addEventListener("focus", () => { const b = g.getBoundingClientRect(); tip(text, b.left + 220, b.top); });
      g.addEventListener("pointerleave", () => tip(null)); g.addEventListener("blur", () => tip(null));
    });
    $("drawdown-table").innerHTML = table(["Assumptions", "Worst 5%", "25th", "Median", "75th", "Mildest 5%"],
      rowsData.map((d) => [P.sets[d.k].label, ...d.q.map((v) => pct(v))]));
  }

  function renderSrs() {
    const srs = state.srs, box = $("srs-results");
    box.hidden = !srs;
    if (!srs) return;
    const warn = $("srs-warning");
    const premature = E.srsPremature(srs, state.plan.years);
    warn.hidden = !premature;
    warn.textContent = premature
      ? `The goal date (age ${srs.age + state.plan.years}) is before the statutory retirement age you entered (${srs.statutoryAge}). Withdrawing then is fully taxed and attracts a ${pct(P.srs.premature_penalty)} penalty; the table assumes that.`
      : "";
    const rows = SHOWN.map((k) => {
      const o = E.srsOutcome(state.draws, P, k, state.plan, srs);
      return [P.sets[k].label, pct(o.pGoal), sgd(o.medianSrs), sgd(o.medianPlain), sgd(o.medianTax), pct(o.aheadShare)];
    });
    $("srs-table").innerHTML = table(["Assumptions", "Chance (SRS balance)", "After-tax withdrawals, SRS (median)", "Same money outside SRS (median)", "Tax paid (median)", "Futures where SRS ends ahead"], rows);
  }

  // --- helpers ---
  function table(head, rows, kind) {
    return `<div class="table-scroll"><table${kind ? ` class="${kind}"` : ""}><thead><tr>${head.map((h) => `<th scope="col">${esc(h)}</th>`).join("")}</tr></thead><tbody>${rows.map((r) => `<tr>${r.map((c, i) => (i ? `<td>${esc(c)}</td>` : `<th scope="row">${esc(c)}</th>`)).join("")}</tr>`).join("")}</tbody></table></div>`;
  }
  function tip(html, cx, cy) {
    const t = $("tooltip");
    if (!html) { t.hidden = true; return; }
    t.innerHTML = html; t.hidden = false;
    const w = t.offsetWidth, h = t.offsetHeight;
    t.style.left = Math.min(window.innerWidth - w - 8, cx + 12) + "px";
    t.style.top = Math.max(8, cy - h - 12) + "px";
  }

  function renderSources() {
    const s = P.sets, v = P.validation, c = P.costs, inf = P.inflation;
    const setRows = SHOWN.map((k) => [s[k].label, pct(s[k].equity, 1), pct(s[k].sgs, 1), pct(s[k].cash, 1)]);
    setRows.splice(1, 0, ["Central, low–high range (shares)", `${pct(P.central_range.low.equity, 1)}–${pct(P.central_range.high.equity, 1)}`, `${pct(P.central_range.low.sgs, 1)}–${pct(P.central_range.high.sgs, 1)}`, `${pct(P.central_range.low.cash, 1)}–${pct(P.central_range.high.cash, 1)}`]);
    const spf = inf.mas_spf
      ? ` The MAS Survey of Professional Forecasters (September 2026) has median forecasts of ${pct(inf.mas_spf["2026"], 1)} for 2026 and ${pct(inf.mas_spf["2027"], 1)} for 2027 (a near-term cross-check only).`
      : "";
    $("assumptions").innerHTML =
      `<p>Return assumptions, after inflation, a year, as of ${esc(P.as_of)}:</p>` +
      table(["Assumption set", "Global shares (in SGD)", "Singapore Government Securities", "SGD cash"], setRows) +
      `<p class="hint">How well the methods forecast the past (out-of-sample, 10-year horizons): today's bond yield explained most of the next decade's bond returns (R² ${v.bond_r2_us.toFixed(2)} in the US, ${v.bond_r2_jst.toFixed(2)} across countries), largely because a bond held for about its duration earns close to its starting yield. The share method did no better than the long-run average across countries (R² ${v.equity_r2_jst.toFixed(3)}, interval ${v.equity_r2_jst_low.toFixed(2)} to ${v.equity_r2_jst_high.toFixed(2)}), which is why several share assumptions are shown.</p>` +
      `<p class="hint">Inflation assumption: ${pct(inf.cma, 2)} a year (Singapore CPI, ${esc(inf.window)}).${spf}</p>` +
      `<p class="hint">Costs: equity fund TER ${pct(c.acwd_ter, 2)} plus withholding tax inside the fund (${pct(c.acwd_withholding, 1)} of a ${pct(c.acwd_dividend_yield, 2)} dividend yield); bond fund TER ${pct(c.a35_ter, 2)}; plus each purchase's broker, exchange, currency and spread costs including minimum fees, and a rebalancing cost. The fat-tailed model uses ${P.student_t.df} degrees of freedom, fitted to monthly returns from ${esc(P.history_span.start)} to ${esc(P.history_span.end)}.</p>`;
    $("licences").innerHTML = table(["What", "Derived from", "Terms"], P.licences.map((l) => [l.item, l.from, l.rule]), "text");
    $("notices").innerHTML = P.notices.map((n) => `<p class="hint">${esc(n)}</p>`).join("");
  }

  let resizeTimer = null;
  window.addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => { if (state.plan) { renderFan(); renderDrawdown(); } }, 150);
  });

  // --- start ---
  buildControls();
  setInputs(P.presets.A);
  $("target").value = 75;
  renderSources();
  syncOutputs();
  schedule();
})();
