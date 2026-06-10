/**
 * ============================================================
 * SQL Query Optimization — Frontend Logic
 * ============================================================
 * Handles API communication, result rendering, Chart.js
 * visualizations, and SQL syntax highlighting.
 * ============================================================
 */

const API_BASE = "http://127.0.0.1:5000/api";

let perfChart = null; // Chart.js instance

// ── Initialization ───────────────────────────────────────────

document.addEventListener("DOMContentLoaded", () => {
    loadSampleQueries();
});

// ── API Helper ───────────────────────────────────────────────

async function apiCall(endpoint, method = "GET", body = null) {
    const opts = {
        method,
        headers: { "Content-Type": "application/json" },
    };
    if (body) opts.body = JSON.stringify(body);

    const res = await fetch(`${API_BASE}${endpoint}`, opts);
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Request failed");
    return data;
}

// ── Load Sample Queries ──────────────────────────────────────

async function loadSampleQueries() {
    try {
        const queries = await apiCall("/sample-queries");
        const container = document.getElementById("sampleQueries");

        queries.forEach((q) => {
            const chip = document.createElement("button");
            chip.className = "sample-chip";
            chip.textContent = q.name;
            chip.title = q.description;
            chip.onclick = () => {
                document.getElementById("queryInput").value = q.sql;
                // Flash effect
                chip.style.background = "rgba(99,102,241,0.35)";
                setTimeout(() => (chip.style.background = ""), 300);
            };
            container.appendChild(chip);
        });
    } catch {
        // Server may not be running yet — silent fail
    }
}

// ── Main Optimize Action ─────────────────────────────────────

async function optimizeQuery() {
    const sql = document.getElementById("queryInput").value.trim();
    if (!sql) {
        showError("Please enter a SQL SELECT query.");
        return;
    }

    const optType = document.querySelector('input[name="optType"]:checked').value;

    showLoading(true);
    hideError();

    try {
        const data = await apiCall("/optimize", "POST", { query: sql, type: optType });
        renderResults(data);
    } catch (err) {
        showError(err.message);
    } finally {
        showLoading(false);
    }
}

// ── Render All Results ───────────────────────────────────────

function renderResults(data) {
    const area = document.getElementById("resultsArea");
    area.classList.remove("hidden");

    // Scroll to results smoothly
    setTimeout(() => area.scrollIntoView({ behavior: "smooth", block: "start" }), 100);

    renderQueryComparison(data);
    renderOptimizationSteps(data.optimization_steps);
    renderPerformanceMetrics(data.comparison);
    renderExecutionPlans(data.comparison);
    renderComparisonTable(data.comparison);
    renderPerformanceChart(data.comparison);
}

// ── Query Comparison ─────────────────────────────────────────

function renderQueryComparison(data) {
    document.getElementById("originalQueryDisplay").innerHTML = highlightSQL(data.original_query);
    document.getElementById("optimizedQueryDisplay").innerHTML = highlightSQL(data.optimized_query);
}

// ── Optimization Steps ───────────────────────────────────────

function renderOptimizationSteps(steps) {
    const timeline = document.getElementById("stepsTimeline");
    timeline.innerHTML = "";

    steps.forEach((step, i) => {
        const item = document.createElement("div");
        item.className = "step-item";
        item.style.animationDelay = `${i * 0.12}s`;

        item.innerHTML = `
            <div class="step-rule">Step ${i + 1}: ${escapeHtml(step.rule)}</div>
            <div class="step-desc">${escapeHtml(step.description)}</div>
        `;
        timeline.appendChild(item);
    });
}

// ── Performance Metrics Cards ────────────────────────────────

function renderPerformanceMetrics(comparison) {
    const grid = document.getElementById("metricsGrid");
    grid.innerHTML = "";

    const origTime = comparison.original?.timing?.avg_ms ?? 0;
    const optTime = comparison.optimized?.timing?.avg_ms ?? 0;
    const improvement = comparison.improvement?.time_reduction_pct ?? 0;
    const origRows = comparison.original?.timing?.rows_returned ?? 0;
    const optRows = comparison.optimized?.timing?.rows_returned ?? 0;
    const origCost = comparison.original?.cost?.estimated_cost ?? 0;
    const optCost = comparison.optimized?.cost?.estimated_cost ?? 0;

    const metrics = [
        {
            value: `${origTime.toFixed(3)}ms`,
            label: "Original Avg Time",
            cls: "neutral",
        },
        {
            value: `${optTime.toFixed(3)}ms`,
            label: "Optimized Avg Time",
            cls: "neutral",
        },
        {
            value: `${improvement >= 0 ? "+" : ""}${improvement.toFixed(1)}%`,
            label: "Time Improvement",
            cls: improvement >= 0 ? "positive" : "negative",
        },
        {
            value: origRows.toLocaleString(),
            label: "Rows Returned (Orig)",
            cls: "neutral",
        },
        {
            value: optRows.toLocaleString(),
            label: "Rows Returned (Opt)",
            cls: "neutral",
        },
        {
            value: origCost.toLocaleString(),
            label: "Est. Cost (Original)",
            cls: "neutral",
        },
        {
            value: optCost.toLocaleString(),
            label: "Est. Cost (Optimized)",
            cls: optCost <= origCost ? "positive" : "negative",
        },
        {
            value: comparison.original?.cost?.scan_type ?? "N/A",
            label: "Scan Type",
            cls: "neutral",
        },
    ];

    metrics.forEach((m) => {
        const card = document.createElement("div");
        card.className = "metric-card";
        card.innerHTML = `
            <div class="metric-value ${m.cls}">${m.value}</div>
            <div class="metric-label">${m.label}</div>
        `;
        grid.appendChild(card);
    });
}

