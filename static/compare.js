const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const num = (n, d = 2) => (n == null ? "—" : Number(n).toLocaleString("en-IN", { minimumFractionDigits: d, maximumFractionDigits: d }));
const sgn = (n) => (n == null ? "" : n >= 0 ? "up" : "down");
const pctRaw = (n) => (n == null ? "—" : `${n >= 0 ? "+" : ""}${n.toFixed(2)}%`);
async function getJSON(url) {
    const r = await fetch(url);
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
    return r.json();
}
const setBody = (id, html) => { const el = $(id); el.className = "body"; el.innerHTML = html; };
const fail = (id, e) => { const el = $(id); el.className = "body err"; el.textContent = `DATA UNAVAILABLE: ${e.message}`; };

let ALL = [];            // [{ticker, name, sector}]
let picked = [];         // ["TCS", "INFY"...]
let range = "6mo";
const RANGES = { "1mo": "1M", "3mo": "3M", "6mo": "6M", "1y": "1Y", "2y": "2Y" };

/* ---------- picker ---------- */
function renderPicker() {
    const free = ALL.filter((s) => !picked.includes(s.ticker));
    $("picker").innerHTML = `<span class="cy">STOCKS (${picked.length}/8):</span>` +
        picked.map((t) => `<span class="chip" data-rm="${t}">${t} ✕</span>`).join("") +
        (picked.length < 8 ? `<select id="addSel"><option value="">+ add stock</option>${free.map((s) => `<option value="${s.ticker}">${s.ticker} · ${esc(s.name)}</option>`).join("")}</select>` : "");
    document.querySelectorAll("[data-rm]").forEach((c) => c.addEventListener("click", () => { if (picked.length > 2) { picked = picked.filter((t) => t !== c.dataset.rm); refresh(); } }));
    const sel = $("addSel"); if (sel) sel.addEventListener("change", () => { if (sel.value) { picked.push(sel.value); refresh(); } });
    $("rangeTabs").innerHTML = Object.entries(RANGES).map(([k, v]) => `<button class="tab ${k === range ? "on" : ""}" data-r="${k}">${v}</button>`).join("");
    document.querySelectorAll("#rangeTabs .tab").forEach((b) => b.addEventListener("click", () => { range = b.dataset.r; refresh(); }));
}

/* ---------- comparison ---------- */
function heat(v) { // -1..1 -> red..amber..green
    if (v == null) return "#444";
    const a = Math.abs(v);
    return v >= 0 ? `rgba(51,255,51,${0.15 + 0.85 * a})` : `rgba(255,59,48,${0.15 + 0.85 * a})`;
}

async function refresh() {
    history.replaceState(null, "", `?tickers=${picked.join(",")}`);
    renderPicker();
    $("corrBox").className = "body wait"; $("corrBox").textContent = "LOADING"; $("statTable").className = "body wait"; $("statTable").textContent = "LOADING";
    try {
        const d = await getJSON(`/compare?tickers=${picked.join(",")}&range=${range}`);
        const C = CH.C, tick = (s) => s.replace(".NS", "");
        CH.make("chPerf", { type: "line", data: { labels: d.dates, datasets: Object.entries(d.series).map(([s, v], i) => CH.line(tick(s), v, CH.PALETTE[i % CH.PALETTE.length], { borderWidth: 1.8 })) },
            options: { interaction: { mode: "index", intersect: false }, scales: { x: CH.xTicks, y: { position: "right", title: { display: true, text: "rebased to 100" } } } } });
        $("cmpNote").textContent = d.note;

        CH.make("chRisk", { type: "scatter", data: { datasets: d.stats.map((r, i) => ({ label: tick(r.ticker), data: [{ x: r.volatility_pct, y: r.return_pct }],
            backgroundColor: CH.PALETTE[i % CH.PALETTE.length], pointRadius: 7 })) },
            options: { scales: { x: { title: { display: true, text: "annualised volatility %" } }, y: { title: { display: true, text: "return % over range" } } } } });

        const cm = d.correlation;
        setBody("corrBox", `<table class="heat"><thead><tr><th></th>${cm.tickers.map((t) => `<th>${tick(t)}</th>`).join("")}</tr></thead><tbody>
            ${cm.matrix.map((row, i) => `<tr><th class="l">${tick(cm.tickers[i])}</th>${row.map((v) => `<td style="background:${heat(v)};color:${v != null && Math.abs(v) < 0.6 ? "#fff" : "#000"}">${v == null ? "—" : v.toFixed(2)}</td>`).join("")}</tr>`).join("")}</tbody></table>
            <div class="note">Closer to 1 = moves together (less diversification). Pearson correlation of daily returns over the selected range.</div>`);

        setBody("statTable", `<table><thead><tr><th class="l">TICKER</th><th class="l">SECTOR</th><th>RETURN</th><th>VOLATILITY</th><th>MAX DRAWDOWN</th><th>RET/VOL</th><th>ACTIONS</th></tr></thead><tbody>
            ${d.stats.map((r) => `<tr><td class="l"><a href="/stock?ticker=${tick(r.ticker)}">${tick(r.ticker)}</a> <span class="dim">${esc(r.name || "")}</span></td><td class="l cy">${esc(r.sector || "")}</td>
            <td class="${sgn(r.return_pct)}">${pctRaw(r.return_pct)}</td><td>${num(r.volatility_pct)}%</td><td class="down">${num(r.max_drawdown_pct)}%</td><td>${num(r.return_over_vol)}</td>
            <td><a class="btn-bs buy" href="/stock?ticker=${tick(r.ticker)}&order=BUY">BUY</a> <a class="btn-bs sell" href="/stock?ticker=${tick(r.ticker)}&order=SELL">SELL</a></td></tr>`).join("")}</tbody></table>`);
    } catch (e) { fail("corrBox", e); fail("statTable", e); }
}

