// FinNSA Terminal GUI Engine v2.0

let allStocks = [];
let previousPrices = {};
let selectedSector = "ALL";
let activeStockForModal = null;
let activeOrderType = "BUY";
let kbSelected = null;      // ticker highlighted by keyboard navigation
let visibleTickers = [];    // tickers currently shown (after filters), in row order

document.addEventListener("DOMContentLoaded", () => {
    // 1. Initialize Ambient Particle Canvas Background
    initAmbientParticleCanvas();

    // 2. Fetch market status & initial stock data
    fetchMarketStatus();
    fetchGlobalMarkets();
    fetchStocks();

    // 3. Start 2.5s streaming poll interval
    setInterval(() => {
        fetchMarketStatus();
        fetchGlobalMarkets();
        fetchStocks();
    }, 2500);


    // Filter Chips
    document.querySelectorAll(".term-btn").forEach(chip => {
        chip.addEventListener("click", (e) => {
            document.querySelectorAll(".term-btn").forEach(c => c.classList.remove("active"));
            e.target.classList.add("active");
            selectedSector = e.target.getAttribute("data-sector");
            renderTable();
        });
    });

    // Search Input Filter
    document.getElementById("searchInput").addEventListener("input", () => {
        renderTable();
    });

    // Setup Order Execution Modal
    setupTradingModal();
    setupKeyboard();
});

// ---- Keyboard shortcuts (see keys.js; '?' lists them) ----
function tradingModalOpen() {
    return !document.getElementById("tradingModal").classList.contains("hidden");
}

function moveSelection(delta) {
    if (!visibleTickers.length) return;
    const i = visibleTickers.indexOf(kbSelected);
    const next = i === -1 ? (delta > 0 ? 0 : visibleTickers.length - 1) : Math.max(0, Math.min(visibleTickers.length - 1, i + delta));
    kbSelected = visibleTickers[next];
    renderTable();
    const row = document.querySelector("tr.kb-sel");
    if (row) row.scrollIntoView({ block: "nearest" });
}

function cycleSector(delta) {
    const chips = [...document.querySelectorAll("#sectorChips .term-btn")];
    const i = chips.findIndex(c => c.classList.contains("active"));
    chips[(i + delta + chips.length) % chips.length].click();
}

function setupKeyboard() {
    const search = document.getElementById("searchInput");
    search.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {            // jump from the search box straight to the first match
            kbSelected = visibleTickers[0] || null;
            renderTable();
            search.blur();
        }
    });

    Keys.addCloser(() => {
        if (!tradingModalOpen()) return false;
        document.getElementById("tradingModal").classList.add("hidden");
        return true;
    });

    const order = (side) => {
        if (tradingModalOpen()) return setModalOrderType(side);
        if (kbSelected) openTradingModal(kbSelected, side);
    };
    const nav = (d) => () => { if (!tradingModalOpen()) moveSelection(d); };

    Keys.bind([
        { key: "/", desc: "Focus search", fn: () => search.focus() },
        { key: ["j", "ArrowDown"], desc: "Select next stock", fn: nav(1) },
        { key: ["k", "ArrowUp"], desc: "Select previous stock", fn: nav(-1) },
        { key: ["o", "Enter"], desc: "Open selected stock", fn: () => { if (!tradingModalOpen() && kbSelected) location.href = `/stock?ticker=${encodeURIComponent(kbSelected.replace(".NS", ""))}`; } },
        { key: "b", desc: "Buy ticket for selected stock (in a ticket: switch to BUY)", fn: () => order("BUY") },
        { key: "s", desc: "Sell ticket for selected stock (in a ticket: switch to SELL)", fn: () => order("SELL") },
        { key: "]", desc: "Next sector filter", fn: () => cycleSector(1) },
        { key: "[", desc: "Previous sector filter", fn: () => cycleSector(-1) },
        { key: "a", desc: "Show all 50 stocks", fn: () => document.querySelector('#sectorChips [data-sector="ALL"]').click() },
    ]);
}

