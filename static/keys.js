/* Shared keyboard shortcuts (vim-style single keys; no Esc/F-keys needed).
   Pages call Keys.bind([...]) to add or override bindings. '?' shows the help overlay. */
const Keys = (() => {
    const bindings = new Map();   // key -> {desc, group, fn}
    const closers = [];           // functions that close something and return true if they did
    let overlay = null;

    const style = document.createElement("style");
    style.textContent = `
      .keys-overlay { position: fixed; inset: 0; background: rgba(0,0,0,.85); z-index: 100; display: flex; align-items: center; justify-content: center; }
      .keys-box { width: min(620px, 94vw); max-height: 88vh; overflow: auto; background: #000; border: 3px double #ffb000; color: #ffb000;
                  font-family: "JetBrains Mono", "Courier New", monospace; font-size: 13px; text-shadow: none; }
      .keys-box .kt { background: #0000aa; color: #fff; padding: 3px 10px; font-family: "VT323", monospace; font-size: 22px; letter-spacing: 1px; display: flex; justify-content: space-between; }
      .keys-box .kg { color: #00e5ff; padding: 8px 12px 2px; font-weight: 700; }
      .keys-box .kr { display: flex; gap: 12px; padding: 1px 12px; }
      .keys-box kbd { display: inline-block; min-width: 26px; text-align: center; background: #ffb000; color: #000; font-weight: 800; padding: 0 6px; font-family: inherit; }
      .keys-box .kf { color: #a06f00; font-size: 11px; padding: 10px 12px; }
      tr.kb-sel td { background: #1f1a00 !important; }
      tr.kb-sel td:first-child { box-shadow: inset 4px 0 0 #ffff55; }
    `;
    document.head.appendChild(style);

    const label = (k) => ({ "/": "/", "?": "?", "[": "[", "]": "]", "Enter": "Enter", "ArrowDown": "↓", "ArrowUp": "↑" }[k] || k.toUpperCase());

    function bind(list) {
        for (const b of list) for (const k of [].concat(b.key)) bindings.set(k, { desc: b.desc, group: b.group || "Page", fn: b.fn, hide: b.hide, aliases: [].concat(b.key) });
    }
    function addCloser(fn) { closers.push(fn); }

    function closeHelp() { if (overlay) { overlay.remove(); overlay = null; return true; } return false; }
    function closeTopmost() {
        if (closeHelp()) return true;
        return closers.some((fn) => fn());
    }
    function help() {
        if (closeHelp()) return;
        const groups = {};
        const seen = new Set();
        for (const [, b] of bindings) {
            if (b.hide || seen.has(b)) continue;
            seen.add(b);
            (groups[b.group] ||= []).push(b);
        }
        const order = ["Page", "Navigate"];
        const names = Object.keys(groups).sort((a, b) => order.indexOf(a) - order.indexOf(b));
        overlay = document.createElement("div");
        overlay.className = "keys-overlay";
        overlay.innerHTML = `<div class="keys-box"><div class="kt"><span>KEYBOARD SHORTCUTS</span><span>[?] CLOSE</span></div>` +
            names.map((g) => `<div class="kg">${g.toUpperCase()}</div>` + groups[g].map((b) =>
                `<div class="kr"><span style="min-width:120px">${b.aliases.map((k) => `<kbd>${label(k)}</kbd>`).join(" ")}</span><span>${b.desc}</span></div>`).join("")).join("") +
            `<div class="kf">Shortcuts are ignored while typing in a box. Press Esc or Q to leave a box or close this panel.</div></div>`;
        overlay.addEventListener("click", (e) => { if (e.target === overlay) closeHelp(); });
        document.body.appendChild(overlay);
    }

    const typing = (t) => t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.tagName === "SELECT" || t.isContentEditable);

    document.addEventListener("keydown", (e) => {
        if (e.metaKey || e.ctrlKey || e.altKey) return;
        if (typing(e.target)) {
            if (e.key === "Escape") e.target.blur();
            return;
        }
        if (e.key === "Escape") { if (closeTopmost()) e.preventDefault(); return; }
        const key = e.key.length === 1 ? e.key.toLowerCase() : e.key;
        const b = bindings.get(key);
        if (b) { e.preventDefault(); b.fn(e); }
    });

    // ---- global bindings (pages may override any of these) ----
    const here = location.pathname;
    bind([
        { key: "?", group: "Navigate", desc: "Show / hide this help", fn: help },
        { key: "h", group: "Navigate", desc: "Market board (home)", fn: () => { if (here !== "/") location.href = "/"; } },
        { key: "c", group: "Navigate", desc: "Compare stocks & sectors", fn: () => { if (!here.startsWith("/compare-view")) location.href = "/compare-view"; } },
        { key: "d", group: "Navigate", desc: "Datasets", fn: () => { location.href = "/static/datasets.html"; } },
        { key: "q", group: "Navigate", desc: "Close panel / go back to board", fn: () => { if (!closeTopmost() && here !== "/") location.href = "/"; } },
    ]);

    return { bind, addCloser, help, closeHelp, label };
})();
