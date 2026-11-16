/* Guided tour: spotlights one part of the page at a time and explains it.
   Start with the header [T] TOUR button or the T key. Arrow keys / Enter / Space step, Q or Esc ends. */
(() => {
    const page = (document.getElementById("appHeader") || {}).dataset?.page || "board";

    // sel = CSS selector of the thing to highlight. panel:true highlights the whole surrounding panel instead.
    const STEPS = {
        board: [
            { sel: "#hdrBroker", title: "Broker connection", text: "Shows whether FinNSA is connected to your <b>Angel One SmartAPI</b> account. <b>Green</b> = live exchange data. <b>Red</b> = not connected, so the app falls back to delayed Yahoo Finance prices and the order book, futures and option chain are unavailable. Click it (or press <b>G</b>) to connect; the form explains each credential." },
            { sel: ".hdr-right", title: "Clock & market status", text: "India time (IST) and whether NSE is open (Mon–Fri, 9:15–15:30). Pages refresh automatically <b>only while the market is open</b>. This check knows weekends but not exchange holidays." },
            { sel: "#hdrIdx", title: "Index ticker", text: "<b>Nifty 50</b>, <b>Nifty Bank</b> and <b>Sensex</b>: the broad market. Green ▲ / red ▼ is the change versus the previous close." },
            { sel: ".search-prompt-wrapper", title: "Search", text: "Type a symbol, company or sector to filter the table. Press <b>/</b> to jump here, then <b>Enter</b> to select the first match." },
            { sel: "#sectorChips", title: "Sector filters", text: "Narrow the board to one sector. <b>[</b> and <b>]</b> step through them, <b>A</b> shows all 50. Sector tags are this app's own groupings, not an official classification." },
            { sel: ".term-table thead", title: "Reading the columns", text: "<b>Price</b> is the last traded price. <b>24H change</b> is versus the previous close. <b>Bid / Ask</b> is the best resting buy and sell price in the exchange order book (blank when the market is closed and no orders are resting). <b>Volume</b> is shares traded today. <b>Day range</b> is today's high / low." },
            { sel: ".term-table tbody tr:first-child", title: "Open a stock", text: "<b>Click any row</b> (or select it with <b>J / K</b> and press <b>O</b>) to open that company's page: charts, news signal, fundamentals, order book, futures and options." },
            { sel: ".term-table tbody tr:first-child .term-action-group", title: "BUY / SELL", text: "Opens an order ticket. It checks your order against the live price, then <b>records it locally only</b>. Nothing is sent to a broker or the exchange." },
            { sel: ".hdr-btns", title: "Help is always here", text: "<b>[T] TOUR</b> replays this walkthrough on any page. <b>[?] KEYS</b> lists every keyboard shortcut. Use <b>H</b> board, <b>C</b> compare, <b>D</b> datasets." },
        ],
        stock: [
            { sel: "#strip", title: "Quote bar", text: "Live price, change, day range and volume, with the market state and update time. The price flashes <b>green/red</b> when it ticks. <b>BUY / SELL</b> (or <b>B / S</b>) open the order ticket; <b>N / P</b> jump to the next/previous stock." },
            { sel: "#chPrice", panel: true, title: "Price chart", text: "Daily closes with the <b>50-day</b> and <b>200-day</b> moving averages (trend) and <b>Bollinger bands</b> (±2 standard deviations; price outside the band is unusually stretched). Pick a range with <b>1–4</b>. Source: Yahoo Finance, so it can lag the live quote." },
            { sel: "#chRsi", panel: true, title: "RSI (14)", text: "Relative Strength Index, 0–100. Above <b>70</b> is traditionally 'overbought', below <b>30</b> 'oversold'. It measures recent momentum; it is a gauge, not a forecast." },
            { sel: "#chMacd", panel: true, title: "MACD", text: "Compares a fast and a slow moving average. When the <b>MACD line</b> crosses above its <b>signal line</b> (histogram turns positive) momentum is rising; below, falling." },
            { sel: "#chDist", panel: true, title: "Returns distribution", text: "How the daily % moves were spread over the chosen period. The header shows mean, standard deviation (σ, the typical daily swing), <b>skew</b> (lean to big gains or losses) and <b>excess kurtosis</b> (how fat the tails are: how often extreme days happen)." },
            { sel: "#chDd", panel: true, title: "Drawdown", text: "How far the price sits below its previous peak. A deep, long red area means a painful period for anyone who bought at the top." },
            { sel: "#statsBox", panel: true, title: "Statistics", text: "Trailing returns, annualised <b>volatility</b> (higher = bumpier), <b>max drawdown</b> over a year, moving averages and average volume, all computed from Yahoo's daily prices." },
            { sel: "#signalBox", panel: true, title: "News signal", text: "Recent headlines (Google News) scored by <b>FinBERT</b>, an open-source finance sentiment model, with newer headlines weighted more. <b>BULLISH / NEUTRAL / BEARISH</b> describes the <i>tone of the news</i>. It does not predict the price." },
            { sel: "#techBox", panel: true, title: "Technicals", text: "Today's RSI, MACD and <b>VWAP</b> (the average price weighted by volume for the last session; trading above it is read as strength)." },
            { sel: "#depthBox", panel: true, title: "Market depth: buy/sell", text: "The exchange order book, 5 levels each side. <b>BUY (bid)</b> is what buyers will pay; <b>SELL (ask)</b> is what sellers want. The gap between the best bid and ask is the <b>spread</b>. Bars show quantity; more size on one side hints at pressure. Outside market hours it is nearly empty." },
            { sel: "#futBox", panel: true, title: "Futures", text: "Contracts to buy/sell the stock at a future date. <b>Basis</b> = futures price − spot; roughly the cost of carrying the position until expiry. <b>OI</b> is open interest: contracts still open." },
            { sel: "#derivBox", panel: true, title: "Derivatives statistics", text: "<b>PCR</b> (put-call ratio) = put open interest ÷ call open interest: above 1 means more puts than calls. <b>Max pain</b> is the strike where option buyers collectively lose most at expiry. <b>ATM IV</b> is the market's expected volatility, from at-the-money options. Computed over the strikes shown." },
            { sel: "#chainBox", panel: true, title: "Option chain", text: "Every strike: <b>calls (CE)</b> on the left, <b>puts (PE)</b> on the right, <b>strike</b> in the middle. Shaded cells are <b>in the money</b>. Prices, OI, volume and bid/ask come from the exchange; <b>IV and Greeks are computed</b> by FinNSA with Black-Scholes. Tabs switch expiry (<b>[ ]</b>); <b>J / K</b> move the strike." },
            { sel: "#chOi", panel: true, title: "Open interest by strike", text: "Where traders have positioned. Big <b>call</b> OI (green) above the price is often treated as resistance; big <b>put</b> OI (red) below as support. It describes positions, not direction." },
            { sel: "#chSmile", panel: true, title: "Implied-volatility smile", text: "IV across strikes. Deep out-of-the-money options usually price higher volatility (the 'smile'). Strikes with no trades are left blank because their last price is stale." },
            { sel: "#greeksBox", panel: true, title: "Greeks", text: "<b>Delta</b>: option price change per ₹1 move in the stock. <b>Gamma</b>: how fast delta changes. <b>Theta</b>: value lost per day from time passing. <b>Vega</b>: change per 1-point rise in volatility. Click any chain row to inspect that strike." },
            { sel: "#holdBox", panel: true, title: "Holdings & analysts", text: "Share held by insiders/promoters and institutions, plus analyst consensus and price targets from third-party data. The exchange-filed shareholding pattern is the authoritative source." },
            { sel: "#peopleBox", panel: true, title: "Officers & management", text: "Key executives with title, age and pay. This is <b>not the full board</b> (independent directors are missing). Use the NSE/BSE links under the table for the official governance filings." },
            { sel: "#fundBox", panel: true, title: "Fundamentals", text: "Market cap, revenue, margins, <b>P/E</b> (price ÷ earnings), P/B, ROE and debt/equity, from Yahoo Finance's aggregation of company filings. Banks report 'total income', which is not comparable to other companies' revenue." },
            { sel: "#chartBox", panel: true, title: "Revenue & net income", text: "Annual revenue (█) and net income (▒) side by side. Watch whether profit grows with sales or shrinks as a share of them." },
            { sel: "#newsBox", panel: true, title: "Headlines", text: "The actual headlines behind the signal, each labelled positive / negative / neutral with its score. Click one to read it." },
        ],
        compare: [
            { sel: "#picker", panel: true, title: "Pick stocks", text: "Choose 2–8 stocks to compare. Remove one by clicking it; add with the dropdown (focus it with <b>/</b>). Change the period with <b>1–5</b>." },
            { sel: "#chPerf", panel: true, title: "Relative performance", text: "Every stock is rebased to <b>100</b> on the first common date, so the lines show who gained or lost more over the same period regardless of share price." },
            { sel: "#chRisk", panel: true, title: "Risk vs return", text: "Each dot is a stock: right = more volatile, up = higher return. The best spot is top-left (more return for less swing)." },
            { sel: "#corrBox", panel: true, title: "Correlation", text: "How similarly daily moves line up: <b>1</b> = move together, <b>0</b> = unrelated. Holding stocks with low correlation diversifies risk." },
            { sel: "#statTable", panel: true, title: "Statistics & trade buttons", text: "Return, volatility, max drawdown and return-per-unit-of-risk for each pick. <b>BUY / SELL</b> open that stock's order ticket." },
            { sel: "#newsProgress", panel: true, title: "Sector vs news signal", text: "FinNSA scores news for all 50 stocks in the background (about a minute after a restart), then compares sectors. The charts below fill in as scores arrive." },
            { sel: "#chSecBar", panel: true, title: "Sector return vs news score", text: "Cyan bars: the sector's average 1-month price return. Yellow bars: its average news tone (−1 bearish to +1 bullish). Do headlines and prices agree?" },
            { sel: "#chSecMix", panel: true, title: "News mix by sector", text: "How many stocks in each sector have bullish, neutral or bearish news right now." },
            { sel: "#chScatter", panel: true, title: "News vs return, every stock", text: "Each dot is one stock, coloured by sector. The header shows the correlation (r). A weak r means news tone and past performance don't line up much, and it says nothing about the future." },
            { sel: "#secTable", panel: true, title: "Sector table", text: "The numbers behind the charts. <b>(n/m)</b> beside a news score is how many stocks in that sector are scored so far." },
        ],
        datasets: [
            { sel: ".dataset-list", panel: true, title: "Training datasets", text: "The public datasets and models the sentiment engine is based on, with links to the sources." },
        ],
    };

    let steps = [], idx = 0, hole = null, pop = null, active = false;

    function target(step) {
        const el = document.querySelector(step.sel);
        if (!el) return null;
        return step.panel ? (el.closest(".panel, .term-box") || el) : el;
    }

    function place() {
        const step = steps[idx], el = target(step);
        if (!el) return;
        const r = el.getBoundingClientRect(), pad = 5, vw = innerWidth, vh = innerHeight;
        const top = Math.max(2, r.top - pad), left = Math.max(2, r.left - pad);
        const w = Math.min(vw - 4, r.right + pad) - left, h = Math.min(vh - 4, r.bottom + pad) - top;
        Object.assign(hole.style, { top: top + "px", left: left + "px", width: w + "px", height: h + "px" });

        const pw = Math.min(380, vw * 0.92), ph = pop.offsetHeight;
        let pt, pl = Math.min(Math.max(8, left + w / 2 - pw / 2), vw - pw - 8);
        if (top + h + ph + 14 < vh) pt = top + h + 10;            // below
        else if (top - ph - 14 > 0) pt = top - ph - 10;            // above
        else { pt = Math.max(8, Math.min(vh - ph - 8, top + 12)); pl = left + w + 12 < vw - pw ? left + w + 12 : Math.max(8, left + 12); } // beside/inside tall targets
        Object.assign(pop.style, { top: pt + "px", left: pl + "px" });
    }

    function show() {
        // skip steps whose target isn't on the page (e.g. data failed to load)
        while (idx < steps.length && !target(steps[idx])) idx++;
        if (idx >= steps.length) return end();
        const step = steps[idx], n = steps.length;
        const el = target(step);
        el.scrollIntoView({ block: "center", behavior: "instant" });
        pop.innerHTML = `<div class="tt"><span>${idx + 1} / ${n} ═ ${step.title.toUpperCase()}</span><span>[Q] END</span></div>
            <div class="tb">${step.text}</div>
            <div class="tf"><span class="dots">${steps.map((_, i) => `<span class="${i === idx ? "on" : ""}">■</span>`).join("")}</span>
            <button id="tourBack" ${idx === 0 ? "disabled style='opacity:.4'" : ""}>← BACK</button>
            <button id="tourNext" class="primary">${idx === n - 1 ? "FINISH ✓" : "NEXT →"}</button></div>`;
        pop.querySelector(".tt span:last-child").onclick = end;
        $("tourBack").onclick = () => go(-1);
        $("tourNext").onclick = () => go(1);
        requestAnimationFrame(place);
        setTimeout(place, 120);   // after smooth layout / lazy content
    }
    const $ = (id) => document.getElementById(id);
    function go(d) { idx += d; if (idx < 0) idx = 0; if (idx >= steps.length) return end(); show(); }

    function onKey(e) {
        if (!active) return;
        const k = e.key;
        if (["ArrowRight", "Enter", " ", "n"].includes(k)) go(1);
        else if (["ArrowLeft", "Backspace", "p"].includes(k)) go(-1);
        else if (k === "Escape" || k.toLowerCase() === "q") end();
        else if (e.metaKey || e.ctrlKey || e.altKey) return;   // leave browser shortcuts (reload, copy…) alone
        e.preventDefault(); e.stopPropagation();   // swallow every other key so page shortcuts can't fire mid-tour
    }

    function start() {
        if (active) return;
        // close any other overlay first
        steps = STEPS[page] || STEPS.board; idx = 0; active = true;
        hole = document.createElement("div"); hole.className = "tour-hole";
        pop = document.createElement("div"); pop.className = "tour-pop";
        document.body.append(hole, pop);
        document.addEventListener("keydown", onKey, true);
        addEventListener("resize", place); addEventListener("scroll", place, true);
        try { localStorage.setItem("finnsa.tour." + page, "1"); } catch (e) { /* private mode */ }
        document.querySelector(".tour-toast")?.remove();
        show();
    }
    function end() {
        if (!active) return false;
        active = false;
        hole.remove(); pop.remove();
        document.removeEventListener("keydown", onKey, true);
        removeEventListener("resize", place); removeEventListener("scroll", place, true);
        window.scrollTo({ top: 0, behavior: "instant" });
        return true;
    }

    document.getElementById("hdrTour")?.addEventListener("click", start);
    if (typeof Keys !== "undefined") {
        Keys.bind([{ key: "t", group: "Navigate", desc: "Guided tour of this page", fn: start }]);
        Keys.addCloser(end);
    }

    // first visit to a page: a gentle, dismissible hint (no auto-start)
    let seen = false;
    try { seen = !!localStorage.getItem("finnsa.tour." + page); } catch (e) { /* ignore */ }
    if (!seen) {
        document.getElementById("hdrTour")?.classList.add("pulse");
        setTimeout(() => {
            if (active || document.querySelector(".tour-toast")) return;
            const t = document.createElement("div");
            t.className = "tour-toast";
            t.innerHTML = `New here? Press <b>T</b> or <a id="tourToastGo">take the 1-minute tour</a>. <a id="tourToastX" style="float:right;color:#a06f00">✕</a>`;
            document.body.appendChild(t);
            $("tourToastGo").onclick = start; $("tourToastX").onclick = () => { t.remove(); try { localStorage.setItem("finnsa.tour." + page, "1"); } catch (e) {} document.getElementById("hdrTour")?.classList.remove("pulse"); };
            setTimeout(() => t.remove(), 15000);
        }, 3500);
    }
    window.Tour = { start, end };
})();
