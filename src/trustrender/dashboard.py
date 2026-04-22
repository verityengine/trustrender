"""Read-only dashboard for render lineage.

Thin observability surface over the trace store. No auth, no writes,
no workflow. Served from the existing Starlette server behind --dashboard.

Routes:
    GET /dashboard          -> HTML dashboard (single-page)
    GET /history        -> JSON render history with filters
    GET /history/{id}   -> JSON single trace with all stages
    GET /stats          -> JSON aggregate statistics
"""

from __future__ import annotations

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
<title>TrustRender</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root {
  --bg:#131313; --surface:#191919; --panel:#1f1f1f;
  --border:#2c2c2c; --border-light:#3b3b3b;
  --ink:#f3ede3; --ink2:#b7a995; --muted:#847766; --faint:#847766;
  --accent:#b86a3a; --accent-hover:#cb7a47; --accent-soft:rgba(184,106,58,.10); --accent-border:rgba(184,106,58,.25);
  --ok:#5f8f73; --ok-soft:rgba(95,143,115,.12); --ok-border:rgba(95,143,115,.22); --ok-faint:rgba(95,143,115,.07);
  --err:#b45849; --err-soft:rgba(180,88,73,.12); --err-border:rgba(180,88,73,.22); --err-faint:rgba(180,88,73,.07);
  --info:#5f7690; --info-soft:rgba(95,118,144,.12); --info-border:rgba(95,118,144,.22);
  --display:'DM Serif Display',Georgia,serif;
  --sans:'Inter',system-ui,sans-serif;
  --mono:'JetBrains Mono',ui-monospace,monospace;
}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:var(--sans);background:var(--bg);color:var(--ink);-webkit-font-smoothing:antialiased;height:100vh;overflow:hidden;font-size:13px}
::selection{background:rgba(192,122,66,.18)}

/* Shell */
.shell{display:flex;flex-direction:column;height:100vh}

/* Header */
header{display:flex;align-items:center;justify-content:space-between;padding:14px 28px;border-bottom:1px solid var(--border);background:var(--surface)}
header h1{font-family:var(--display);font-size:19px;font-weight:400;color:var(--ink);letter-spacing:.4px}
header .meta{display:flex;align-items:center;gap:14px}
header .meta span{font-size:11px;color:var(--faint);font-family:var(--mono)}
header button{background:var(--panel);border:1px solid var(--border);color:var(--ink2);padding:8px 20px;border-radius:5px;cursor:pointer;font-size:12px;font-family:var(--sans);font-weight:500;letter-spacing:.3px;transition:all .15s}
header button:hover{border-color:var(--accent-border);color:var(--ink);background:var(--accent-soft)}

/* Summary strip */
.strip{display:flex;border-bottom:1px solid var(--border);background:linear-gradient(180deg,var(--surface) 0%,var(--bg) 100%)}
.strip .stat{flex:1;padding:16px 28px;border-right:1px solid var(--border)}
.strip .stat:last-child{border-right:none}
.strip .stat .label{font-size:9px;text-transform:uppercase;letter-spacing:1.2px;color:var(--faint);margin-bottom:6px;font-weight:500}
.strip .stat .val{font-size:20px;font-weight:500;font-family:var(--mono);color:var(--ink2);line-height:1}
.strip .stat .val.primary{font-size:28px;font-weight:700}
.strip .stat .val.sage{color:var(--ok)}
.strip .stat .val.sage.perfect{background:var(--ok-faint);padding:2px 8px;border-radius:4px;margin:-2px -8px}
.strip .stat .val.wine{color:var(--err)}
.strip .stat .val.wine.hot{background:var(--err-faint);padding:2px 8px;border-radius:4px;margin:-2px -8px}

/* Split view */
.split{display:flex;flex:1;overflow:hidden}
.list-pane{width:420px;min-width:360px;border-right:1px solid var(--border);display:flex;flex-direction:column;overflow:hidden;background:var(--bg)}
.detail-pane{flex:1;overflow-y:auto;background:var(--bg)}

/* Filters */
.filters{display:flex;border-bottom:1px solid var(--border);background:var(--surface)}
.filters button{flex:1;background:none;border:none;border-bottom:2px solid transparent;color:var(--faint);padding:11px 0;font-size:11px;font-family:var(--sans);font-weight:500;cursor:pointer;letter-spacing:.4px;text-transform:uppercase;transition:color .12s}
.filters button:hover{color:var(--muted)}
.filters button.active{color:var(--accent);border-bottom-color:var(--accent)}

