"""Read-only dashboard for render lineage.

Thin observability surface over the trace store. No auth, no writes,
no workflow. Served from the existing Starlette server behind --dashboard.

Routes:
    GET /dashboard          -> HTML dashboard (single-page)
    GET /api/history        -> JSON render history with filters
    GET /api/history/{id}   -> JSON single trace with all stages
    GET /api/stats          -> JSON aggregate statistics
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
# Dashboard HTML — brand-aligned, split-view, trace-first
# ---------------------------------------------------------------------------

_DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Formforge</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root {
  --bg:#1c1b19; --surface:#242320; --panel:#2c2a27; --border:#3d3a36;
  --ink:#ddd8d0; --ink2:#b8b2a8; --muted:#8a847a; --mid:#6b655c;
  --accent:#a07850; --accent-dim:rgba(160,120,80,.08);
  --ok:#5a8a6a; --ok-dim:rgba(90,138,106,.08);
  --err:#b05545; --err-dim:rgba(176,85,69,.08);
  --info:#6a8a9a; --info-dim:rgba(106,138,154,.08);
  --display:'DM Serif Display',Georgia,serif;
  --sans:'Inter',system-ui,sans-serif;
  --mono:'JetBrains Mono',ui-monospace,monospace;
}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:var(--sans);background:var(--bg);color:var(--ink);-webkit-font-smoothing:antialiased;height:100vh;overflow:hidden}
::selection{background:rgba(196,98,42,.2)}

/* Layout */
.shell{display:flex;flex-direction:column;height:100vh}
header{display:flex;align-items:center;justify-content:space-between;padding:16px 24px;border-bottom:1px solid var(--border);background:var(--surface)}
header h1{font-family:var(--display);font-size:20px;font-weight:400;color:var(--ink);letter-spacing:.3px}
header .meta{display:flex;align-items:center;gap:12px}
header .meta span{font-size:11px;color:var(--muted);font-family:var(--mono)}
header button{background:none;border:1px solid var(--border);color:var(--muted);padding:5px 14px;border-radius:4px;cursor:pointer;font-size:12px;font-family:var(--sans)}
header button:hover{border-color:var(--accent);color:var(--accent)}

/* Summary strip */
.strip{display:flex;gap:0;border-bottom:1px solid var(--border);background:var(--surface)}
.strip .stat{flex:1;padding:14px 24px;border-right:1px solid var(--border);display:flex;flex-direction:column}
.strip .stat:last-child{border-right:none}
.strip .stat .label{font-size:10px;text-transform:uppercase;letter-spacing:.8px;color:var(--muted);margin-bottom:4px}
.strip .stat .val{font-size:22px;font-weight:600;font-family:var(--mono);color:var(--ink)}
.strip .stat .val.sage{color:var(--ok)}
.strip .stat .val.wine{color:var(--err)}

/* Split view */
.split{display:flex;flex:1;overflow:hidden}
.list-pane{width:420px;min-width:350px;border-right:1px solid var(--border);display:flex;flex-direction:column;overflow:hidden}
.detail-pane{flex:1;overflow-y:auto;background:var(--bg)}

/* Filters */
.filters{display:flex;gap:0;padding:0;border-bottom:1px solid var(--border)}
.filters button{flex:1;background:none;border:none;border-bottom:2px solid transparent;color:var(--muted);padding:10px 0;font-size:12px;font-family:var(--sans);cursor:pointer;letter-spacing:.3px}
.filters button:hover{color:var(--ink2)}
.filters button.active{color:var(--accent);border-bottom-color:var(--accent)}

/* Event list */
.events{flex:1;overflow-y:auto}
.event{padding:14px 20px;border-bottom:1px solid var(--border);cursor:pointer;transition:background .1s}
.event:hover{background:var(--surface)}
.event.selected{background:var(--panel);border-left:3px solid var(--accent)}
.event .top{display:flex;justify-content:space-between;align-items:center;margin-bottom:6px}
.event .template{font-size:13px;font-weight:500;color:var(--ink)}
.event .time{font-size:11px;font-family:var(--mono);color:var(--muted)}
.event .bottom{display:flex;align-items:center;gap:8px}
.event .badge{font-size:10px;font-weight:600;padding:2px 8px;border-radius:3px;letter-spacing:.3px}
.event .badge.ok{background:var(--ok-dim);color:var(--ok)}
.event .badge.fail{background:var(--err-dim);color:var(--err)}
.event .pill{font-size:10px;padding:2px 6px;border-radius:3px;font-family:var(--mono)}
.event .pill.zugferd{background:var(--info-dim);color:var(--info)}
.event .pill.prov{background:var(--accent-dim);color:var(--accent)}
.event .dur{font-size:11px;color:var(--muted);font-family:var(--mono);margin-left:auto}
.event .error-line{margin-top:6px;font-size:11px;color:var(--err);font-family:var(--mono);padding-left:2px}

/* Detail pane */
.detail-empty{display:flex;align-items:center;justify-content:center;height:100%;color:var(--mid);font-size:14px}
.detail{padding:32px}
.detail h2{font-family:var(--display);font-size:24px;font-weight:400;margin-bottom:20px;color:var(--ink)}
.detail .fields{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:28px}
.detail .field .label{font-size:10px;text-transform:uppercase;letter-spacing:.8px;color:var(--muted);margin-bottom:3px}
.detail .field .val{font-size:13px;color:var(--ink2);font-family:var(--mono)}
.detail .field .val.ok{color:var(--ok)}
.detail .field .val.fail{color:var(--err)}

/* Stage pipeline */
.pipeline{margin-bottom:28px}
.pipeline h3{font-size:11px;text-transform:uppercase;letter-spacing:.8px;color:var(--muted);margin-bottom:12px}
.stage{display:flex;align-items:flex-start;gap:12px;padding:12px 16px;background:var(--surface);border:1px solid var(--border);border-radius:6px;margin-bottom:8px}
.stage .icon{font-size:15px;margin-top:1px;width:18px;flex-shrink:0}
.stage .icon.pass{color:var(--ok)}
.stage .icon.fail{color:var(--err)}
.stage .icon.skip{color:var(--mid)}
.stage .body{flex:1;min-width:0}
.stage .name{font-size:13px;font-family:var(--mono);font-weight:500;color:var(--ink)}
.stage .row{display:flex;gap:12px;margin-top:4px}
.stage .row span{font-size:11px;color:var(--muted);font-family:var(--mono)}
.stage .errors{margin-top:6px}
.stage .errors div{font-size:11px;color:var(--err);font-family:var(--mono);padding:2px 0}

/* Hashes */
.hashes{background:var(--surface);border:1px solid var(--border);border-radius:6px;padding:16px}
.hashes h3{font-size:11px;text-transform:uppercase;letter-spacing:.8px;color:var(--muted);margin-bottom:10px}
.hashes .row{display:flex;justify-content:space-between;padding:4px 0;font-size:12px;font-family:var(--mono)}
.hashes .row .k{color:var(--muted)}
.hashes .row .v{color:var(--ink2)}

.empty-state{text-align:center;padding:60px 20px;color:var(--mid)}
.empty-state p{margin-top:8px;font-size:12px}
</style>
</head>
<body>
<div class="shell">
  <header>
    <h1>Formforge</h1>
    <div class="meta">
      <span id="instance-info"></span>
      <button onclick="loadData()">Refresh</button>
    </div>
  </header>

  <div class="strip">
    <div class="stat"><div class="label">Renders</div><div class="val" id="s-total">-</div></div>
    <div class="stat"><div class="label">Success</div><div class="val sage" id="s-rate">-</div></div>
    <div class="stat"><div class="label">Avg Duration</div><div class="val" id="s-avg">-</div></div>
    <div class="stat"><div class="label">Failures</div><div class="val wine" id="s-fail">-</div></div>
    <div class="stat"><div class="label">Templates</div><div class="val" id="s-tpl">-</div></div>
  </div>

  <div class="split">
    <div class="list-pane">
      <div class="filters">
        <button class="active" onclick="setFilter('all',this)">All</button>
        <button onclick="setFilter('error',this)">Failures</button>
        <button onclick="setFilter('zugferd',this)">Compliance</button>
      </div>
      <div class="events" id="events"></div>
    </div>
    <div class="detail-pane" id="detail-pane">
      <div class="detail-empty">Select a render to inspect its trace</div>
    </div>
  </div>
</div>

<script>
let filter='all', selectedId=null;

async function loadData(){
  const [sr,hr]=await Promise.all([fetch('/api/stats'),fetch('/api/history?limit=100'+(filter==='error'?'&outcome=error':''))]);
  const stats=await sr.json(), traces=await hr.json();
  document.getElementById('s-total').textContent=stats.total;
  document.getElementById('s-rate').textContent=stats.total>0?stats.success_rate+'%':'-';
  document.getElementById('s-avg').textContent=stats.avg_ms+'ms';
  document.getElementById('s-fail').textContent=stats.failures;
  document.getElementById('s-tpl').textContent=stats.unique_templates;
  let filtered=traces;
  if(filter==='zugferd') filtered=traces.filter(t=>t.zugferd_profile);
  renderEvents(filtered);
  if(selectedId){
    const t=filtered.find(t=>t.id===selectedId);
    if(t){showDetail(t)}
    else if(filtered.length){selectTrace(filtered[0].id)}
  } else if(filtered.length){
    selectTrace(filtered[0].id);
  }
}

function renderEvents(traces){
  const el=document.getElementById('events');
  if(!traces.length){el.innerHTML='<div class="empty-state"><p>No renders recorded</p><p>Set FORMFORGE_HISTORY to enable</p></div>';return}
  el.innerHTML=traces.map(t=>{
    const time=t.timestamp.substring(11,19);
    const sel=t.id===selectedId?' selected':'';
    const badge=t.outcome==='success'?'<span class="badge ok">OK</span>':'<span class="badge fail">FAIL</span>';
    let pills='';
    if(t.zugferd_profile) pills+='<span class="pill zugferd">'+t.zugferd_profile+'</span>';
    if(t.provenance_hash) pills+='<span class="pill prov">provenance</span>';
    const dur=t.total_ms+'ms';
    let err='';
    if(t.outcome==='error') err='<div class="error-line">'+t.error_code+' at '+t.error_stage+'</div>';
    return '<div class="event'+sel+'" onclick="selectTrace(&quot;'+t.id+'&quot;)"><div class="top"><span class="template">'+t.template_name+'</span><span class="time">'+time+'</span></div><div class="bottom">'+badge+pills+'<span class="dur">'+dur+'</span></div>'+err+'</div>';
  }).join('');
}

function setFilter(f,btn){
  filter=f;
  document.querySelectorAll('.filters button').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');
  loadData();
}

async function selectTrace(id){
  selectedId=id;
  document.querySelectorAll('.event').forEach(e=>e.classList.remove('selected'));
  const el=document.querySelector('.event[onclick*="'+id+'"]');
  if(el)el.classList.add('selected');
  const res=await fetch('/api/history/'+id);
  const t=await res.json();
  showDetail(t);
}

function showDetail(t){
  const p=document.getElementById('detail-pane');
  const outcome=t.outcome==='success'?'<span class="val ok">SUCCESS</span>':'<span class="val fail">FAIL</span>';
  let stagesHtml='';
  if(t.stages&&t.stages.length){
    stagesHtml=t.stages.map(s=>{
      const icon=s.status==='pass'?'\\u2713':s.status==='fail'||s.status==='error'?'\\u2717':'\\u25CB';
      const cls=s.status==='pass'?'pass':s.status==='fail'||s.status==='error'?'fail':'skip';
      let meta=[];
      if(s.metadata){
        if(s.metadata.pdf_size) meta.push(Math.round(s.metadata.pdf_size/1024)+'KB');
        if(s.metadata.xml_size) meta.push(s.metadata.xml_size+'B XML');
        if(s.metadata.profile) meta.push(s.metadata.profile);
        if(s.metadata.proof_hash) meta.push(s.metadata.proof_hash.substring(0,20)+'...');
      }
      let errs='';
      if(s.errors&&s.errors.length){
        errs='<div class="errors">'+s.errors.map(e=>'<div>'+e.path+': '+e.message+'</div>').join('')+'</div>';
      }
      return '<div class="stage"><div class="icon '+cls+'">'+icon+'</div><div class="body"><div class="name">'+s.stage+'</div><div class="row"><span>'+s.status+'</span><span>'+s.duration_ms+'ms</span>'+(meta.length?'<span>'+meta.join(' \\u00b7 ')+'</span>':'')+'</div>'+errs+'</div></div>';
    }).join('');
  }
  p.innerHTML='<div class="detail"><h2>'+t.template_name+'</h2><div class="fields"><div class="field"><div class="label">Outcome</div>'+outcome+'</div><div class="field"><div class="label">Duration</div><div class="val">'+t.total_ms+'ms</div></div>'+(t.pdf_size?'<div class="field"><div class="label">PDF Size</div><div class="val">'+Math.round(t.pdf_size/1024)+'KB</div></div>':'')+'<div class="field"><div class="label">Time</div><div class="val">'+t.timestamp.replace('T',' ').substring(0,19)+'</div></div>'+(t.zugferd_profile?'<div class="field"><div class="label">Compliance</div><div class="val">'+t.zugferd_profile+'</div></div>':'')+(t.provenance_hash?'<div class="field"><div class="label">Provenance</div><div class="val">'+t.provenance_hash.substring(0,24)+'...</div></div>':'')+(t.error_code?'<div class="field"><div class="label">Error</div><div class="val fail">'+t.error_code+'</div></div><div class="field"><div class="label">Stage</div><div class="val fail">'+t.error_stage+'</div></div>':'')+'</div><div class="pipeline"><h3>Pipeline Stages</h3>'+stagesHtml+'</div><div class="hashes"><h3>Identity</h3><div class="row"><span class="k">Trace ID</span><span class="v">'+t.id+'</span></div><div class="row"><span class="k">Template</span><span class="v">'+t.template_hash+'</span></div><div class="row"><span class="k">Data</span><span class="v">'+t.data_hash+'</span></div><div class="row"><span class="k">Engine</span><span class="v">formforge '+t.engine_version+'</span></div></div></div>';
}

loadData();
setInterval(loadData,10000);
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
