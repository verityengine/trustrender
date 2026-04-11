"""HTTP server for Formforge — thin wrapper over the render pipeline.

Endpoints:
    POST /render     — render a template to PDF
    POST /preflight  — readiness check (no render)
    GET  /health     — health check

Execution model:
    The server uses ``TypstCliBackend`` for all renders.  This provides a
    subprocess boundary so that timeouts actually kill the running compile
    process.  The execution mode is fixed at app creation — it is a
    deployment-level decision, not a per-request choice.

Timeout:
    Primary timeout is the subprocess kill via ``subprocess.run(timeout=X)``
    inside ``TypstCliBackend``.  A secondary watchdog
    (``asyncio.wait_for(timeout + 5)``) provides a defensive backstop in case
    the subprocess kill is slow or cleanup stalls.  The watchdog should never
    fire in normal operation.
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from pathlib import Path

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from . import FormforgeError, RenderResult, __version__, _build_font_paths, _render_document_pipeline
from .engine import TypstCliBackend
from .errors import ErrorCode

MAX_BODY_SIZE = 1_048_576  # 1 MB
RENDER_TIMEOUT = 30  # seconds
ALLOWED_FIELDS = {"template", "data", "debug", "validate", "zugferd", "provenance"}
PREFLIGHT_FIELDS = {"template", "data", "zugferd"}


def _server_render(
    template_path: Path,
    data: dict,
    *,
    debug: bool,
    validate: bool,
    zugferd: str | None,
    provenance: bool,
    font_paths: list[str] | None,
    timeout: float,
) -> bytes:
    """Server render path: CLI subprocess backend for killable execution.

    Delegates to ``_render_document_pipeline()`` — the shared pipeline that
    is also used by ``render()``.  The only server-specific concern is
    forcing the CLI subprocess backend for real timeout/kill behavior.
    """
    backend = TypstCliBackend(compile_timeout=timeout)
    return _render_document_pipeline(  # returns RenderResult
        template_path,
        data,
        debug=debug,
        font_paths=font_paths,
        validate=validate,
        zugferd=zugferd,
        provenance=provenance,
        backend=backend,
        timeout=timeout,
    )


def create_app(
    templates_dir: str | Path,
    *,
    debug: bool = False,
    font_paths: list[str | os.PathLike] | None = None,
    render_timeout: float = RENDER_TIMEOUT,
    dashboard: bool = False,
    history_path: str | None = None,
) -> Starlette:
    """Create the Starlette application.

    The server always uses the CLI subprocess backend for killable execution.
    Timeout is real: timed-out renders are terminated, not just abandoned.

    Args:
        templates_dir: Root directory for templates. All template paths
            in requests are resolved relative to this directory.
            Only relative paths are accepted — no absolute paths, no ``..``.
        debug: If True, preserve intermediate .typ files on render errors
            and include source_path in error responses.
        font_paths: Additional font directories to pass to the renderer.
        render_timeout: Maximum seconds for a render request (default 30).
    """
    templates_dir = Path(templates_dir).resolve()
    # Resolve font paths once at startup — same precedence as render():
    # explicit paths + bundled fonts + system fonts (Typst default)
    resolved_fonts = _build_font_paths(font_paths)

    async def health(request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok", "version": __version__})

    async def render_endpoint(request: Request) -> Response:
        request_id = request.state.request_id

        # Enforce body size before parsing
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > MAX_BODY_SIZE:
            return _error(
                400,
                ErrorCode.INVALID_DATA,
                "Request body too large",
                request_id,
                stage="execution",
            )

        # Parse JSON body
        body = await request.body()
        if len(body) > MAX_BODY_SIZE:
            return _error(
                400,
                ErrorCode.INVALID_DATA,
                "Request body too large",
                request_id,
                stage="execution",
            )

        try:
            payload = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            return _error(
                400,
                ErrorCode.INVALID_DATA,
                f"Invalid JSON: {exc}",
                request_id,
                stage="execution",
            )

        if not isinstance(payload, dict):
            return _error(
                400,
                ErrorCode.INVALID_DATA,
                "Request body must be a JSON object",
                request_id,
                stage="execution",
            )

        # Validate fields
        unknown = set(payload.keys()) - ALLOWED_FIELDS
        if unknown:
            return _error(
                400,
                ErrorCode.INVALID_DATA,
                f"Unknown fields: {', '.join(sorted(unknown))}",
                request_id,
                stage="execution",
            )

        template_name = payload.get("template")
        data = payload.get("data")
        req_debug = payload.get("debug", False)
        req_validate = payload.get("validate", True)
        req_zugferd = payload.get("zugferd")
        req_provenance = payload.get("provenance", False)

        if not template_name or not isinstance(template_name, str):
            return _error(
                400,
                ErrorCode.INVALID_DATA,
                "Missing or invalid 'template' field",
                request_id,
                stage="execution",
            )
        if data is None or not isinstance(data, dict):
            return _error(
                400,
                ErrorCode.INVALID_DATA,
                "Missing or invalid 'data' field",
                request_id,
                stage="execution",
            )
        if not isinstance(req_debug, bool):
            return _error(
                400,
                ErrorCode.INVALID_DATA,
                "'debug' must be a boolean",
                request_id,
                stage="execution",
            )
        if req_zugferd is not None and req_zugferd not in ("en16931", "xrechnung"):
            return _error(
                400,
                ErrorCode.INVALID_DATA,
                "'zugferd' must be 'en16931' or 'xrechnung'",
                request_id,
                stage="execution",
            )

        # Path traversal protection
        template_path = (templates_dir / template_name).resolve()
        if not str(template_path).startswith(str(templates_dir)):
            return _error(
                400,
                ErrorCode.INVALID_DATA,
                "Invalid template path",
                request_id,
                stage="execution",
            )
        if not template_path.exists():
            return _error(
                404,
                ErrorCode.TEMPLATE_NOT_FOUND,
                f"Template not found: {template_name}",
                request_id,
                stage="execution",
            )

        # Render with killable execution via CLI subprocess backend.
        # Primary timeout: subprocess kill inside TypstCliBackend.
        # Watchdog: asyncio.wait_for with extra margin — defensive backstop
        # only, should never fire in normal operation.
        use_debug = debug or req_debug
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(
                    _server_render,
                    template_path,
                    data,
                    debug=use_debug,
                    validate=req_validate,
                    zugferd=req_zugferd,
                    provenance=req_provenance,
                    font_paths=resolved_fonts,
                    timeout=render_timeout,
                ),
                timeout=render_timeout + 5,  # watchdog — subprocess kill is primary
            )
        except asyncio.TimeoutError:
            # Watchdog fired — subprocess kill was slow or stuck.
            # This is an exceptional event; the primary subprocess timeout
            # should have handled it.
            return _error(
                504,
                ErrorCode.RENDER_TIMEOUT,
                f"Render timed out after {render_timeout}s (watchdog)",
                request_id,
                stage="execution",
            )
        except FormforgeError as exc:
            if exc.code == ErrorCode.RENDER_TIMEOUT:
                status = 504
            elif exc.code in (ErrorCode.DATA_CONTRACT, ErrorCode.ZUGFERD_ERROR):
                status = 422
            elif exc.code == ErrorCode.INVALID_DATA:
                status = 400
            else:
                status = 500
            error_data = exc.to_dict(include_debug=use_debug)
            error_data["request_id"] = request_id
            return JSONResponse(
                error_data,
                status_code=status,
                headers={"X-Request-ID": request_id},
            )

        headers = {
            "Content-Disposition": "inline",
            "X-Request-ID": request_id,
        }
        if result.trace_id:
            headers["X-Trace-ID"] = result.trace_id

        return Response(
            content=result.pdf_bytes,
            media_type="application/pdf",
            headers=headers,
        )

    async def preflight_endpoint(request: Request) -> JSONResponse:
        """Pre-render readiness check — no rendering, just validation."""
        from dataclasses import asdict

        from .readiness import preflight

        request_id = request.state.request_id

        # Same body parsing as /render
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > MAX_BODY_SIZE:
            return _error(400, ErrorCode.INVALID_DATA, "Request body too large", request_id, stage="execution")

        body = await request.body()
        if len(body) > MAX_BODY_SIZE:
            return _error(400, ErrorCode.INVALID_DATA, "Request body too large", request_id, stage="execution")

        try:
            payload = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            return _error(400, ErrorCode.INVALID_DATA, f"Invalid JSON: {exc}", request_id, stage="execution")

        if not isinstance(payload, dict):
            return _error(400, ErrorCode.INVALID_DATA, "Request body must be a JSON object", request_id, stage="execution")

        unknown = set(payload.keys()) - PREFLIGHT_FIELDS
        if unknown:
            return _error(400, ErrorCode.INVALID_DATA, f"Unknown fields: {', '.join(sorted(unknown))}", request_id, stage="execution")

        template_name = payload.get("template")
        data = payload.get("data")
        req_zugferd = payload.get("zugferd")

        if not template_name or not isinstance(template_name, str):
            return _error(400, ErrorCode.INVALID_DATA, "Missing or invalid 'template' field", request_id, stage="execution")
        if data is None or not isinstance(data, dict):
            return _error(400, ErrorCode.INVALID_DATA, "Missing or invalid 'data' field", request_id, stage="execution")
        if req_zugferd is not None and req_zugferd not in ("en16931", "xrechnung"):
            return _error(400, ErrorCode.INVALID_DATA, "'zugferd' must be 'en16931' or 'xrechnung'", request_id, stage="execution")

        # Same path traversal protection as /render
        template_path = (templates_dir / template_name).resolve()
        if not str(template_path).startswith(str(templates_dir)):
            return _error(400, ErrorCode.INVALID_DATA, "Invalid template path", request_id, stage="execution")
        if not template_path.exists():
            return _error(404, ErrorCode.TEMPLATE_NOT_FOUND, f"Template not found: {template_name}", request_id, stage="execution")

        verdict = preflight(template_path, data, zugferd=req_zugferd)
        return JSONResponse(
            {
                "ready": verdict.ready,
                "errors": [asdict(e) for e in verdict.errors],
                "warnings": [asdict(e) for e in verdict.warnings],
                "profile_eligible": verdict.profile_eligible,
                "stages_checked": verdict.stages_checked,
                "checked_at": verdict.checked_at,
            },
            headers={"X-Request-ID": request_id},
        )

    async def request_id_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    from starlette.middleware.base import BaseHTTPMiddleware

    # Initialize trace store for history/dashboard
    if history_path:
        from .trace import init_store

        trace_store = init_store(history_path)
    else:
        from .trace import get_store

        trace_store = get_store()

    routes = [
        Route("/health", health, methods=["GET"]),
        Route("/render", render_endpoint, methods=["POST"]),
        Route("/preflight", preflight_endpoint, methods=["POST"]),
    ]

    # Always mount trace API (returns 503 if history not enabled).
    # Routes use bare paths (no /api/ prefix) because the Vite dev proxy
    # strips /api/ before forwarding.  In production the server is accessed
    # directly, so these paths work either way.
    from .dashboard import api_history, api_stats, api_trace

    routes.extend([
        Route("/history", api_history, methods=["GET"]),
        Route("/history/{trace_id}", api_trace, methods=["GET"]),
        Route("/stats", api_stats, methods=["GET"]),
    ])

    if dashboard and trace_store:
        from .dashboard import dashboard_routes

        routes.extend([r for r in dashboard_routes() if r.path == "/dashboard"])

    app = Starlette(
        routes=routes,
        middleware=[
            Middleware(BaseHTTPMiddleware, dispatch=request_id_middleware),
        ],
    )

    # Store trace_store on app state for dashboard API access
    app.state.trace_store = trace_store

    return app


def _error(
    status: int,
    code: ErrorCode,
    message: str,
    request_id: str,
    *,
    stage: str = "unknown",
) -> JSONResponse:
    return JSONResponse(
        {
            "error": code.value,
            "message": message,
            "stage": stage,
            "request_id": request_id,
        },
        status_code=status,
        headers={"X-Request-ID": request_id},
    )