/* Event list */
.events{flex:1;overflow-y:auto}
.events::-webkit-scrollbar{width:6px}
.events::-webkit-scrollbar-track{background:transparent}
.events::-webkit-scrollbar-thumb{background:var(--border);border-radius:3px}
.event{padding:14px 20px 14px 18px;border-bottom:1px solid var(--border);border-left:2px solid transparent;cursor:pointer;transition:all .12s}
.event:hover{background:var(--surface)}
.event.selected{background:var(--panel);border-left:3px solid var(--accent);box-shadow:inset 0 0 0 1px var(--accent-border)}
.event.event-fail{border-left:2px solid var(--err-border)}
.event.event-fail.selected{border-left:3px solid var(--err);box-shadow:inset 0 0 0 1px var(--err-border)}
.event .top{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:7px}
.event .template{font-size:13px;font-weight:500;color:var(--ink)}
.event .time{font-size:10px;font-family:var(--mono);color:var(--faint);letter-spacing:.3px}
.event .bottom{display:flex;align-items:center;gap:6px}
.event .badge{font-size:9px;font-weight:600;padding:3px 7px;border-radius:3px;letter-spacing:.5px;text-transform:uppercase;border:1px solid transparent}
.event .badge.ok{background:var(--ok-soft);color:var(--ok);border-color:var(--ok-border)}
.event .badge.fail{background:var(--err-soft);color:var(--err);border-color:var(--err-border)}
.event .badge.compliance{background:var(--info-soft);color:var(--info);border-color:var(--info-border)}
.event .pill{font-size:9px;padding:2px 6px;border-radius:3px;font-family:var(--mono);letter-spacing:.2px}
.event .pill.zugferd{background:var(--info-soft);color:var(--info)}
.event .pill.prov{background:var(--accent-soft);color:var(--accent)}
.event .dur{font-size:10px;color:var(--ink2);font-family:var(--mono);font-weight:500;margin-left:auto}
.event .error-line{margin-top:8px;font-size:11px;color:var(--err);font-family:var(--mono);padding-left:1px;line-height:1.5;opacity:.85}

/* Detail pane */
.detail-pane::-webkit-scrollbar{width:6px}
.detail-pane::-webkit-scrollbar-track{background:transparent}
.detail-pane::-webkit-scrollbar-thumb{background:var(--border);border-radius:3px}
.detail-empty{display:flex;align-items:center;justify-content:center;height:100%;color:var(--faint);font-size:13px;letter-spacing:.2px}
.detail{padding:36px 40px}
.detail h2{font-family:var(--display);font-size:29px;font-weight:400;margin-bottom:0;color:var(--ink);letter-spacing:.2px;line-height:1.2}
.detail-header{margin-bottom:28px;padding-bottom:20px;border-bottom:1px solid var(--border);border-left:3px solid var(--accent);padding-left:20px}
.detail-header .header-meta{display:flex;align-items:center;gap:14px;margin-top:10px}
.detail-header .header-meta .otag{font-size:9px;font-weight:600;padding:2px 8px;border-radius:3px;letter-spacing:.6px;text-transform:uppercase;font-family:var(--sans)}
.detail-header .header-meta .otag.ok{background:var(--ok-soft);color:var(--ok);border:1px solid var(--ok-border)}
.detail-header .header-meta .otag.fail{background:var(--err-soft);color:var(--err);border:1px solid var(--err-border)}
.detail-header .header-meta span{font-size:11px;color:var(--muted);font-family:var(--mono)}
.detail .fields{display:grid;grid-template-columns:1fr 1fr;gap:20px 32px;margin-bottom:32px;padding:20px 24px;background:var(--surface);border:1px solid var(--border);border-radius:8px}
.detail .field .label{font-size:9px;text-transform:uppercase;letter-spacing:1.1px;color:var(--faint);margin-bottom:5px;font-weight:500}
.detail .field .val{font-size:13px;color:var(--ink2);font-family:var(--mono);line-height:1.4}
.detail .field .val.ok{color:var(--ok)}
.detail .field .val.fail{color:var(--err)}