/* ---------- sectors + news ---------- */
let secTimer = null;
async function loadSectors() {
    let d;
    try { d = await getJSON("/compare/sectors"); } catch (e) { $("newsProgress").className = "progress down"; $("newsProgress").textContent = `DATA UNAVAILABLE: ${e.message}`; return; }
    const C = CH.C, p = d.news_progress;
    const covered = d.stocks.filter((s) => s.news_score != null).length;
    $("newsProgress").textContent = p.running ? `SCORING NEWS: ${p.done}/${p.total} stocks done (charts update automatically)...` : `NEWS SCORED FOR ${covered}/${d.stocks.length} STOCKS`;
    if (p.running) { clearTimeout(secTimer); secTimer = setTimeout(loadSectors, 6000); }

    const sec = d.sectors;
    CH.make("chSecBar", { type: "bar", data: { labels: sec.map((s) => s.sector), datasets: [
        { label: "Avg 1M return %", data: sec.map((s) => s.avg_ret_1m), backgroundColor: C.cyan, yAxisID: "y" },
        { label: "Avg news score", data: sec.map((s) => s.avg_news_score), backgroundColor: C.yellow, yAxisID: "y2" },
    ] }, options: { scales: { x: { ticks: { maxRotation: 40 } }, y: { position: "left", title: { display: true, text: "1M return %" } },
        y2: { position: "right", min: -1, max: 1, grid: { display: false }, title: { display: true, text: "news score (-1..+1)" } } } } });

    CH.make("chSecMix", { type: "bar", data: { labels: sec.map((s) => s.sector), datasets: [
        { label: "Bullish", data: sec.map((s) => s.bullish), backgroundColor: C.green },
        { label: "Neutral", data: sec.map((s) => s.neutral), backgroundColor: C.yellow },
        { label: "Bearish", data: sec.map((s) => s.bearish), backgroundColor: C.red },
    ] }, options: { scales: { x: { stacked: true, ticks: { maxRotation: 40 } }, y: { stacked: true, ticks: { stepSize: 1 } } } } });

    const names = [...new Set(d.stocks.map((s) => s.sector))];
    const pts = d.stocks.filter((s) => s.news_score != null && s.ret_1m != null);
    CH.make("chScatter", { type: "scatter", data: { datasets: names.map((n, i) => ({ label: n, backgroundColor: CH.PALETTE[i % CH.PALETTE.length], pointRadius: 5,
        data: pts.filter((s) => s.sector === n).map((s) => ({ x: s.news_score, y: s.ret_1m, t: s.ticker })) })) },
        options: { plugins: { tooltip: { callbacks: { label: (c) => `${c.raw.t}: news ${c.raw.x}, 1M ${c.raw.y}%` } } },
            scales: { x: { title: { display: true, text: "news score (-1 bearish … +1 bullish)" }, min: -1, max: 1 }, y: { title: { display: true, text: "1M price return %" } } } } });
    const r = d.correlation_news_vs_1m_return;
    $("scatterNote").textContent = r.r == null ? "NEWS STILL SCORING" : `Pearson r = ${r.r} (n=${r.n})`;

    setBody("secTable", `<table><thead><tr><th class="l">SECTOR</th><th>STOCKS</th><th>DAY</th><th>1M</th><th>3M</th><th>NEWS SCORE</th><th>BULL/NEUT/BEAR</th></tr></thead><tbody>
        ${sec.map((s) => `<tr><td class="l cy">${esc(s.sector)}</td><td>${s.count}</td><td class="${sgn(s.avg_day_pct)}">${pctRaw(s.avg_day_pct)}</td>
        <td class="${sgn(s.avg_ret_1m)}">${pctRaw(s.avg_ret_1m)}</td><td class="${sgn(s.avg_ret_3m)}">${pctRaw(s.avg_ret_3m)}</td>
        <td class="${sgn(s.avg_news_score)}">${s.avg_news_score == null ? "…" : s.avg_news_score.toFixed(3)} <span class="dim">(${s.news_covered}/${s.count})</span></td>
        <td>${s.bullish}/${s.neutral}/${s.bearish}</td></tr>`).join("")}</tbody></table>`);
    $("secNote").textContent = `${d.note} Source: ${d.source}`;
}

