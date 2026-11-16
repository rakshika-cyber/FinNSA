const params = new URLSearchParams(location.search);
const TICKER = (params.get("ticker") || "").toUpperCase().replace(".NS", "");
// ?poll=1 forces the live refresh loops even when the market is closed (testing only; data is still real, just unchanged).
const FORCE_POLL = params.get("poll") === "1";
let MARKET_OPEN = false;

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

/* ---------- formatters ---------- */
const DASH = "—";
const num = (n, d = 2) => (n == null || Number.isNaN(n) ? DASH : Number(n).toLocaleString("en-IN", { minimumFractionDigits: d, maximumFractionDigits: d }));
const int = (n) => (n == null ? DASH : Number(n).toLocaleString("en-IN"));
const pct = (n, d = 1) => (n == null ? DASH : `${(n * 100).toFixed(d)}%`);
const pctRaw = (n) => (n == null ? DASH : `${n >= 0 ? "+" : ""}${n.toFixed(2)}%`);
const sgn = (n) => (n == null ? "" : n >= 0 ? "up" : "down");
function inrCompact(n) {
    if (n == null) return DASH;
    const cr = n / 1e7;
    if (Math.abs(cr) >= 1e5) return `₹${(cr / 1e5).toFixed(2)} L Cr`;
    return `₹${cr.toLocaleString("en-IN", { maximumFractionDigits: 0 })} Cr`;
}
function qty(n) { // compact quantity: 1.2L, 3.4Cr
    if (n == null) return DASH;
    if (n >= 1e7) return (n / 1e7).toFixed(2) + "Cr";
    if (n >= 1e5) return (n / 1e5).toFixed(2) + "L";
    if (n >= 1e3) return (n / 1e3).toFixed(1) + "K";
    return String(n);
}
const kv = (k, v) => `<div><div class="k">${k}</div><div class="v">${v}</div></div>`;
const dl = (rows) => `<dl class="kv">${rows.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join("")}</dl>`;

async function getJSON(url) {
    const r = await fetch(url);
    if (!r.ok) {
        const err = new Error((await r.json().catch(() => ({}))).detail || r.statusText);
        err.brokerOff = r.headers.get("X-Broker") === "not-connected";
        throw err;
    }
    return r.json();
}
const setBody = (id, html) => { const el = $(id); el.className = "body"; el.innerHTML = html; };
const BROKER_OFF_BOXES = new Set();
const fail = (id, e) => {
    const el = $(id);
    if (e && e.brokerOff) {   // not an error: live NSE/NFO data simply needs a broker session
        BROKER_OFF_BOXES.add(id);
        el.className = "body wait";
        el.innerHTML = `LIVE DATA NEEDS A BROKER CONNECTION<br><button class="chip" data-connect-broker>CONNECT ANGEL ONE [G]</button>`;
        return;
    }
    el.className = "body err"; el.textContent = `DATA UNAVAILABLE: ${e.message}`;
};
document.addEventListener("click", (ev) => { if (ev.target.closest("[data-connect-broker]") && window.Header) window.Header.openBroker(); });
// Once the broker connects (header fires this), reload the panels that were waiting on it.
window.addEventListener("broker:connected", () => {
    if (!BROKER_OFF_BOXES.size) return;
    BROKER_OFF_BOXES.clear();
    loadDepth().catch((e) => fail("depthBox", e));
    loadFutures().catch((e) => fail("futBox", e));
    loadChain();
});

/* ---------- quote strip ---------- */
let QUOTE = null;
let TICKER_LIST = [];
async function loadQuote(first = true) {
    const [stocks, status] = await Promise.all([getJSON("/stocks"), getJSON("/stocks/status")]);
    const st = stocks.find((s) => s.ticker === `${TICKER}.NS`);
    if (!st) throw new Error("Ticker not in Nifty 50 list");
    const prevPrice = QUOTE ? QUOTE.price : null;
    QUOTE = st;
    MARKET_OPEN = status.is_open || FORCE_POLL;
    if (first) TICKER_LIST = stocks.map((x) => x.ticker.replace(".NS", ""));
    $("strip").innerHTML = `
        <span class="nm">${esc(TICKER)} · ${esc(st.name)}</span>
        <span class="px ${prevPrice != null && st.price !== prevPrice ? (st.price > prevPrice ? "flash-up" : "flash-down") : ""}">₹${num(st.price)}</span>
        <span class="${sgn(st.change_percent)}">${pctRaw(st.change_percent)}</span>
        <span><span class="lbl">SECTOR</span>${esc(st.sector)}</span>
        <span><span class="lbl">DAY L/H</span>${num(st.day_low)} / ${num(st.day_high)}</span>
        <span><span class="lbl">VOL</span>${int(st.volume)}</span>
        <span class="${MARKET_OPEN ? "up" : "down"}">${MARKET_OPEN ? `● LIVE · ${new Date().toLocaleTimeString("en-IN", { hour12: false })}` : "● MARKET CLOSED · LAST TRADED"}</span>
        <span style="margin-left:auto"><button class="btn-bs buy" id="btnBuy">BUY</button> <button class="btn-bs sell" id="btnSell">SELL</button></span>`;
    $("btnBuy").addEventListener("click", () => openOrder("BUY"));
    $("btnSell").addEventListener("click", () => openOrder("SELL"));
    $("cmpLink").href = `/compare-view?tickers=${TICKER}`;
    const wanted = params.get("order");
    if (first && (wanted === "BUY" || wanted === "SELL")) setTimeout(() => openOrder(wanted), 0);
    if (!first && typeof orderOpen === "function" && orderOpen()) syncOrder(); // keep an open ticket on the live price
}