// Check NSE/BSE Market Open Hours Status
async function fetchMarketStatus() {
    try {
        const response = await fetch("/stocks/status");
        if (!response.ok) return;
        const data = await response.json();
        const footerNoteEl = document.getElementById("footerMarketNote");
        if (footerNoteEl) {
            footerNoteEl.textContent = data.is_open
                ? `NSE/BSE STATUS: TRADING HOURS ACTIVE (${data.ist_time})`
                : `NSE/BSE STATUS: OFF-HOURS // ${data.ist_time} (LAST TRADED PRICES)`;
        }
    } catch (err) {
        console.error("Error fetching market status:", err);
    }
}

// Ambient Canvas Particle Animation (Lightweight Floating Node Constellation)
// initAmbientParticleCanvas() now lives in ambient-canvas.js (shared with datasets.html)

// 1. Fetch India Feed (NIFTY 50, NIFTY BANK, SENSEX)
async function fetchGlobalMarkets() { /* index ticker now lives in the shared header (header.js) */ }

// 2. Fetch all 50 Nifty 50 Stocks
async function fetchStocks() {
    try {
        const url = "/stocks";
        const response = await fetch(url);
        if (!response.ok) return;
        const stocks = await response.json();

        // Track price changes for tick pulse animations
        stocks.forEach(st => {
            const prev = previousPrices[st.ticker];
            if (prev !== undefined) {
                if (st.price > prev) st._tick = "up";
                else if (st.price < prev) st._tick = "down";
            }
            previousPrices[st.ticker] = st.price;
        });

        allStocks = stocks;
        renderTable();
    } catch (err) {
        console.error("Error fetching Nifty 50 stocks:", err);
    }
}