/* ---------- keyboard shortcuts (see keys.js; '?' lists them) ---------- */
function setupKeyboard() {
    const rng = (r) => () => { range = r; refresh(); };
    Keys.bind([
        { key: "/", desc: "Focus the add-stock box", fn: () => { const s = $("addSel"); if (s) s.focus(); } },
        { key: "1", desc: "Range 1M", fn: rng("1mo") }, { key: "2", desc: "Range 3M", fn: rng("3mo") },
        { key: "3", desc: "Range 6M", fn: rng("6mo") }, { key: "4", desc: "Range 1Y", fn: rng("1y") },
        { key: "5", desc: "Range 2Y", fn: rng("2y") },
    ]);
}

/* ---------- live refresh (only while the market is open) ---------- */
const FORCE_POLL = new URLSearchParams(location.search).get("poll") === "1";
let liveOn = false, liveTimers = [];
async function checkMarket() {
    let open = FORCE_POLL;
    try { open = open || (await getJSON("/stocks/status")).is_open; } catch (e) { return; }
    if (open && !liveOn) {
        liveTimers = [setInterval(() => { if (!document.hidden) loadSectors().catch(() => {}); }, 60000),   // day % moves; news re-scores every 10 min
                      setInterval(() => { if (!document.hidden) refresh(); }, 300000)];                      // Yahoo bars: every 5 min
    } else if (!open && liveOn) { liveTimers.forEach(clearInterval); liveTimers = []; }
    liveOn = open;
}

/* ---------- boot ---------- */
(async function init() {
    setupKeyboard();
    try {
        const stocks = await getJSON("/stocks");
        ALL = stocks.map((s) => ({ ticker: s.ticker.replace(".NS", ""), name: s.name, sector: s.sector }));
    } catch (e) { $("picker").textContent = `DATA UNAVAILABLE: ${e.message}`; return; }
    const valid = new Set(ALL.map((s) => s.ticker));
    picked = (new URLSearchParams(location.search).get("tickers") || "").toUpperCase().split(",").filter((t) => valid.has(t));
    if (picked.length === 0) picked = ["RELIANCE", "TCS", "HDFCBANK"];
    if (picked.length === 1) { // single ticker arrives from a stock page: add same-sector peers
        const me = ALL.find((s) => s.ticker === picked[0]);
        const peers = ALL.filter((s) => s.sector === me.sector && s.ticker !== me.ticker).slice(0, 2).map((s) => s.ticker);
        picked = [...picked, ...(peers.length >= 1 ? peers : ["RELIANCE", "TCS"].filter((t) => t !== picked[0]).slice(0, 2))];
    }
    refresh();
    loadSectors();
    checkMarket();
    setInterval(checkMarket, 60000);
})();