/* ---------- statistics ---------- */
async function loadStats() {
    const s = await getJSON(`/company/${TICKER}/statistics`);
    const r = s.returns_pct;
    const c = (v) => `<span class="${sgn(v)}">${pctRaw(v)}</span>`;
    setBody("statsBox", dl([
        ["Return 1M", c(r["1M"])], ["Return 3M", c(r["3M"])], ["Return 6M", c(r["6M"])], ["Return 1Y", c(r["1Y"])],
        ["Volatility 20D (ann.)", `${num(s.volatility_annualised_pct["20D"])}%`],
        ["Volatility 1Y (ann.)", `${num(s.volatility_annualised_pct["1Y"])}%`],
        ["Max drawdown 1Y", `<span class="down">${num(s.max_drawdown_1y_pct)}%</span>`],
        ["SMA 50", `₹${num(s.sma_50)}`], ["SMA 200", s.sma_200 ? `₹${num(s.sma_200)}` : DASH],
        ["52W High", `₹${num(s.week52_high)}`], ["52W Low", `₹${num(s.week52_low)}`],
        ["Avg volume 20D", int(s.avg_volume_20d)],
    ]) + `<div class="note">${esc(s.source)}</div>`);
}

/* ---------- news signal + headlines ---------- */
async function loadSignal() {
    const sig = await getJSON(`/company/${TICKER}/news-signal`);
    const b = sig.breakdown || {};
    setBody("signalBox", `
        <div class="signal ${sig.signal}">${sig.signal}</div>
        ${dl([["Score (-1..+1)", num(sig.score, 3)], ["Confidence", Math.round(sig.confidence * 100) + "%"],
              ["Headlines", sig.count], ["Pos/Neu/Neg", `${b.positive || 0}/${b.neutral || 0}/${b.negative || 0}`]])}
        <div class="note">Recency-weighted (3-day half-life) FinBERT sentiment of headlines. Not a price forecast.</div>`);

    setBody("newsBox", sig.headlines.length ? `<table><tbody>${sig.headlines.map((h) => {
        const cls = h.label === "positive" ? "up" : h.label === "negative" ? "down" : "dim";
        const d = new Date(h.published).toLocaleDateString("en-IN", { day: "2-digit", month: "short" });
        return `<tr><td class="l"><a href="${esc(h.link)}" target="_blank" rel="noopener noreferrer">${esc(h.title)}</a></td>
            <td class="dim">${esc(h.source || "")}</td><td class="dim">${d}</td><td class="${cls}">${esc(h.label.toUpperCase())} ${h.score}</td></tr>`;
    }).join("")}</tbody></table>` : "NO RECENT HEADLINES");
}

/* ---------- technicals ---------- */
async function loadTech() {
    const d = await getJSON(`/detectors/${TICKER}`);
    const tone = (t) => (/BULL/.test(t) ? "up" : /BEAR/.test(t) ? "down" : "yl");
    setBody("techBox", dl([
        ["RSI (14, Wilder)", `${d.rsi} <span class="${tone(d.rsi_signal)}">${esc(d.rsi_signal)}</span>`],
        ["VWAP (last session)", d.vwap ? `₹${num(d.vwap)}` : DASH],
        ["Price vs VWAP", `<span class="${tone(d.vwap_signal)}">${esc(d.vwap_signal)}</span>`],
        ["MACD (12,26,9)", num(d.macd.macd_line)], ["Signal line", num(d.macd.signal_line)],
        ["Histogram", `<span class="${sgn(d.macd.histogram)}">${num(d.macd.histogram)}</span>`],
        ["MACD trend", `<span class="${tone(d.macd.trend)}">${esc(d.macd.trend)}</span>`],
    ]) + `<div class="note">${esc(d.source)}</div>`);
}