// ── Execution Plans ──────────────────────────────────────────

function renderExecutionPlans(comparison) {
    const origPlan = comparison.original?.plan?.readable ?? "No plan available";
    const optPlan = comparison.optimized?.plan?.readable ?? "No plan available";

    document.getElementById("originalPlanDisplay").textContent = origPlan;
    document.getElementById("optimizedPlanDisplay").textContent = optPlan;
}

// ── Comparison Table ─────────────────────────────────────────

function renderComparisonTable(comparison) {
    const tbody = document.getElementById("comparisonTableBody");
    tbody.innerHTML = "";

    const origT = comparison.original?.timing ?? {};
    const optT = comparison.optimized?.timing ?? {};
    const origC = comparison.original?.cost ?? {};
    const optC = comparison.optimized?.cost ?? {};

    const rows = [
        ["Avg Execution Time", fmtMs(origT.avg_ms), fmtMs(optT.avg_ms), fmtPct(origT.avg_ms, optT.avg_ms)],
        ["Min Execution Time", fmtMs(origT.min_ms), fmtMs(optT.min_ms), fmtPct(origT.min_ms, optT.min_ms)],
        ["Max Execution Time", fmtMs(origT.max_ms), fmtMs(optT.max_ms), fmtPct(origT.max_ms, optT.max_ms)],
        ["Median Time", fmtMs(origT.median_ms), fmtMs(optT.median_ms), fmtPct(origT.median_ms, optT.median_ms)],
        ["Rows Returned", origT.rows_returned ?? "-", optT.rows_returned ?? "-", "—"],
        ["Estimated Cost", origC.estimated_cost ?? "-", optC.estimated_cost ?? "-", fmtPct(origC.estimated_cost, optC.estimated_cost)],
        ["Scan Type", origC.scan_type ?? "-", optC.scan_type ?? "-", "—"],
        ["Uses Index", origC.uses_index ? "✅ Yes" : "❌ No", optC.uses_index ? "✅ Yes" : "❌ No", "—"],
        ["Indexes Used", (origC.indexes_used || []).join(", ") || "None", (optC.indexes_used || []).join(", ") || "None", "—"],
        ["Temp B-Tree", origC.uses_temp_btree ? "⚠️ Yes" : "No", optC.uses_temp_btree ? "⚠️ Yes" : "No", "—"],
        ["Plan Steps", origC.plan_steps ?? "-", optC.plan_steps ?? "-", "—"],
    ];

    rows.forEach((r) => {
        const tr = document.createElement("tr");
        tr.innerHTML = r.map((cell) => `<td>${cell}</td>`).join("");
        tbody.appendChild(tr);
    });
}

// ── Performance Chart ────────────────────────────────────────

function renderPerformanceChart(comparison) {
    const ctx = document.getElementById("perfChart").getContext("2d");

    // Destroy old chart if exists
    if (perfChart) perfChart.destroy();

    const origT = comparison.original?.timing ?? {};
    const optT = comparison.optimized?.timing ?? {};

    perfChart = new Chart(ctx, {
        type: "bar",
        data: {
            labels: ["Avg Time (ms)", "Min Time (ms)", "Max Time (ms)", "Median (ms)"],
            datasets: [
                {
                    label: "Original Query",
                    data: [origT.avg_ms, origT.min_ms, origT.max_ms, origT.median_ms],
                    backgroundColor: "rgba(245, 158, 11, 0.6)",
                    borderColor: "rgba(245, 158, 11, 1)",
                    borderWidth: 1,
                    borderRadius: 6,
                },
                {
                    label: "Optimized Query",
                    data: [optT.avg_ms, optT.min_ms, optT.max_ms, optT.median_ms],
                    backgroundColor: "rgba(34, 197, 94, 0.6)",
                    borderColor: "rgba(34, 197, 94, 1)",
                    borderWidth: 1,
                    borderRadius: 6,
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    labels: { color: "#8b95a8", font: { family: "'Inter', sans-serif" } },
                },
                tooltip: {
                    backgroundColor: "rgba(15, 20, 35, 0.95)",
                    titleColor: "#e2e8f0",
                    bodyColor: "#8b95a8",
                    borderColor: "rgba(100, 120, 200, 0.2)",
                    borderWidth: 1,
                    cornerRadius: 8,
                    callbacks: {
                        label: (ctx) => `${ctx.dataset.label}: ${ctx.parsed.y?.toFixed(4)} ms`,
                    },
                },
            },
            scales: {
                x: {
                    ticks: { color: "#5a6478", font: { size: 11 } },
                    grid: { color: "rgba(100, 120, 200, 0.06)" },
                },
                y: {
                    ticks: {
                        color: "#5a6478",
                        font: { size: 11 },
                        callback: (v) => v.toFixed(3) + " ms",
                    },
                    grid: { color: "rgba(100, 120, 200, 0.06)" },
                    beginAtZero: true,
                },
            },
        },
    });
}