// 3. Render Terminal Data Matrix Board
function renderTable() {
    const tbody = document.getElementById("stocksTableBody");
    const searchQuery = document.getElementById("searchInput").value.toLowerCase().trim();
    
    const filtered = allStocks.filter(st => {
        const matchesSector = (selectedSector === "ALL") || (st.sector === selectedSector);
        const matchesSearch = st.ticker.toLowerCase().includes(searchQuery) || 
                              st.name.toLowerCase().includes(searchQuery) ||
                              st.sector.toLowerCase().includes(searchQuery);
        return matchesSector && matchesSearch;
    });

    visibleTickers = filtered.map(st => st.ticker);
    const badgeEl = document.getElementById("stockCountBadge");
    if (badgeEl) badgeEl.textContent = `[LOADED: ${filtered.length}/${allStocks.length}]`;

    tbody.innerHTML = "";
    filtered.forEach(st => {
        const tr = document.createElement("tr");
        tr.dataset.ticker = st.ticker;
        if (st.ticker === kbSelected) tr.classList.add("kb-sel");
        if (st._tick === "up") tr.classList.add("tick-up-green");
        else if (st._tick === "down") tr.classList.add("tick-down-red");

        const changeClass = st.change_percent >= 0 ? "up" : "down";
        const changeSign = st.change_percent >= 0 ? "+" : "";

        tr.style.cursor = "pointer";
        tr.title = "Open stock detail";
        tr.addEventListener("click", (e) => {
            if (e.target.closest(".btn-trade-term")) return; // BUY/SELL keep opening the order ticket
            window.location.href = `/stock?ticker=${encodeURIComponent(st.ticker.replace(".NS", ""))}`;
        });

        tr.innerHTML = `
            <td>
                <div style="display: flex; flex-direction: column;">
                    <span class="t-sym">${st.ticker.replace(".NS", "")}</span>
                    <span class="t-name">${st.name}</span>
                </div>
            </td>
            <td><span class="t-sec">${st.sector}</span></td>
            <td class="text-right" style="font-weight: 700; color: #ffffff;">₹${st.price.toLocaleString('en-IN', {minimumFractionDigits: 2})}</td>
            <td class="text-right">
                <span class="t-badge ${changeClass}">${changeSign}${st.change_percent}%</span>
            </td>
            <td class="text-right" style="font-size: 0.8125rem;">
                <span style="color: var(--matrix-green)">${st.bid ? "₹" + st.bid : "—"}</span> / <span style="color: var(--neon-red)">${st.ask ? "₹" + st.ask : "—"}</span>
            </td>
            <td class="text-right" style="color: var(--text-dim); font-size: 0.8125rem;">
                ${st.volume ? st.volume.toLocaleString('en-IN') : '—'}
            </td>
            <td class="text-right" style="color: var(--text-muted); font-size: 0.75rem;">
                ₹${st.day_high} / ₹${st.day_low}
            </td>
            <td class="text-center">
                <div class="term-action-group">
                    <button class="btn-trade-term buy" onclick="openTradingModal('${st.ticker}', 'BUY')">BUY</button>
                    <button class="btn-trade-term sell" onclick="openTradingModal('${st.ticker}', 'SELL')">SELL</button>
                </div>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

// 4. Order Execution Ticket Modal
function openTradingModal(ticker, orderType = "BUY") {
    const modal = document.getElementById("tradingModal");
    const stock = allStocks.find(s => s.ticker === ticker) || { ticker, name: ticker, sector: "Nifty 50", price: 1500.0 };

    activeStockForModal = stock;
    activeOrderType = orderType;

    document.getElementById("modalStockName").textContent = stock.ticker;
    document.getElementById("modalLivePrice").textContent = `₹${stock.price.toLocaleString('en-IN', {minimumFractionDigits: 2})}`;
    document.getElementById("orderPrice").value = stock.price.toFixed(2);
    document.getElementById("orderStatusMsg").textContent = "";

    setModalOrderType(orderType);
    updateOrderSummary();

    modal.classList.remove("hidden");
}

function setModalOrderType(type) {
    activeOrderType = type;
    const tabBuy = document.getElementById("tabBuy");
    const tabSell = document.getElementById("tabSell");
    const btnExec = document.getElementById("btnExecuteOrder");

    if (type === "BUY") {
        tabBuy.classList.add("active");
        tabSell.classList.remove("active");
        btnExec.className = "btn-execute-term buy";
        btnExec.textContent = `>> EXECUTE_BUY_ORDER <<`;
    } else {
        tabSell.classList.add("active");
        tabBuy.classList.remove("active");
        btnExec.className = "btn-execute-term sell";
        btnExec.textContent = `>> EXECUTE_SELL_ORDER <<`;
    }
}

function updateOrderSummary() {
    const qty = parseInt(document.getElementById("orderQty").value) || 1;
    const price = parseFloat(document.getElementById("orderPrice").value) || (activeStockForModal ? activeStockForModal.price : 1000);
    const total = qty * price;

    document.getElementById("summaryTotal").textContent = `₹${total.toLocaleString('en-IN', {minimumFractionDigits: 2})}`;
}

function setupTradingModal() {
    const modal = document.getElementById("tradingModal");
    document.getElementById("modalCloseBtn").addEventListener("click", () => {
        modal.classList.add("hidden");
    });

    document.getElementById("tabBuy").addEventListener("click", () => setModalOrderType("BUY"));
    document.getElementById("tabSell").addEventListener("click", () => setModalOrderType("SELL"));

    document.getElementById("orderQty").addEventListener("input", updateOrderSummary);
    document.getElementById("orderPrice").addEventListener("input", updateOrderSummary);

    document.getElementById("btnExecuteOrder").addEventListener("click", async () => {
        const status = document.getElementById("orderStatusMsg");
        const body = {
            ticker: activeStockForModal.ticker.replace(".NS", ""),
            side: activeOrderType,
            order_type: "LIMIT",
            quantity: parseInt(document.getElementById("orderQty").value) || 0,
            limit_price: parseFloat(document.getElementById("orderPrice").value),
        };
        try {
            const r = await fetch("/orders", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
            const d = await r.json();
            if (!r.ok) throw new Error(typeof d.detail === "string" ? d.detail : "Invalid order (check quantity / price)");
            status.style.color = "var(--amber-accent)";
            status.textContent = `[RECORDED #${d.id}]: ${d.side} ${d.quantity} ${body.ticker} @ limit ₹${body.limit_price} - NOT SENT TO BROKER`;
        } catch (e) {
            status.style.color = "var(--neon-red)";
            status.textContent = `[REJECTED]: ${e.message}`;
        }
    });
}