/* ---------- market depth (buy / sell book) ---------- */
async function loadDepth() {
    const d = await getJSON(`/company/${TICKER}/depth`);
    const maxQ = Math.max(1, ...d.buy.map((l) => l.qty), ...d.sell.map((l) => l.qty));
    const bar = (q, cls) => `<span class="bar ${cls}" style="width:${Math.round((q / maxQ) * 60)}px"></span>`;
    const lvl = (l, side) => (l.price ? `<td class="${side === "b" ? "bp" : "ap"}">${num(l.price)}</td><td>${int(l.qty)}${bar(l.qty, side)}</td><td class="dim">${l.orders}</td>`
                                       : `<td class="dim">${DASH}</td><td class="dim">${DASH}</td><td class="dim">${DASH}</td>`);
    const rows = d.buy.map((b, i) => `<tr>${lvl(b, "b")}${lvl(d.sell[i] || { price: 0 }, "a")}</tr>`).join("");
    const bt = d.total_buy_qty || 0, st = d.total_sell_qty || 0;
    setBody("depthBox", `<table class="book"><thead><tr><th colspan="3" class="up">BUY (BID)</th><th colspan="3" class="down">SELL (ASK)</th></tr>
        <tr><th>PRICE</th><th>QTY</th><th>ORD</th><th>PRICE</th><th>QTY</th><th>ORD</th></tr></thead><tbody>${rows}</tbody></table>
        ${dl([["Total buy qty", `<span class="up">${int(bt)}</span>`], ["Total sell qty", `<span class="down">${int(st)}</span>`],
              ["Circuit L/U", `${num(d.lower_circuit)} / ${num(d.upper_circuit)}`]])}
        <div class="note">Best 5 levels. Outside market hours this shows only the closing-auction residue.</div>`);
}

/* ---------- futures ---------- */
async function loadFutures() {
    const f = await getJSON(`/company/${TICKER}/futures`);
    if (!f.length) return setBody("futBox", "NO LISTED FUTURES");
    setBody("futBox", `<table><thead><tr><th class="l">EXPIRY</th><th>LTP</th><th>CHG%</th><th>BASIS</th><th>OI</th><th>VOL</th></tr></thead><tbody>
        ${f.map((x) => `<tr><td class="l cy">${esc(x.expiry)}</td><td class="hi">${num(x.ltp)}</td><td class="${sgn(x.change_pct)}">${pctRaw(x.change_pct)}</td>
        <td>${num(x.basis)}</td><td>${qty(x.oi)}</td><td>${qty(x.volume)}</td></tr>`).join("")}</tbody></table>
        <div class="note">Basis = futures LTP − spot. Lot size ${int(f[0].lot)}. OI &amp; volume in shares.</div>`);
}

/* ---------- option chain ---------- */
let CHAIN = null, SELECTED = null, EXPIRY = null;

async function loadChain(expiry) {
    $("chainBox").className = "body wait"; $("chainBox").textContent = "LOADING";
    try {
        const url = `/company/${TICKER}/option-chain` + (expiry ? `?expiry=${encodeURIComponent(expiry)}` : "");
        CHAIN = await getJSON(url);
        EXPIRY = CHAIN.expiry;
        SELECTED = CHAIN.atm_strike;
        renderChain();
    } catch (e) {
        fail("chainBox", e); fail("derivBox", e); fail("greeksBox", e); $("expiryTabs").innerHTML = "";
    }
}

