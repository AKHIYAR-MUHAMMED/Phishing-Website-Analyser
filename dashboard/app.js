/**
 * PhishGuard AI dashboard controller.
 *
 * Honesty rules (Phase 1):
 * - Every value shown comes from an API response. No default or placeholder numbers.
 * - No client-side verdicts. If the backend fails, the error is shown.
 * - Components that are not available are shown with their status and reason.
 */

document.addEventListener('DOMContentLoaded', () => {
    initNavigation();
    initScanForm();
    loadComponentStatus();
    loadEvaluationStatus();
});

const STATUS_BADGE = {
    available: 'badge-success',
    ok: 'badge-success',
    heuristic: 'badge-warning',
    not_evaluated: 'badge-muted',
    unavailable: 'badge-muted',
    not_implemented: 'badge-muted',
    error: 'badge-danger',
};

function escapeHtml(value) {
    return String(value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function statusBadge(status) {
    const cls = STATUS_BADGE[status] || 'badge-muted';
    return `<span class="badge ${cls}">${escapeHtml(status || 'unknown')}</span>`;
}

function rowsHtml(obj) {
    return Object.entries(obj)
        .map(([k, v]) => `<div class="intel-row"><span>${escapeHtml(k)}</span> <strong>${escapeHtml(v === null ? '—' : v)}</strong></div>`)
        .join('');
}

function unavailableHtml(section) {
    return `${statusBadge(section.status)} <p class="status-note">${escapeHtml(section.reason || '')}</p>`;
}

async function fetchJson(url, options) {
    const response = await fetch(url, options);
    let body = null;
    try { body = await response.json(); } catch (e) { /* non-JSON body */ }
    if (!response.ok) {
        const detail = body && (body.detail || body.reason) ? (body.detail || body.reason) : '';
        throw new Error(`HTTP ${response.status}${detail ? ': ' + detail : ''}`);
    }
    return body;
}

// --- Tab navigation ---
function initNavigation() {
    const headings = { 'scanner-tab': 'Scanner', 'status-tab': 'Component Status', 'evaluation-tab': 'Evaluation & Data' };
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const target = item.getAttribute('data-tab');
            document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
            document.querySelectorAll('.tab-page').forEach(p => p.classList.remove('active'));
            item.classList.add('active');
            const page = document.getElementById(target);
            if (page) page.classList.add('active');
            document.getElementById('page-heading').textContent = headings[target] || '';
        });
    });
}

// --- Scan ---
function initScanForm() {
    const btn = document.getElementById('start-scan-btn');
    const urlInput = document.getElementById('target-url-input');
    const run = () => { const url = urlInput.value.trim(); if (url) performScan(url); };
    btn.addEventListener('click', run);
    urlInput.addEventListener('keypress', (e) => { if (e.key === 'Enter') run(); });
}

async function performScan(url) {
    const btn = document.getElementById('start-scan-btn');
    const results = document.getElementById('results-container');
    const errorBox = document.getElementById('scan-error');
    const html = document.getElementById('html-content-input').value;

    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Analysing...';
    errorBox.classList.add('hidden');
    results.classList.add('hidden');

    try {
        const report = await fetchJson('/api/v1/scan', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url: url, html_content: html }),
        });
        renderReport(report);
        results.classList.remove('hidden');
    } catch (err) {
        // No fallback verdict: show the failure.
        document.getElementById('scan-error-text').textContent = `The backend request failed (${err.message}). No result is shown.`;
        errorBox.classList.remove('hidden');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="fa-solid fa-magnifying-glass"></i> Analyse';
    }
}

function renderCrawl(crawl) {
    const box = document.getElementById('crawl-box');
    if (!crawl) { box.innerHTML = ''; return; }
    if (crawl.status === 'available') {
        const { status, component, headers, html_length_bytes, visible_text, ...stats } = crawl;
        box.innerHTML = `${statusBadge(status)} ${rowsHtml({ ...stats, html_length_bytes })}`;
    } else {
        box.innerHTML = unavailableHtml(crawl);
    }
}