// ── Table Info ────────────────────────────────────────────────

async function loadTableInfo() {
    const card = document.getElementById("tableInfoCard");
    const grid = document.getElementById("tableInfoGrid");

    try {
        const tables = await apiCall("/table-info");
        grid.innerHTML = "";

        tables.forEach((t) => {
            const item = document.createElement("div");
            item.className = "table-info-item";
            const cols = t.columns.map((c) => `${c.name} (${c.type})`).join(", ");
            item.innerHTML = `
                <h4>${escapeHtml(t.name)}</h4>
                <div class="row-count">${t.row_count.toLocaleString()} rows</div>
                <div style="font-size:.72rem;color:var(--text-muted);margin-top:6px;">${escapeHtml(cols)}</div>
            `;
            grid.appendChild(item);
        });

        card.classList.remove("hidden");
        card.scrollIntoView({ behavior: "smooth" });
    } catch (err) {
        showError("Could not load table info: " + err.message);
    }
}

// ── Clear All ────────────────────────────────────────────────

function clearAll() {
    document.getElementById("queryInput").value = "";
    document.getElementById("resultsArea").classList.add("hidden");
    document.getElementById("tableInfoCard").classList.add("hidden");
    hideError();
    if (perfChart) { perfChart.destroy(); perfChart = null; }
}

// ── SQL Syntax Highlighting ──────────────────────────────────

function highlightSQL(sql) {
    if (!sql) return "";
    let s = escapeHtml(sql);

    // Keywords
    const keywords = [
        "SELECT", "FROM", "WHERE", "JOIN", "INNER JOIN", "LEFT JOIN",
        "RIGHT JOIN", "CROSS JOIN", "ON", "AND", "OR", "NOT", "IN",
        "AS", "GROUP BY", "ORDER BY", "HAVING", "LIMIT", "DISTINCT",
        "UNION", "INSERT", "UPDATE", "DELETE", "CREATE", "DROP",
        "ALTER", "INDEX", "TABLE", "IS", "NULL", "LIKE", "BETWEEN",
        "EXISTS", "CASE", "WHEN", "THEN", "ELSE", "END", "ASC", "DESC",
    ];

    // Functions
    const funcs = ["COUNT", "SUM", "AVG", "MAX", "MIN", "COALESCE", "IFNULL", "UPPER", "LOWER"];

    // Highlight keywords
    keywords.forEach((kw) => {
        const regex = new RegExp(`\\b(${kw})\\b`, "gi");
        s = s.replace(regex, '<span class="keyword">$1</span>');
    });

    // Highlight functions
    funcs.forEach((fn) => {
        const regex = new RegExp(`\\b(${fn})\\s*\\(`, "gi");
        s = s.replace(regex, '<span class="function">$1</span>(');
    });

    // Highlight strings
    s = s.replace(/&#39;([^&#]*?)&#39;/g, '<span class="string">\'$1\'</span>');

    // Highlight numbers
    s = s.replace(/\b(\d+\.?\d*)\b/g, '<span class="number">$1</span>');

    return s;
}

// ── Utility Functions ────────────────────────────────────────

function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}

function fmtMs(val) {
    if (val === undefined || val === null) return "-";
    return val.toFixed(4) + " ms";
}

function fmtPct(orig, opt) {
    if (!orig || !opt || orig === 0) return "—";
    const pct = ((orig - opt) / orig) * 100;
    const sign = pct >= 0 ? "+" : "";
    const color = pct >= 0 ? "var(--success)" : "var(--error)";
    return `<span style="color:${color};font-weight:600">${sign}${pct.toFixed(1)}%</span>`;
}

function showLoading(show) {
    const overlay = document.getElementById("loadingOverlay");
    if (show) overlay.classList.add("active");
    else overlay.classList.remove("active");
}

function showError(msg) {
    const el = document.getElementById("errorMessage");
    el.textContent = msg;
    el.classList.remove("hidden");
}

function hideError() {
    document.getElementById("errorMessage").classList.add("hidden");
}

// ── Keyboard Shortcut: Ctrl+Enter to optimize ────────────────

document.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
        e.preventDefault();
        optimizeQuery();
    }
});