/* Pipeline stages */
.pipeline{margin-bottom:32px}
.pipeline h3{font-size:10px;text-transform:uppercase;letter-spacing:1.2px;color:var(--faint);margin-bottom:14px;font-weight:500}
.stage{display:flex;align-items:flex-start;gap:14px;padding:14px 18px;background:var(--surface);border:1px solid var(--border);border-left:3px solid transparent;border-radius:8px;margin-bottom:6px;transition:border-color .12s}
.stage:hover{border-color:var(--border-light)}
.stage.stage-pass{border-left-color:var(--ok-border);background:var(--ok-faint)}
.stage.stage-fail{border-left-color:var(--err-border);background:var(--err-faint)}
.stage.stage-skip{opacity:.6}
.stage.stage-compliance{border-left-color:var(--info-border);background:var(--info-soft)}
.stage .icon{font-size:14px;margin-top:2px;width:16px;flex-shrink:0;opacity:.9}
.stage .icon.pass{color:var(--ok)}
.stage .icon.fail{color:var(--err)}
.stage .icon.skip{color:var(--faint)}
.stage .body{flex:1;min-width:0}
.stage .name{font-size:12px;font-family:var(--mono);font-weight:600;color:var(--ink);letter-spacing:.2px}
.stage .row{display:flex;gap:14px;margin-top:5px}
.stage .row span{font-size:10px;color:var(--muted);font-family:var(--mono);letter-spacing:.2px}
.stage .errors{margin-top:8px;padding-top:8px;border-top:1px solid var(--border)}
.stage .errors div{font-size:11px;color:var(--err);font-family:var(--mono);padding:3px 0;line-height:1.5;opacity:.9}

/* Identity block */
.hashes{background:var(--surface);border:1px solid var(--border);border-top:2px solid var(--accent);border-radius:8px;padding:22px 24px;margin-top:8px}
.hashes h3{font-size:10px;text-transform:uppercase;letter-spacing:1.4px;color:var(--accent);margin-bottom:14px;font-weight:600}
.hashes .row{display:flex;justify-content:space-between;padding:7px 0;font-size:11px;font-family:var(--mono);border-bottom:1px solid var(--border)}
.hashes .row:last-child{border-bottom:none}
.hashes .row .k{color:var(--muted)}
.hashes .row .v{color:var(--ink);text-align:right;font-weight:500}

.empty-state{text-align:center;padding:60px 20px;color:var(--faint)}
.empty-state p{margin-top:8px;font-size:12px;letter-spacing:.2px}
</style>
</head>
<body>
<div class="shell">
  <header>
    <h1>TrustRender</h1>
    <div class="meta">
      <span id="instance-info"></span>
      <span id="last-updated"></span>
      <button id="refresh-btn" onclick="doRefresh()">Refresh</button>
    </div>
  </header>

  <div class="strip">
    <div class="stat"><div class="label">Renders</div><div class="val" id="s-total">-</div></div>
    <div class="stat"><div class="label">Success</div><div class="val" id="s-rate">-</div></div>
    <div class="stat"><div class="label">Avg Duration</div><div class="val" id="s-avg">-</div></div>
    <div class="stat"><div class="label">Failures</div><div class="val" id="s-fail">-</div></div>
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

function updateTimestamp(){
  const now=new Date();
  document.getElementById('last-updated').textContent=now.toLocaleTimeString([],{hour:'2-digit',minute:'2-digit',second:'2-digit'});
}

function doRefresh(){
  const btn=document.getElementById('refresh-btn');
  btn.textContent='Refreshed';btn.style.color='var(--ok)';btn.style.borderColor='var(--ok-border)';
  setTimeout(()=>{btn.textContent='Refresh';btn.style.color='';btn.style.borderColor='';},1000);
  loadData();
}

