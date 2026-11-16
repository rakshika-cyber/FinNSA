/* Shared Chart.js theme (1990s terminal palette). Requires Chart.js loaded first. */
const CH = (() => {
    const C = { amber: "#ffb000", cyan: "#00e5ff", green: "#33ff33", red: "#ff3b30", yellow: "#ffff55", magenta: "#ff55ff", white: "#ffffff", grey: "#8a8a8a", blue: "#5a7dff", orange: "#ff8c1a", lime: "#b6ff3b", pink: "#ff8fb3" };
    const PALETTE = [C.cyan, C.yellow, C.green, C.magenta, C.orange, C.blue, C.lime, C.pink];
    Chart.defaults.color = C.amber;
    Chart.defaults.font.family = '"JetBrains Mono", "Courier New", monospace';
    Chart.defaults.font.size = 10;
    Chart.defaults.borderColor = "rgba(255,176,0,0.18)";
    Chart.defaults.animation = false;
    Chart.defaults.maintainAspectRatio = false;
    Chart.defaults.plugins.legend.labels.boxWidth = 10;
    Chart.defaults.plugins.tooltip.backgroundColor = "#000";
    Chart.defaults.plugins.tooltip.borderColor = C.amber;
    Chart.defaults.plugins.tooltip.borderWidth = 1;
    const live = {};
    function make(id, config) {
        if (live[id]) live[id].destroy();
        const canvas = document.getElementById(id);
        if (!canvas) return null;
        live[id] = new Chart(canvas, config);
        return live[id];
    }
    const line = (label, data, color, extra = {}) => ({ label, data, borderColor: color, backgroundColor: color, borderWidth: 1.4, pointRadius: 0, tension: 0, ...extra });
    const xTicks = { ticks: { maxTicksLimit: 8, maxRotation: 0 }, grid: { display: false } };
    return { C, PALETTE, make, line, xTicks };
})();