function renderReport(report) {
    renderCrawl(report.crawl);
    document.getElementById('verdict-val').textContent = report.verdict === null ? 'Not available' : report.verdict;
    document.getElementById('probability-val').textContent =
        report.phishing_probability === null ? 'Not available' : report.phishing_probability;
    document.getElementById('latency-val').textContent = `${report.processing_latency_ms} ms`;
    document.getElementById('decision-reason').textContent = report.decision ? report.decision.reason || '' : '';

    const m = report.modalities || {};
    document.getElementById('modalities-tbody').innerHTML = Object.entries(m).map(([name, section]) => `
        <tr>
            <td><strong>${escapeHtml(name)}</strong></td>
            <td>${statusBadge(section.status)}</td>
            <td>${escapeHtml(section.reason || section.note || section.kind ||
                (section.engines_queried !== undefined ? `${section.engines_ok} of ${section.engines_queried} engines returned a valid answer` : ''))}</td>
        </tr>`).join('');

    const url = m.url_features || {};
    document.getElementById('url-features-box').innerHTML =
        url.status === 'available' ? rowsHtml(url.features) : unavailableHtml(url);

    const dom = m.dom_graph || {};
    if (dom.status === 'available') {
        const { status, kind, known_limitations, ...stats } = dom;
        document.getElementById('dom-graph-box').innerHTML =
            rowsHtml(stats) + `<p class="status-note mt-2">${escapeHtml(known_limitations || '')}</p>`;
    } else {
        document.getElementById('dom-graph-box').innerHTML = unavailableHtml(dom);
    }

    const js = m.js_indicators || {};
    document.getElementById('js-box').innerHTML = js.status === 'heuristic'
        ? `${statusBadge(js.status)} <p class="status-note">${escapeHtml(js.note)}</p>${rowsHtml(js.counts)}`
        : unavailableHtml(js);

    renderLLM(m.llm || {});
}

function renderLLM(llm) {
    const results = llm.engine_results || [];
    const header = `<p class="status-note">${escapeHtml(llm.engines_ok)} of ${escapeHtml(llm.engines_queried)} engines returned a valid answer.
        ${llm.aggregate ? escapeHtml(llm.aggregate.reason) : ''}</p>`;
    const rows = results.map(r => {
        const detail = r.status === 'ok'
            ? `${escapeHtml(r.verdict)} (threat_score ${escapeHtml(r.threat_score)}, ${escapeHtml(r.latency_ms)} ms). Model-generated reasoning: ${escapeHtml(r.reasoning)}`
            : escapeHtml(r.reason || '');
        return `<tr><td>${escapeHtml(r.engine)}</td><td>${statusBadge(r.status)}</td><td>${detail}</td></tr>`;
    }).join('');
    document.getElementById('llm-box').innerHTML = header +
        `<div class="table-wrapper"><table class="data-table"><thead><tr><th>Engine</th><th>Status</th><th>Result</th></tr></thead><tbody>${rows}</tbody></table></div>`;
}

// --- Component status ---
async function loadComponentStatus() {
    const tbody = document.getElementById('components-tbody');
    try {
        const data = await fetchJson('/dashboard/system');
        tbody.innerHTML = data.components.map(c => `
            <tr><td><strong>${escapeHtml(c.name)}</strong></td><td>${statusBadge(c.status)}</td><td>${escapeHtml(c.reason)}</td></tr>`).join('');
    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="3">Could not load component status (${escapeHtml(err.message)}).</td></tr>`;
    }
}

// --- Evaluation, dataset, history ---
async function loadEvaluationStatus() {
    const tbody = document.getElementById('evaluation-tbody');
    const items = [
        ['Evaluation metrics', '/api/v1/metrics'],
        ['Dataset', '/dashboard/datasets'],
        ['Scan history', '/dashboard/history'],
    ];
    const rows = [];
    for (const [label, url] of items) {
        try {
            const data = await fetchJson(url);
            rows.push(`<tr><td><strong>${escapeHtml(label)}</strong></td><td>${statusBadge(data.status)}</td><td>${escapeHtml(data.reason || '')}</td></tr>`);
        } catch (err) {
            rows.push(`<tr><td><strong>${escapeHtml(label)}</strong></td><td>${statusBadge('error')}</td><td>${escapeHtml(err.message)}</td></tr>`);
        }
    }
    tbody.innerHTML = rows.join('');
}