async function loadData(){
  const [sr,hr]=await Promise.all([fetch('/stats'),fetch('/history?limit=100'+(filter==='error'?'&outcome=error':''))]);
  const stats=await sr.json(), traces=await hr.json();
  updateTimestamp();
  document.getElementById('s-total').textContent=stats.total;
  const rateEl=document.getElementById('s-rate');
  rateEl.textContent=stats.total>0?stats.success_rate+'%':'-';
  rateEl.className='val sage primary'+(stats.success_rate===100&&stats.total>0?' perfect':'');
  document.getElementById('s-avg').textContent=stats.avg_ms+'ms';
  const failEl=document.getElementById('s-fail');
  failEl.textContent=stats.failures;
  failEl.className='val wine primary'+(stats.failures>0?' hot':'');
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
  if(!traces.length){el.innerHTML='<div class="empty-state"><p>No renders recorded</p><p>Set TRUSTRENDER_HISTORY to enable</p></div>';return}
  el.innerHTML=traces.map(t=>{
    const time=t.timestamp.substring(11,19);
    const sel=(t.id===selectedId?' selected':'')+(t.outcome==='error'?' event-fail':'');
    const badge=t.outcome==='success'?'<span class="badge ok">OK</span>':'<span class="badge fail">FAIL</span>';
    const compBadge=t.zugferd_profile?'<span class="badge compliance">EN16931</span>':'';
    let pills='';
    if(t.provenance_hash) pills+='<span class="pill prov">provenance</span>';
    const dur=t.total_ms+'ms';
    let err='';
    if(t.outcome==='error') err='<div class="error-line">'+t.error_code+' at '+t.error_stage+'</div>';
    return '<div class="event'+sel+'" onclick="selectTrace(&quot;'+t.id+'&quot;)"><div class="top"><span class="template">'+t.template_name+'</span><span class="time">'+time+'</span></div><div class="bottom">'+badge+compBadge+pills+'<span class="dur">'+dur+'</span></div>'+err+'</div>';
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
  const res=await fetch('/history/'+id);
  const t=await res.json();
  showDetail(t);
}

function showDetail(t){
  const p=document.getElementById('detail-pane');
  const otag=t.outcome==='success'?'<span class="otag ok">OK</span>':'<span class="otag fail">FAIL</span>';
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
      const isComp=s.stage==='zugferd_validation'||s.stage==='zugferd_postprocess';
      const stageCls=isComp&&cls==='pass'?' stage-compliance':cls==='pass'?' stage-pass':cls==='fail'?' stage-fail':' stage-skip';
      let errs='';
      if(s.errors&&s.errors.length){
        errs='<div class="errors">'+s.errors.map(e=>'<div>'+e.path+': '+e.message+'</div>').join('')+'</div>';
      }
      return '<div class="stage'+stageCls+'"><div class="icon '+cls+'">'+icon+'</div><div class="body"><div class="name">'+s.stage+'</div><div class="row"><span>'+s.status+'</span><span>'+s.duration_ms+'ms</span>'+(meta.length?'<span>'+meta.join(' \\u00b7 ')+'</span>':'')+'</div>'+errs+'</div></div>';
    }).join('');
  }
  p.innerHTML='<div class="detail"><div class="detail-header"><h2>'+t.template_name+'</h2><div class="header-meta">'+otag+'<span>'+t.total_ms+'ms</span><span>'+t.timestamp.replace('T',' ').substring(0,19)+'</span></div></div><div class="fields"><div class="field"><div class="label">Outcome</div>'+outcome+'</div><div class="field"><div class="label">Duration</div><div class="val">'+t.total_ms+'ms</div></div>'+(t.pdf_size?'<div class="field"><div class="label">PDF Size</div><div class="val">'+Math.round(t.pdf_size/1024)+'KB</div></div>':'')+'<div class="field"><div class="label">Time</div><div class="val">'+t.timestamp.replace('T',' ').substring(0,19)+'</div></div>'+(t.zugferd_profile?'<div class="field"><div class="label">Compliance</div><div class="val">'+t.zugferd_profile+'</div></div>':'')+(t.provenance_hash?'<div class="field"><div class="label">Provenance</div><div class="val">'+t.provenance_hash.substring(0,24)+'...</div></div>':'')+(t.error_code?'<div class="field"><div class="label">Error</div><div class="val fail">'+t.error_code+'</div></div><div class="field"><div class="label">Stage</div><div class="val fail">'+t.error_stage+'</div></div>':'')+'</div><div class="pipeline"><h3>Pipeline Stages</h3>'+stagesHtml+'</div><div class="hashes"><h3>Identity</h3><div class="row"><span class="k">Trace ID</span><span class="v">'+t.id+'</span></div><div class="row"><span class="k">Template</span><span class="v">'+t.template_hash+'</span></div><div class="row"><span class="k">Data</span><span class="v">'+t.data_hash+'</span></div>'+(t.output_hash?'<div class="row"><span class="k">Output</span><span class="v">'+t.output_hash+'</span></div>':'')+'<div class="row"><span class="k">Engine</span><span class="v">trustrender '+t.engine_version+'</span></div></div></div>';
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
        Route("/history", api_history, methods=["GET"]),
        Route("/history/{trace_id}", api_trace, methods=["GET"]),
        Route("/stats", api_stats, methods=["GET"]),
    ]
