"""Read-only dashboard for render lineage.

Thin observability surface over the trace store. No auth, no writes,
no workflow. Served from the existing Starlette server behind --dashboard.

Routes:
    GET /dashboard          → HTML dashboard (single-page)
    GET /api/history        → JSON render history with filters
    GET /api/history/{id}   → JSON single trace with all stages
    GET /api/stats          → JSON aggregate statistics
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route

from .trace import TraceStore


def _get_store(request: Request) -> TraceStore | None:
    return getattr(request.app.state, "trace_store", None)


# ---------------------------------------------------------------------------
# JSON API endpoints
# ---------------------------------------------------------------------------


async def api_history(request: Request) -> JSONResponse:
    """Paginated render history with optional filters."""
    store = _get_store(request)
    if not store:
        return JSONResponse({"error": "History not enabled"}, status_code=503)

    template = request.query_params.get("template")
    outcome = request.query_params.get("outcome")
    since = request.query_params.get("since")
    limit = int(request.query_params.get("limit", "50"))

    traces = store.query(template=template, outcome=outcome, since=since, limit=limit)
    return JSONResponse([t.to_dict() for t in traces])


async def api_trace(request: Request) -> JSONResponse:
    """Single trace detail with all stages."""
    store = _get_store(request)
    if not store:
        return JSONResponse({"error": "History not enabled"}, status_code=503)

    trace_id = request.path_params["trace_id"]
    trace = store.get(trace_id)
    if not trace:
        return JSONResponse({"error": "Trace not found"}, status_code=404)

    return JSONResponse(trace.to_dict())


async def api_stats(request: Request) -> JSONResponse:
    """Aggregate statistics."""
    store = _get_store(request)
    if not store:
        return JSONResponse({"error": "History not enabled"}, status_code=503)

    since = request.query_params.get("since")
    return JSONResponse(store.stats(since=since))


# ---------------------------------------------------------------------------
# Dashboard HTML
# ---------------------------------------------------------------------------

_DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Formforge Dashboard</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif; background: #0f1117; color: #e1e4e8; }
  .container { max-width: 1100px; margin: 0 auto; padding: 24px; }
  header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; padding-bottom: 16px; border-bottom: 1px solid #21262d; }
  header h1 { font-size: 18px; font-weight: 600; color: #f0f3f6; letter-spacing: 0.5px; }
  header .refresh { background: none; border: 1px solid #30363d; color: #8b949e; padding: 6px 12px; border-radius: 6px; cursor: pointer; font-size: 13px; }
  header .refresh:hover { border-color: #58a6ff; color: #58a6ff; }

  .cards { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }
  .card { background: #161b22; border: 1px solid #21262d; border-radius: 8px; padding: 16px; }
  .card .label { font-size: 11px; text-transform: uppercase; color: #8b949e; letter-spacing: 0.5px; margin-bottom: 4px; }
  .card .value { font-size: 28px; font-weight: 600; color: #f0f3f6; }
  .card .value.green { color: #3fb950; }
  .card .value.red { color: #f85149; }

  .section { margin-bottom: 24px; }
  .section h2 { font-size: 14px; font-weight: 600; color: #8b949e; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 12px; }

  .filters { display: flex; gap: 8px; margin-bottom: 12px; }
  .filters button { background: #21262d; border: 1px solid #30363d; color: #c9d1d9; padding: 4px 12px; border-radius: 4px; cursor: pointer; font-size: 12px; }
  .filters button.active { background: #1f6feb; border-color: #1f6feb; color: #fff; }
  .filters button:hover { border-color: #58a6ff; }

  table { width: 100%; border-collapse: collapse; }
  th { text-align: left; font-size: 11px; text-transform: uppercase; color: #8b949e; padding: 8px 12px; border-bottom: 1px solid #21262d; letter-spacing: 0.5px; }
  td { padding: 10px 12px; border-bottom: 1px solid #161b22; font-size: 13px; vertical-align: top; }
  tr:hover td { background: #161b22; }
  tr.clickable { cursor: pointer; }

  .badge { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; }
  .badge.ok { background: #0d3117; color: #3fb950; }
  .badge.fail { background: #3d1014; color: #f85149; }

  .error-detail { color: #f85149; font-size: 12px; padding: 4px 0 0 24px; }
  .meta { color: #8b949e; font-size: 12px; }
  .zugferd-badge { background: #0c2d6b; color: #58a6ff; padding: 2px 6px; border-radius: 4px; font-size: 10px; margin-left: 4px; }
  .prov-badge { background: #2d1b3d; color: #bc8cff; padding: 2px 6px; border-radius: 4px; font-size: 10px; margin-left: 4px; }

  /* Trace detail view */
  #detail { display: none; }
  #detail.active { display: block; }
  #list.hidden { display: none; }
  .back { background: none; border: none; color: #58a6ff; cursor: pointer; font-size: 13px; margin-bottom: 16px; }
  .back:hover { text-decoration: underline; }
  .detail-header { background: #161b22; border: 1px solid #21262d; border-radius: 8px; padding: 20px; margin-bottom: 16px; }
  .detail-header .row { display: flex; gap: 24px; margin-bottom: 8px; }
  .detail-header .field { }
  .detail-header .field .label { font-size: 11px; color: #8b949e; text-transform: uppercase; }
  .detail-header .field .val { font-size: 14px; color: #e1e4e8; font-family: monospace; }

  .stages { background: #161b22; border: 1px solid #21262d; border-radius: 8px; padding: 16px; }
  .stage-row { display: flex; align-items: center; gap: 12px; padding: 8px 0; border-bottom: 1px solid #21262d; }
  .stage-row:last-child { border-bottom: none; }
  .stage-icon { font-size: 16px; width: 20px; }
  .stage-icon.pass { color: #3fb950; }
  .stage-icon.fail { color: #f85149; }
  .stage-name { font-family: monospace; font-size: 13px; min-width: 200px; }
  .stage-status { font-size: 12px; min-width: 50px; }
  .stage-time { font-size: 12px; color: #8b949e; min-width: 60px; }
  .stage-meta { font-size: 12px; color: #8b949e; }
  .stage-errors { padding: 4px 0 0 32px; }
  .stage-errors div { color: #f85149; font-size: 12px; padding: 2px 0; }

  .empty { text-align: center; padding: 48px; color: #484f58; }

  @media (max-width: 768px) { .cards { grid-template-columns: repeat(2, 1fr); } }
</style>
</head>
<body>
<div class="container">
  <header>
    <h1>FORMFORGE</h1>
    <button class="refresh" onclick="loadData()">Refresh</button>
  </header>

  <div class="cards">
    <div class="card"><div class="label">Renders</div><div class="value" id="stat-total">-</div></div>
    <div class="card"><div class="label">Success Rate</div><div class="value green" id="stat-rate">-</div></div>
    <div class="card"><div class="label">Avg Time</div><div class="value" id="stat-avg">-</div></div>
    <div class="card"><div class="label">Errors</div><div class="value red" id="stat-errors">-</div></div>
  </div>

  <div id="list">
    <div class="section">
      <h2>Renders</h2>
      <div class="filters">
        <button class="active" onclick="setFilter('all', this)">All</button>
        <button onclick="setFilter('error', this)">Failures</button>
      </div>
      <table>
        <thead><tr><th>Time</th><th>Template</th><th>Status</th><th>Size</th><th>Duration</th><th></th></tr></thead>
        <tbody id="renders"></tbody>
      </table>
      <div id="empty" class="empty" style="display:none">No renders recorded yet. Set FORMFORGE_HISTORY to enable tracing.</div>
    </div>
  </div>

  <div id="detail">
    <button class="back" onclick="showList()">← Back to list</button>
    <div class="detail-header" id="detail-header"></div>
    <div class="section">
      <h2>Pipeline Stages</h2>
      <div class="stages" id="detail-stages"></div>
    </div>
  </div>
</div>

<script>
let currentFilter = 'all';
let allTraces = [];

async function loadData() {
  try {
    const [statsRes, historyRes] = await Promise.all([
      fetch('/api/stats'),
      fetch('/api/history?limit=100' + (currentFilter === 'error' ? '&outcome=error' : ''))
    ]);
    const stats = await statsRes.json();
    const traces = await historyRes.json();
    allTraces = traces;

    document.getElementById('stat-total').textContent = stats.total;
    document.getElementById('stat-rate').textContent = stats.total > 0 ? stats.success_rate + '%' : '-';
    document.getElementById('stat-avg').textContent = stats.avg_ms + 'ms';
    document.getElementById('stat-errors').textContent = stats.failures;

    renderTable(traces);
  } catch (e) {
    document.getElementById('empty').style.display = 'block';
    document.getElementById('empty').textContent = 'Could not load data: ' + e.message;
  }
}

function renderTable(traces) {
  const tbody = document.getElementById('renders');
  const empty = document.getElementById('empty');

  if (!traces.length) {
    tbody.innerHTML = '';
    empty.style.display = 'block';
    return;
  }
  empty.style.display = 'none';

  tbody.innerHTML = traces.map(t => {
    const time = t.timestamp.substring(11, 19);
    const badge = t.outcome === 'success'
      ? '<span class="badge ok">OK</span>'
      : '<span class="badge fail">FAIL</span>';
    const size = t.pdf_size > 0 ? Math.round(t.pdf_size / 1024) + 'KB' : '--';
    const duration = t.total_ms + 'ms';
    let extras = '';
    if (t.zugferd_profile) extras += '<span class="zugferd-badge">' + t.zugferd_profile + '</span>';
    if (t.provenance_hash) extras += '<span class="prov-badge">provenance</span>';
    let errorRow = '';
    if (t.outcome === 'error') {
      errorRow = '<tr><td></td><td colspan="4" class="error-detail">' +
        t.error_code + ' at ' + t.error_stage + ': ' + (t.error_message || '').substring(0, 80) +
        '</td><td></td></tr>';
    }
    return '<tr class="clickable" onclick="showTrace(\\'' + t.id + '\\')">' +
      '<td class="meta">' + time + '</td>' +
      '<td>' + t.template_name + extras + '</td>' +
      '<td>' + badge + '</td>' +
      '<td class="meta">' + size + '</td>' +
      '<td class="meta">' + duration + '</td>' +
      '<td class="meta">' + t.id.substring(0, 8) + '</td>' +
      '</tr>' + errorRow;
  }).join('');
}

function setFilter(filter, btn) {
  currentFilter = filter;
  document.querySelectorAll('.filters button').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  loadData();
}

async function showTrace(id) {
  try {
    const res = await fetch('/api/history/' + id);
    const t = await res.json();

    document.getElementById('list').classList.add('hidden');
    document.getElementById('detail').classList.add('active');

    const header = document.getElementById('detail-header');
    header.innerHTML =
      '<div class="row">' +
        '<div class="field"><div class="label">Template</div><div class="val">' + t.template_name + '</div></div>' +
        '<div class="field"><div class="label">Outcome</div><div class="val">' + t.outcome.toUpperCase() + '</div></div>' +
        '<div class="field"><div class="label">Duration</div><div class="val">' + t.total_ms + 'ms</div></div>' +
        (t.pdf_size ? '<div class="field"><div class="label">PDF Size</div><div class="val">' + Math.round(t.pdf_size/1024) + 'KB</div></div>' : '') +
      '</div>' +
      '<div class="row">' +
        '<div class="field"><div class="label">Time</div><div class="val">' + t.timestamp + '</div></div>' +
        '<div class="field"><div class="label">Trace ID</div><div class="val">' + t.id + '</div></div>' +
      '</div>' +
      (t.zugferd_profile ? '<div class="row"><div class="field"><div class="label">ZUGFeRD</div><div class="val">' + t.zugferd_profile + '</div></div></div>' : '') +
      (t.provenance_hash ? '<div class="row"><div class="field"><div class="label">Provenance</div><div class="val">' + t.provenance_hash.substring(0,40) + '...</div></div></div>' : '') +
      (t.error_code ? '<div class="row"><div class="field"><div class="label">Error</div><div class="val" style="color:#f85149">' + t.error_code + ' at ' + t.error_stage + '</div></div></div>' : '') +
      '<div class="row">' +
        '<div class="field"><div class="label">Template Hash</div><div class="val">' + t.template_hash + '</div></div>' +
        '<div class="field"><div class="label">Data Hash</div><div class="val">' + t.data_hash + '</div></div>' +
      '</div>';

    const stages = document.getElementById('detail-stages');
    if (!t.stages || !t.stages.length) {
      stages.innerHTML = '<div class="empty">No stage data</div>';
    } else {
      stages.innerHTML = t.stages.map(s => {
        const icon = s.status === 'pass' ? '✓' : s.status === 'fail' || s.status === 'error' ? '✗' : '○';
        const iconClass = s.status === 'pass' ? 'pass' : 'fail';
        let meta = '';
        if (s.metadata) {
          if (s.metadata.pdf_size) meta = Math.round(s.metadata.pdf_size/1024) + 'KB';
          else if (s.metadata.xml_size) meta = s.metadata.xml_size + 'B XML';
          else if (s.metadata.profile) meta = s.metadata.profile;
          else if (s.metadata.proof_hash) meta = s.metadata.proof_hash;
        }
        let errors = '';
        if (s.errors && s.errors.length) {
          errors = '<div class="stage-errors">' +
            s.errors.map(e => '<div>' + e.path + ': ' + e.message + '</div>').join('') +
            '</div>';
        }
        return '<div class="stage-row">' +
          '<div class="stage-icon ' + iconClass + '">' + icon + '</div>' +
          '<div class="stage-name">' + s.stage + '</div>' +
          '<div class="stage-status">' + s.status + '</div>' +
          '<div class="stage-time">' + s.duration_ms + 'ms</div>' +
          '<div class="stage-meta">' + meta + '</div>' +
          '</div>' + errors;
      }).join('');
    }
  } catch (e) {
    alert('Error loading trace: ' + e.message);
  }
}

function showList() {
  document.getElementById('detail').classList.remove('active');
  document.getElementById('list').classList.remove('hidden');
}

loadData();
setInterval(loadData, 10000);
</script>
</body>
</html>"""


async def dashboard_page(request: Request) -> HTMLResponse:
    """Serve the dashboard HTML."""
    return HTMLResponse(_DASHBOARD_HTML)


# ---------------------------------------------------------------------------
# Route factory
# ---------------------------------------------------------------------------

def dashboard_routes() -> list[Route]:
    """Return the dashboard routes to mount in the Starlette app."""
    return [
        Route("/dashboard", dashboard_page, methods=["GET"]),
        Route("/api/history", api_history, methods=["GET"]),
        Route("/api/history/{trace_id}", api_trace, methods=["GET"]),
        Route("/api/stats", api_stats, methods=["GET"]),
    ]