function renderChain() {
    const d = CHAIN;
    $("expiryTabs").innerHTML = d.expiries.map((e) => `<button class="tab ${e === EXPIRY ? "on" : ""}" data-exp="${e}">${e}</button>`).join("")
        + `<span class="dim" style="margin-left:auto">SPOT ₹${num(d.spot)} · ${d.days_to_expiry}d to expiry</span>`;
    document.querySelectorAll(".tab").forEach((b) => b.addEventListener("click", () => loadChain(b.dataset.exp)));

    const maxOI = Math.max(1, ...d.chain.flatMap((r) => [r.CE?.oi || 0, r.PE?.oi || 0]));
    const w = (v) => Math.round((v / maxOI) * 50);
    const cell = (o, side) => {
        if (!o) return `<td colspan="7" class="dim c">${DASH}</td>`;
        const oi = `<td>${side === "CE" ? `<span class="bar oic" style="width:${w(o.oi)}px"></span> ` : ""}${qty(o.oi)}${side === "PE" ? ` <span class="bar oip" style="width:${w(o.oi)}px"></span>` : ""}</td>`;
        const cols = [oi, `<td>${qty(o.volume)}</td>`, `<td>${o.iv == null ? DASH : o.iv.toFixed(1)}</td>`,
            `<td>${o.greeks ? o.greeks.delta.toFixed(3) : DASH}</td>`, `<td class="up">${num(o.bid)}</td>`, `<td class="down">${num(o.ask)}</td>`,
            `<td class="ltp">${num(o.ltp)}</td>`];
        return (side === "CE" ? cols : cols.slice().reverse()).join("");
    };
    const head = ["OI", "VOL", "IV%", "DELTA", "BID", "ASK", "LTP"];
    const rows = d.chain.map((r) => {
        const itmC = r.strike < d.spot, itmP = r.strike > d.spot;
        let ce = cell(r.CE, "CE"), pe = cell(r.PE, "PE");
        if (itmC) ce = ce.replace(/<td/g, '<td class="itm"').replace(/<td class="itm" class="/g, '<td class="itm ');
        if (itmP) pe = pe.replace(/<td/g, '<td class="itm"').replace(/<td class="itm" class="/g, '<td class="itm ');
        return `<tr data-strike="${r.strike}" class="${r.strike === d.atm_strike ? "atm" : ""} ${r.strike === SELECTED ? "sel" : ""}">${ce}<td class="strike">${num(r.strike, 0)}</td>${pe}</tr>`;
    }).join("");

    setBody("chainBox", `<table class="chain"><thead><tr><th colspan="7" class="c side-ce">CALLS (CE)</th><th></th><th colspan="7" class="c side-pe">PUTS (PE)</th></tr>
        <tr>${head.map((h) => `<th>${h}</th>`).join("")}<th class="c">STRIKE</th>${head.slice().reverse().map((h) => `<th>${h}</th>`).join("")}</tr></thead><tbody>${rows}</tbody></table>`);
    document.querySelectorAll(".chain tbody tr").forEach((tr) => tr.addEventListener("click", () => { SELECTED = Number(tr.dataset.strike); renderChain(); }));

    const a = d.assumptions;
    $("chainNote").textContent = `Shaded = in-the-money. Exchange feed time: ${d.exchange_feed_time || DASH}. ${a.note} Model: ${a.model}, r=${(a.risk_free_rate * 100).toFixed(2)}%, dividend yield=${(a.dividend_yield * 100).toFixed(1)}%. IV% blank = no trades/OI (stale quote) or price outside no-arbitrage bounds. Strikes shown: ${d.summary.window}.`;

    const s = d.summary, pcrTone = (v) => (v == null ? "" : v > 1 ? "up" : v < 0.7 ? "down" : "yl");
    setBody("derivBox", dl([
        ["PCR (OI)", `<span class="${pcrTone(s.pcr_oi)}">${num(s.pcr_oi, 3)}</span>`], ["PCR (volume)", `<span class="${pcrTone(s.pcr_volume)}">${num(s.pcr_volume, 3)}</span>`],
        ["Call OI", qty(s.call_oi)], ["Put OI", qty(s.put_oi)],
        ["Max pain", `₹${num(s.max_pain, 0)}`], ["ATM IV", s.atm_iv == null ? DASH : `${s.atm_iv}%`],
        ["Lot size", int(s.lot_size)], ["ATM strike", num(d.atm_strike, 0)],
    ]) + `<div class="note">Stats cover ${esc(s.window)} of the ${esc(d.expiry)} expiry only. PCR &gt; 1 = more put OI than call OI.</div>`);

    renderGreeks();
    renderOptionCharts();
}

function renderGreeks() {
    const row = CHAIN.chain.find((r) => r.strike === SELECTED);
    if (!row) return;
    const side = (o, name, cls) => {
        if (!o) return `<div><h3 class="${cls}">${name}</h3>${DASH}</div>`;
        const g = o.greeks;
        return `<div><h3 class="${cls}">${name} ${esc(o.symbol)}</h3>` + dl([
            ["LTP", `₹${num(o.ltp)}`], ["Bid / Ask", `${num(o.bid)} / ${num(o.ask)}`], ["Implied vol", o.iv == null ? DASH : `${o.iv}%`],
            ["Delta", g ? g.delta : DASH], ["Gamma", g ? g.gamma : DASH],
            ["Theta (₹/day)", g ? g.theta : DASH], ["Vega (₹ per 1 vol pt)", g ? g.vega : DASH],
            ["Open interest", int(o.oi)], ["Volume", int(o.volume)],
        ]) + "</div>";
    };
    setBody("greeksBox", `<div class="hi" style="margin-bottom:6px">STRIKE ₹${num(SELECTED, 0)} · EXPIRY ${esc(CHAIN.expiry)}</div>
        <div class="greeks-grid">${side(row.CE, "CALL", "up")}${side(row.PE, "PUT", "down")}</div>
        <div class="note">Computed from live option prices with Black-Scholes; not exchange-published. Click any chain row to change strike.</div>`);
}

/* ---------- governance: officers, holders, analysts ---------- */
async function loadGovernance() {
    const g = await getJSON(`/company/${TICKER}/governance`);
    const pay = (n) => (n == null ? DASH : inrCompact(n));
    setBody("peopleBox", g.officers.length ? `<table><thead><tr><th class="l">NAME</th><th class="l">TITLE</th><th>AGE</th><th>TOTAL PAY (FY${g.officers[0].fiscal_year || ""})</th></tr></thead><tbody>
        ${g.officers.map((o) => `<tr><td class="l hi">${esc(o.name)}</td><td class="l cy">${esc(o.title)}</td><td>${o.age ?? DASH}</td><td>${pay(o.total_pay_inr)}</td></tr>`).join("")}</tbody></table>
        <div class="note">${esc(g.scope_note)} Official: <a href="${esc(g.official_links.nse_company)}" target="_blank" rel="noopener noreferrer">NSE company page</a> ·
        <a href="${esc(g.official_links.bse_search)}" target="_blank" rel="noopener noreferrer">BSE scrip search</a> (Corporate Governance &amp; Shareholding Pattern filings)</div>`
        : `NO OFFICER DATA. ${esc(g.scope_note)}`);

    const a = g.analysts, h = g.holders;
    const upside = a.target_mean && QUOTE ? ((a.target_mean / QUOTE.price - 1) * 100) : null;
    setBody("holdBox", dl([
        ["Insiders / promoters held", pct(h.insiders_pct)], ["Institutions held", pct(h.institutions_pct)],
        ["Analyst consensus", a.recommendation ? esc(a.recommendation.replace("_", " ").toUpperCase()) : DASH], ["Analysts covering", a.count ?? DASH],
        ["Target mean", a.target_mean ? `₹${num(a.target_mean)}` : DASH],
        ["Target low / high", `${a.target_low ? "₹" + num(a.target_low) : DASH} / ${a.target_high ? "₹" + num(a.target_high) : DASH}`],
        ["Implied move to mean", upside == null ? DASH : `<span class="${sgn(upside)}">${pctRaw(upside)}</span>`],
    ]) + `<div class="note">Holding % and analyst targets are third-party aggregates; the exchange-filed shareholding pattern is authoritative.</div>`);
}

/* ---------- fundamentals ---------- */
function barChart(rev, ni) {
    if (!rev.length) return "NO ANNUAL STATEMENT DATA FOR THIS COMPANY";
    const max = Math.max(...rev.map((r) => r.value || 0), ...ni.map((r) => r.value || 0)) || 1;
    const niBy = Object.fromEntries(ni.map((r) => [r.period, r.value]));
    const bar = (v, ch) => ch.repeat(Math.max(0, Math.round(((v || 0) / max) * 40)));
    return `<pre style="margin:0;font-family:inherit">${rev.map((r) =>
        `<span class="cy">FY${r.period.slice(0, 4)}</span> REV <span class="up">${bar(r.value, "█")}</span> ${inrCompact(r.value)}\n` +
        `       NI  <span class="yl">${bar(niBy[r.period], "▒")}</span> ${inrCompact(niBy[r.period])}`).join("\n")}</pre>`;
}

async function loadFundamentals() {
    const f = await getJSON(`/company/${TICKER}/fundamentals`);
    const v = f.valuation, fin = f.financials, p = f.profile;
    setBody("fundBox", `<div class="kv2">
        ${kv("Market cap", inrCompact(v.market_cap))} ${kv("Revenue (TTM)", inrCompact(fin.total_revenue_ttm))}
        ${kv("Revenue growth", pct(fin.revenue_growth))} ${kv("Earnings growth", pct(fin.earnings_growth))}
        ${kv("Profit margin", pct(fin.profit_margin))} ${kv("Operating margin", pct(fin.operating_margin))}
        ${kv("P/E (TTM)", num(v.pe_trailing))} ${kv("P/E (fwd)", num(v.pe_forward))}
        ${kv("P/B", num(v.price_to_book))} ${kv("EPS (TTM)", num(v.eps_trailing))}
        ${kv("ROE", pct(fin.return_on_equity))} ${kv("Debt / Equity", num(fin.debt_to_equity))}
        ${kv("Dividend yield", v.dividend_yield_pct == null ? DASH : num(v.dividend_yield_pct) + "%")} ${kv("Beta", num(v.beta))}
        ${kv("Industry", esc(p.industry || DASH))} ${kv("Employees", int(p.employees))}</div>
        ${p.summary ? `<div class="note">${esc(p.summary)}</div>` : ""}
        <div class="note">Source: ${esc(f.source)}. Banks report total income, not comparable to non-financial revenue.</div>`);
    setBody("chartBox", barChart(fin.revenue_annual, fin.net_income_annual));
}




/* ---------- statistical charts ---------- */
const RANGE_LABELS = { "3mo": "3M", "6mo": "6M", "1y": "1Y", "2y": "2Y" };
let CHART_RANGE = "1y";

async function loadCharts(range) {
    CHART_RANGE = range;
    $("rangeTabs").innerHTML = Object.entries(RANGE_LABELS).map(([k, v]) => `<button class="tab ${k === range ? "on" : ""}" data-r="${k}">${v}</button>`).join("");
    document.querySelectorAll("#rangeTabs .tab").forEach((b) => b.addEventListener("click", () => loadCharts(b.dataset.r).catch(() => {})));
    const d = await getJSON(`/company/${TICKER}/chart?range=${range}`);
    const C = CH.C, x = d.dates;
    const noX = { x: { ...CH.xTicks } };

    CH.make("chPrice", { type: "line", data: { labels: x, datasets: [
        CH.line("Close", d.close, C.white, { borderWidth: 1.8 }),
        CH.line("SMA 50", d.sma50, C.amber), CH.line("SMA 200", d.sma200, C.magenta),
        CH.line("Boll +2σ", d.bb_upper, C.grey, { borderDash: [4, 3], borderWidth: 1 }),
        CH.line("Boll −2σ", d.bb_lower, C.grey, { borderDash: [4, 3], borderWidth: 1 }),
    ] }, options: { interaction: { mode: "index", intersect: false }, scales: { ...noX, y: { position: "right" } } } });

    CH.make("chVolume", { type: "bar", data: { labels: x, datasets: [{ label: "Volume", data: d.volume,
        backgroundColor: d.close.map((c, i) => (i && c >= d.close[i - 1] ? C.green : C.red)) }] },
        options: { plugins: { legend: { display: false } }, scales: { x: { display: false }, y: { position: "right", ticks: { maxTicksLimit: 3, callback: (v) => qty(v) } } } } });

    CH.make("chRsi", { type: "line", data: { labels: x, datasets: [
        CH.line("RSI", d.rsi, C.cyan, { borderWidth: 1.6 }),
        CH.line("70", x.map(() => 70), C.red, { borderDash: [4, 3], borderWidth: 1 }),
        CH.line("30", x.map(() => 30), C.green, { borderDash: [4, 3], borderWidth: 1 }),
    ] }, options: { plugins: { legend: { display: false } }, scales: { ...noX, y: { min: 0, max: 100, position: "right" } } } });

    CH.make("chMacd", { type: "bar", data: { labels: x, datasets: [
        { type: "bar", label: "Histogram", data: d.macd_hist, backgroundColor: d.macd_hist.map((v) => (v >= 0 ? C.green : C.red)) },
        CH.line("MACD", d.macd, C.cyan), CH.line("Signal", d.macd_signal, C.yellow),
    ] }, options: { scales: { ...noX, y: { position: "right" } } } });

    const h = d.returns_histogram;
    CH.make("chDist", { type: "bar", data: { labels: h.bins.map((b) => ((b.from + b.to) / 2).toFixed(1)),
        datasets: [{ label: "Days", data: h.bins.map((b) => b.count), backgroundColor: h.bins.map((b) => ((b.from + b.to) / 2 >= 0 ? C.green : C.red)) }] },
        options: { plugins: { legend: { display: false } }, scales: { x: { title: { display: true, text: "daily return %" }, ticks: { maxTicksLimit: 10 } } } } });
    $("distNote").textContent = `n=${h.n} · mean ${h.mean}% · σ ${h.std}% · skew ${h.skew} · excess kurt ${h.kurtosis}`;

    CH.make("chDd", { type: "line", data: { labels: x, datasets: [CH.line("Drawdown %", d.drawdown, C.red, { fill: true, backgroundColor: "rgba(255,59,48,0.25)" })] },
        options: { plugins: { legend: { display: false } }, scales: { ...noX, y: { position: "right" } } } });
}

/* ---------- option charts (from the loaded chain) ---------- */
function renderOptionCharts() {
    const C = CH.C, rows = CHAIN.chain, labels = rows.map((r) => r.strike);
    CH.make("chOi", { type: "bar", data: { labels, datasets: [
        { label: "Call OI", data: rows.map((r) => r.CE?.oi || 0), backgroundColor: C.green },
        { label: "Put OI", data: rows.map((r) => r.PE?.oi || 0), backgroundColor: C.red },
    ] }, options: { scales: { x: { title: { display: true, text: `strike · spot ₹${num(CHAIN.spot)} · max pain ₹${num(CHAIN.summary.max_pain, 0)}` } }, y: { ticks: { callback: (v) => qty(v) } } } } });
    CH.make("chSmile", { type: "line", data: { labels, datasets: [
        CH.line("Call IV %", rows.map((r) => r.CE?.iv ?? null), C.green, { spanGaps: true, pointRadius: 2 }),
        CH.line("Put IV %", rows.map((r) => r.PE?.iv ?? null), C.red, { spanGaps: true, pointRadius: 2 }),
    ] }, options: { scales: { x: { title: { display: true, text: "strike" } }, y: { title: { display: true, text: "IV %" } } } } });
}

/* ---------- buy / sell order ticket ---------- */
let OM = { side: "BUY", type: "MARKET" };
function openOrder(side) {
    OM = { side, type: "MARKET" };
    $("omTicker").textContent = `${TICKER} @ ₹${num(QUOTE.price)}`;
    $("omQty").value = 1; $("omPrice").value = QUOTE.price.toFixed(2); $("omMsg").textContent = "";
    $("orderModal").classList.remove("hidden");
    syncOrder();
}
function syncOrder() {
    $("omBuy").classList.toggle("on", OM.side === "BUY"); $("omSell").classList.toggle("on", OM.side === "SELL");
    $("omMkt").classList.toggle("on", OM.type === "MARKET"); $("omLmt").classList.toggle("on", OM.type === "LIMIT");
    $("omPriceRow").classList.toggle("hidden", OM.type !== "LIMIT");
    const q = parseInt($("omQty").value) || 0;
    const px = OM.type === "LIMIT" ? parseFloat($("omPrice").value) || 0 : QUOTE.price;
    const btn = $("omSubmit");
    btn.className = `btn-go ${OM.side === "BUY" ? "buy" : "sell"}`;
    btn.innerHTML = `&gt;&gt; VALIDATE &amp; RECORD ${OM.side} ORDER &lt;&lt;`;
    $("omSummary").innerHTML = dl([["Last price", `₹${num(QUOTE.price)}`], ["Order price", OM.type === "LIMIT" ? `₹${num(px)}` : "MARKET (≈ last)"],
        ["Quantity", int(q)], ["Estimated value", `₹${num(px * q)}`]]);
}
$("omClose").addEventListener("click", (e) => { e.preventDefault(); $("orderModal").classList.add("hidden"); });
$("orderModal").addEventListener("click", (e) => { if (e.target.id === "orderModal") $("orderModal").classList.add("hidden"); });
$("omBuy").addEventListener("click", () => { OM.side = "BUY"; syncOrder(); });
$("omSell").addEventListener("click", () => { OM.side = "SELL"; syncOrder(); });
$("omMkt").addEventListener("click", () => { OM.type = "MARKET"; syncOrder(); });
$("omLmt").addEventListener("click", () => { OM.type = "LIMIT"; syncOrder(); });
$("omQty").addEventListener("input", syncOrder); $("omPrice").addEventListener("input", syncOrder);
$("omSubmit").addEventListener("click", async () => {
    const msg = $("omMsg");
    const body = { ticker: TICKER, side: OM.side, order_type: OM.type, quantity: parseInt($("omQty").value) || 0 };
    if (OM.type === "LIMIT") body.limit_price = parseFloat($("omPrice").value);
    try {
        const r = await fetch("/orders", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
        const d = await r.json();
        if (!r.ok) throw new Error(typeof d.detail === "string" ? d.detail : "Invalid order (check quantity / price)");
        msg.className = "om-msg yl";
        msg.textContent = `RECORDED #${d.id} · ${d.side} ${d.quantity} ${TICKER} · est. ₹${num(d.estimated_value)} · NOT SENT TO BROKER`;
    } catch (e) { msg.className = "om-msg down"; msg.textContent = `REJECTED: ${e.message}`; }
});


/* ---------- keyboard shortcuts (see keys.js; '?' lists them) ---------- */
const orderOpen = () => !$("orderModal").classList.contains("hidden");
const closeOrder = () => $("orderModal").classList.add("hidden");
function stepStrike(d) {
    if (!CHAIN) return;
    const strikes = CHAIN.chain.map((r) => r.strike);
    const i = strikes.indexOf(SELECTED);
    SELECTED = strikes[Math.max(0, Math.min(strikes.length - 1, (i === -1 ? strikes.indexOf(CHAIN.atm_strike) : i) + d))];
    renderChain();
    const row = document.querySelector(".chain tr.sel");
    if (row) row.scrollIntoView({ block: "nearest" });
}
function stepExpiry(d) {
    if (!CHAIN) return;
    const i = CHAIN.expiries.indexOf(EXPIRY);
    const next = CHAIN.expiries[i + d];
    if (next) loadChain(next);
}
function stepStock(d) {
    const i = TICKER_LIST.indexOf(TICKER);
    if (i === -1 || !TICKER_LIST.length) return;
    location.href = `/stock?ticker=${encodeURIComponent(TICKER_LIST[(i + d + TICKER_LIST.length) % TICKER_LIST.length])}`;
}
function setupKeyboard() {
    Keys.addCloser(() => { if (!orderOpen()) return false; closeOrder(); return true; });
    const side = (v) => () => { if (!QUOTE) return; if (orderOpen()) { OM.side = v; syncOrder(); } else openOrder(v); };
    const rng = (r) => () => { if (!orderOpen()) loadCharts(r).catch(() => {}); };
    Keys.bind([
        { key: "b", desc: "Buy ticket (in a ticket: switch to BUY)", fn: side("BUY") },
        { key: "s", desc: "Sell ticket (in a ticket: switch to SELL)", fn: side("SELL") },
        { key: "m", desc: "In a ticket: MARKET order", fn: () => { if (orderOpen()) { OM.type = "MARKET"; syncOrder(); } } },
        { key: "l", desc: "In a ticket: LIMIT order", fn: () => { if (orderOpen()) { OM.type = "LIMIT"; syncOrder(); } } },
        { key: "1", desc: "Chart range 3M", fn: rng("3mo") },
        { key: "2", desc: "Chart range 6M", fn: rng("6mo") },
        { key: "3", desc: "Chart range 1Y", fn: rng("1y") },
        { key: "4", desc: "Chart range 2Y", fn: rng("2y") },
        { key: "]", desc: "Next option expiry", fn: () => { if (!orderOpen()) stepExpiry(1); } },
        { key: "[", desc: "Previous option expiry", fn: () => { if (!orderOpen()) stepExpiry(-1); } },
        { key: ["j", "ArrowDown"], desc: "Option chain: next strike", fn: () => { if (!orderOpen()) stepStrike(1); } },
        { key: ["k", "ArrowUp"], desc: "Option chain: previous strike", fn: () => { if (!orderOpen()) stepStrike(-1); } },
        { key: "n", desc: "Next stock in Nifty 50 list", fn: () => { if (!orderOpen()) stepStock(1); } },
        { key: "p", desc: "Previous stock in Nifty 50 list", fn: () => { if (!orderOpen()) stepStock(-1); } },
        { key: "c", group: "Navigate", desc: "Compare this stock with peers", fn: () => { location.href = `/compare-view?tickers=${TICKER}`; } },
    ]);
}


/* ---------- live updates (only while the market is open) ---------- */
const liveTimers = {};
function every(name, ms, fn) {
    clearInterval(liveTimers[name]);
    // Skip ticks while the tab is hidden (saves the broker API rate budget); a visibility handler catches up.
    liveTimers[name] = setInterval(() => { if (!document.hidden) Promise.resolve(fn()).catch(() => {}); }, ms);
}
function stopLive() { Object.values(liveTimers).forEach(clearInterval); }

async function refreshChain() {
    if (!CHAIN) return;
    const d = await getJSON(`/company/${TICKER}/option-chain?expiry=${encodeURIComponent(EXPIRY)}`);
    CHAIN = d;
    if (!d.chain.some((r) => r.strike === SELECTED)) SELECTED = d.atm_strike; // keep the user's selected strike
    renderChain();
}

function startLive() {
    every("quote", 5000, () => loadQuote(false));       // server refreshes Angel One quotes every 5s
    every("depth", 5000, loadDepth);
    every("fut", 30000, loadFutures);                    // option chain/futures are cached server-side for 30s
    every("chain", 30000, refreshChain);
    every("tech", 60000, loadTech);
    every("news", 600000, loadSignal);
    every("charts", 300000, () => loadCharts(CHART_RANGE)); // Yahoo daily bars: refreshed every 5 min
}

async function checkMarket() {
    const was = MARKET_OPEN;
    try { MARKET_OPEN = (await getJSON("/stocks/status")).is_open || FORCE_POLL; } catch (e) { return; }
    if (MARKET_OPEN && !was) startLive();
    if (!MARKET_OPEN && was) { stopLive(); loadQuote(false).catch(() => {}); }
}
document.addEventListener("visibilitychange", () => {
    if (!document.hidden && MARKET_OPEN) { loadQuote(false).catch(() => {}); loadDepth().catch(() => {}); }
});

/* ---------- boot ---------- */
(function init() {
    setupKeyboard();
    if (!TICKER) { $("strip").textContent = "NO TICKER SPECIFIED"; return; }
    document.title = `FinNSA - ${TICKER}`;
    $("titleTicker").textContent = TICKER;
    // Quote first: it tells us whether the market is open (starts live loops) and gives analyst-target upside a price.
    loadQuote()
        .catch((e) => { $("strip").textContent = e.message; })
        .then(() => {
            if (MARKET_OPEN) startLive();
            setInterval(checkMarket, 60000);   // notice when the market opens/closes while the page stays open
            return loadGovernance().catch((e) => { fail("peopleBox", e); fail("holdBox", e); });
        });
    loadStats().catch((e) => fail("statsBox", e));
    loadSignal().catch((e) => { fail("signalBox", e); fail("newsBox", e); });
    loadTech().catch((e) => fail("techBox", e));
    loadDepth().catch((e) => fail("depthBox", e));
    loadFundamentals().catch((e) => { fail("fundBox", e); fail("chartBox", e); });
    // Angel One calls are rate-limited server-side; stagger them so the page doesn't queue behind the chain.
    loadFutures().catch((e) => fail("futBox", e));
    loadChain().catch((e) => fail("chainBox", e));
    loadCharts("1y").catch((e) => { $("rangeTabs").innerHTML = `<span class="down">CHART DATA UNAVAILABLE: ${esc(e.message)}</span>`; });
})();
