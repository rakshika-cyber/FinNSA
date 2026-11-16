/* Shared header: brand, navigation, IST clock, market status, broker connection chip + connect modal, index ticker.
   Mounts into <div id="appHeader" data-page="board|stock|compare|datasets">. Requires keys.js loaded first. */
(() => {
    const mount = document.getElementById("appHeader");
    if (!mount) return;
    const page = mount.dataset.page || "board";
    const $ = (id) => document.getElementById(id);
    const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
    const num = (n, d = 2) => Number(n).toLocaleString("en-IN", { minimumFractionDigits: d, maximumFractionDigits: d });
    const on = (p) => (page === p ? "on" : "");

    mount.innerHTML = `
    <div class="hdr">
      <div class="hdr-top">
        <a class="hdr-brand" href="/"><span class="logo">▓▒░</span>FinNSA<span class="sub">TERMINAL v2.1 · NIFTY 50</span></a>
        <div class="hdr-right">
          <span id="hdrClock">--:--:-- IST</span>
          <span id="hdrMarket" class="chip">● MARKET …</span>
          <button id="hdrBroker" class="chip" title="Broker connection (press G)">○ BROKER …</button>
        </div>
      </div>
      <div class="hdr-nav">
        <nav>
          <a class="${on("board")}" href="/">[H] BOARD</a>
          <a class="${on("compare")}" id="cmpLink" href="/compare-view">[C] COMPARE</a>
          <a class="${on("datasets")}" href="/static/datasets.html">[D] DATASETS</a>
          ${page === "stock" ? '<span class="tab on">STOCK · <b id="titleTicker"></b></span>' : ""}
        </nav>
        <div class="hdr-idx" id="hdrIdx"></div>
        <div class="hdr-btns"><button id="hdrTour">[T] TOUR</button><button id="hdrKeys">[?] KEYS</button></div>
      </div>
    </div>`;
    $("hdrKeys").addEventListener("click", () => Keys.help());

    /* ---------- clock + market status + indices ---------- */
    const tick = () => { $("hdrClock").textContent = new Date().toLocaleTimeString("en-GB", { timeZone: "Asia/Kolkata" }) + " IST"; };
    tick(); setInterval(tick, 1000);

    async function getJSON(url, opts) {
        const r = await fetch(url, opts);
        const d = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(typeof d.detail === "string" ? d.detail : r.statusText);
        return d;
    }
    async function market() {
        try {
            const s = await getJSON("/stocks/status");
            const el = $("hdrMarket");
            el.className = "chip " + (s.is_open ? "up" : "down");
            el.textContent = s.is_open ? "● MARKET OPEN" : "● MARKET CLOSED";
            el.title = s.ist_time;
        } catch (e) { /* keep last */ }
    }
    async function indices() {
        if (document.hidden) return;
        try {
            const d = await getJSON("/stocks/global");
            $("hdrIdx").innerHTML = d.map((x) => `<span class="ix"><b>${esc(x.name.toUpperCase())}</b><span class="px">${num(x.price)}</span><span class="${x.change_percent >= 0 ? "up" : "down"}">${x.change_percent >= 0 ? "▲" : "▼"}${Math.abs(x.change_percent).toFixed(2)}%</span></span>`).join("");
        } catch (e) { /* keep last */ }
    }
    market(); indices(); setInterval(market, 30000); setInterval(indices, 5000);

    /* ---------- broker chip ---------- */
    let BROKER = { state: "CHECKING" };
    function renderChip() {
        const el = $("hdrBroker"), b = BROKER;
        const map = {
            CONNECTED: ["chip up", `● BROKER: CONNECTED · ${b.client || "ANGEL ONE"}`],
            CONNECTING: ["chip warn", "◌ BROKER: CONNECTING…"],
            ERROR: ["chip down", "▲ BROKER: ERROR · FIX [G]"],
            NOT_CONNECTED: ["chip down", "○ BROKER: NOT CONNECTED · CONNECT [G]"],
            CHECKING: ["chip", "○ BROKER …"],
        };
        const [cls, txt] = map[b.state] || map.CHECKING;
        el.className = cls; el.textContent = txt;
        el.title = b.state === "CONNECTED" ? "Live data from Angel One SmartAPI. Click to manage." : (b.fallback ? `Using ${b.fallback}. Click to connect.` : "Click to connect");
    }
    async function brokerStatus() {
        const was = BROKER.state;
        try { BROKER = await getJSON("/broker/status"); } catch (e) { BROKER = { state: "CHECKING" }; }
        if (BROKER.state === "CONNECTED" && was !== "CONNECTED") window.dispatchEvent(new Event("broker:connected"));
        renderChip();
        if (!$("bmBack").classList.contains("hidden")) renderModalStatus();
    }

    /* ---------- broker modal ---------- */
    const back = document.createElement("div");
    back.id = "bmBack"; back.className = "bm-back hidden";
    back.innerHTML = `
    <div class="bm" role="dialog" aria-label="Broker connection">
      <div class="bt"><span>BROKER CONNECTION ═ ANGEL ONE SMARTAPI</span><a id="bmClose">[Q] CLOSE</a></div>
      <div class="bb">
        <div class="stat" id="bmStat"></div>
        <div class="intro">
          Connecting lets FinNSA read <b>live prices, buy/sell order-book depth, futures and option chains</b> from your Angel One account
          through SmartAPI. Without it the app falls back to Yahoo Finance: delayed prices, and no depth, futures or options.<br>
          This app only <b>reads market data</b>. It never places orders with the broker; the BUY/SELL tickets are recorded locally only.
        </div>

        <form id="bmForm" autocomplete="off" class="bb" style="padding:0">
          <div class="field"><label for="bmKey">1 · API KEY</label>
            <input id="bmKey" type="password" autocomplete="off" spellcheck="false" placeholder="paste your SmartAPI key">
            <div class="help">Identifies <b>your app</b> to Angel One. Get it at <a href="https://smartapi.angelone.in/" target="_blank" rel="noopener noreferrer">smartapi.angelone.in</a> → log in → <b>My Apps</b> → <b>Create App</b> (type: Trading/Market data) → copy the <b>API Key</b>. It is a short random string. (You do not need the secret key.)</div></div>
          <div class="field"><label for="bmClient">2 · CLIENT CODE</label>
            <input id="bmClient" type="text" autocomplete="off" spellcheck="false" placeholder="e.g. A123456">
            <div class="help">Your Angel One <b>login ID</b> (the same ID you use in the Angel One app), usually a letter followed by digits.</div></div>
          <div class="field"><label for="bmPin">3 · PIN</label>
            <input id="bmPin" type="password" autocomplete="off" placeholder="your Angel One MPIN">
            <div class="help">Your <b>4-digit MPIN</b> for Angel One, not your email password.</div></div>
          <div class="field"><label for="bmTotp">4 · TOTP SECRET</label>
            <input id="bmTotp" type="password" autocomplete="off" spellcheck="false" placeholder="base32 text under the QR code">
            <div class="help">SmartAPI logins need a 6-digit code that changes every 30s. FinNSA generates it for you from a secret. Enable TOTP at <a href="https://smartapi.angelone.in/enable-totp" target="_blank" rel="noopener noreferrer">smartapi.angelone.in/enable-totp</a>, then copy the <b>text shown with the QR code</b> (letters A–Z and digits 2–7). It is <b>not</b> the 6-digit code itself.</div></div>
          <label class="chk"><input id="bmSave" type="checkbox" checked><span>Remember on this computer (saved in the project's <b>.env</b> file in plain text, owner-only permissions, git-ignored) so it reconnects after a restart. Untick to keep the credentials in memory only.</span></label>
          <div class="row">
            <button type="submit" class="btn go" id="bmGo">&gt;&gt; TEST &amp; CONNECT &lt;&lt;</button>
            <button type="button" class="btn danger hidden" id="bmDisc" style="display:none">DISCONNECT</button>
          </div>
          <div class="msg" id="bmMsg"></div>
        </form>

        <details><summary>How the connection works &amp; what happens to your credentials</summary>
          <ol>
            <li>Your browser sends the four values to <b>this local FinNSA server only</b> (it rejects requests from other machines and websites).</li>
            <li>The server logs in to Angel One's SmartAPI once to test them. If Angel One rejects them, nothing is changed and your existing connection stays.</li>
            <li>On success it keeps a session token in memory and uses it to poll quotes about every 5 seconds while the market is open (and once a minute when closed).</li>
            <li>The credentials are never sent back to the browser, never shown in logs, and never sent to any service other than Angel One.</li>
          </ol>
        </details>
        <details><summary>Troubleshooting</summary>
          <ul>
            <li><b>"Invalid totp and client combination"</b>: the TOTP secret or client code is wrong, or your computer's clock is off by more than ~30s.</li>
            <li><b>"Invalid API key"</b>: copy the key from <i>My Apps</i> again; make sure the app is active.</li>
            <li><b>"Access denied … exceeding access rate"</b>: Angel One limits calls to about one per second; wait a minute and retry.</li>
            <li>SmartAPI is for your own personal use; keep your credentials private and rotate them if you suspect exposure.</li>
          </ul>
        </details>
      </div>
    </div>`;
    document.body.appendChild(back);

    function renderModalStatus() {
        const b = BROKER;
        const m = { CONNECTED: ["#33ff33", "● CONNECTED"], CONNECTING: ["#ffff55", "◌ CONNECTING"], ERROR: ["#ff3b30", "▲ ERROR"], NOT_CONNECTED: ["#ff3b30", "○ NOT CONNECTED"], CHECKING: ["#ffb000", "○ CHECKING"] }[b.state] || ["#ffb000", b.state];
        $("bmStat").innerHTML = `<span class="dot" style="color:${m[0]}">${m[1]}</span>` +
            (b.state === "CONNECTED" ? `<span>client <b style="color:#fff">${esc(b.client)}</b></span><span>last data ${b.last_ok_seconds_ago ?? "?"}s ago</span>` : "") +
            (b.last_error ? `<span style="color:#ff3b30">${esc(b.last_error)}</span>` : "") +
            (b.fallback ? `<span style="color:#a06f00">using: ${esc(b.fallback)}</span>` : "");
        const connected = b.state !== "NOT_CONNECTED" && b.state !== "CHECKING";
        $("bmDisc").style.display = connected ? "" : "none";
        $("bmGo").innerHTML = connected ? "&gt;&gt; REPLACE CREDENTIALS &amp; RECONNECT &lt;&lt;" : "&gt;&gt; TEST &amp; CONNECT &lt;&lt;";
    }
    function openBroker() { back.classList.remove("hidden"); $("bmMsg").textContent = ""; brokerStatus(); setTimeout(() => $("bmKey").focus(), 50); }
    function closeBroker() {
        if (back.classList.contains("hidden")) return false;
        back.classList.add("hidden");
        ["bmKey", "bmClient", "bmPin", "bmTotp"].forEach((id) => ($(id).value = ""));   // never leave secrets in the DOM
        return true;
    }
    const msg = (t, ok) => { const m = $("bmMsg"); m.className = "msg " + (ok ? "ok" : "err"); m.textContent = t; };

    $("hdrBroker").addEventListener("click", openBroker);
    $("bmClose").addEventListener("click", closeBroker);
    back.addEventListener("click", (e) => { if (e.target === back) closeBroker(); });
    Keys.addCloser(closeBroker);
    Keys.bind([{ key: "g", group: "Navigate", desc: "Broker connection (connect SmartAPI)", fn: openBroker }]);

    $("bmForm").addEventListener("submit", async (e) => {
        e.preventDefault();
        const body = { api_key: $("bmKey").value, client_id: $("bmClient").value, pin: $("bmPin").value, totp_secret: $("bmTotp").value, persist: $("bmSave").checked };
        if (!body.api_key.trim() || !body.client_id.trim() || !body.pin.trim() || !body.totp_secret.trim()) return msg("Fill in all four fields.", false);
        $("bmGo").disabled = true; msg("Logging in to Angel One…", true);
        try {
            const r = await getJSON("/broker/connect", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
            ["bmKey", "bmClient", "bmPin", "bmTotp"].forEach((id) => ($(id).value = ""));
            BROKER = r; renderChip(); renderModalStatus();
            if (r.state === "CONNECTED") window.dispatchEvent(new Event("broker:connected"));
            msg(`${r.message}${r.saved_to_env ? " Saved to .env." : " (Not saved: it will be forgotten on restart.)"}`, true);
        } catch (err) { msg(err.message, false); }
        $("bmGo").disabled = false;
    });

    let discArmed = false;
    $("bmDisc").addEventListener("click", async () => {
        if (!discArmed) {   // two-step confirm without a browser dialog
            discArmed = true; $("bmDisc").textContent = "CLICK AGAIN: DISCONNECT & FORGET SAVED CREDENTIALS";
            setTimeout(() => { discArmed = false; $("bmDisc").textContent = "DISCONNECT"; }, 5000); return;
        }
        discArmed = false; $("bmDisc").textContent = "DISCONNECT";
        try { const r = await getJSON("/broker/disconnect", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ forget: true }) }); BROKER = r; renderChip(); renderModalStatus(); msg(r.message, true); }
        catch (err) { msg(err.message, false); }
    });

    brokerStatus(); setInterval(brokerStatus, 15000);
    window.Header = { openBroker, refreshBroker: brokerStatus };
})();
