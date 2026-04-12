"""HTTP server for TrustRender — thin wrapper over the render pipeline.

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
import logging
import os
import time
import uuid
from pathlib import Path

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route

from . import TrustRenderError, RenderResult, __version__, _build_font_paths, _render_document_pipeline
from .engine import TypstCliBackend
from .errors import ErrorCode

logger = logging.getLogger("trustrender.server")

DEFAULT_MAX_BODY_SIZE = 10_485_760  # 10 MB
MAX_TEMPLATE_SOURCE_SIZE = 262_144  # 256 KB — templates should be small
RENDER_TIMEOUT = 30  # seconds
MAX_CONCURRENT_RENDERS = 8  # backpressure: reject with 503 when at capacity
ALLOWED_FIELDS = {"template", "data", "debug", "validate", "zugferd", "provenance", "template_source"}
PREFLIGHT_FIELDS = {"template", "data", "zugferd", "template_source"}


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
    display_name: str | None = None,
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
        display_name=display_name,
    )


def create_app(
    templates_dir: str | Path,
    *,
    debug: bool = False,
    font_paths: list[str | os.PathLike] | None = None,
    render_timeout: float = RENDER_TIMEOUT,
    max_concurrent_renders: int = MAX_CONCURRENT_RENDERS,
    max_body_size: int = DEFAULT_MAX_BODY_SIZE,
    dashboard: bool = False,
    history_path: str | None = None,
    cors_origins: list[str] | None = None,
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
        max_concurrent_renders: Maximum simultaneous render operations.
            When at capacity, new requests get 503.  Default 8.
    """
    templates_dir = Path(templates_dir).resolve()
    # Resolve font paths once at startup — same precedence as render():
    # explicit paths + bundled fonts + system fonts (Typst default)
    resolved_fonts = _build_font_paths(font_paths)
    render_semaphore = asyncio.Semaphore(max_concurrent_renders)

    logger.info(
        "server.startup templates_dir=%s max_concurrent=%d timeout=%ds debug=%s version=%s",
        templates_dir, max_concurrent_renders, render_timeout, debug, __version__,
    )

    async def health(request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok", "version": __version__})

    async def templates_list_endpoint(request: Request) -> JSONResponse:
        """List available templates in the templates directory."""
        templates = []
        for p in sorted(templates_dir.glob("**/*")):
            if p.suffix == ".typ" and p.is_file():
                rel = str(p.relative_to(templates_dir))
                has_data = (templates_dir / (p.stem.replace(".j2", "") + "_data.json")).exists()
                templates.append({"name": rel, "has_data": has_data})
        return JSONResponse({"templates": templates})

    async def template_source_endpoint(request: Request) -> Response:
        """Return raw template source for browser-based editing."""
        request_id = request.state.request_id
        name = request.query_params.get("name")
        if not name or not isinstance(name, str):
            return _error(400, ErrorCode.INVALID_DATA, "Missing 'name' query parameter", request_id, stage="execution")

        # Path traversal protection
        template_path = (templates_dir / name).resolve()
        if not str(template_path).startswith(str(templates_dir)):
            return _error(400, ErrorCode.INVALID_DATA, "Invalid template path", request_id, stage="execution")
        if not template_path.exists():
            return _error(404, ErrorCode.TEMPLATE_NOT_FOUND, f"Template not found: {name}", request_id, stage="execution")

        source = template_path.read_text(encoding="utf-8")
        return JSONResponse({"source": source}, headers={"X-Request-ID": request_id})

    async def template_data_endpoint(request: Request) -> Response:
        """Return matching JSON data file for a template."""
        request_id = request.state.request_id
        name = request.query_params.get("name")
        if not name or not isinstance(name, str):
            return _error(400, ErrorCode.INVALID_DATA, "Missing 'name' query parameter", request_id, stage="execution")

        # Derive data file name: invoice.j2.typ -> invoice_data.json
        base = name.replace(".j2.typ", "").replace(".typ", "")
        data_path = (templates_dir / f"{base}_data.json").resolve()
        if not str(data_path).startswith(str(templates_dir)):
            return _error(400, ErrorCode.INVALID_DATA, "Invalid path", request_id, stage="execution")
        if not data_path.exists():
            return JSONResponse({"data": None}, headers={"X-Request-ID": request_id})

        import json
        with open(data_path) as f:
            data = json.load(f)
        return JSONResponse({"data": data}, headers={"X-Request-ID": request_id})

    def _write_ephemeral_template(template_name: str, source: str) -> Path:
        """Write ephemeral template source to a temp file for pipeline consumption.

        Uses the same ``_trustrender_*`` naming pattern as Jinja2 preprocessing.
        The caller is responsible for cleanup.
        """
        import random
        import string

        suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
        # Preserve extension so the pipeline detects Jinja2 vs raw Typst
        ext = "".join(Path(template_name).suffixes)  # e.g. ".j2.typ"
        temp_path = templates_dir / f"_trustrender_{suffix}{ext}"
        temp_path.write_text(source, encoding="utf-8")
        return temp_path

    async def render_endpoint(request: Request) -> Response:
        request_id = request.state.request_id

        # Enforce body size before parsing
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > max_body_size:
            return _error(
                400,
                ErrorCode.INVALID_DATA,
                f"Request body too large (limit: {max_body_size:,} bytes)",
                request_id,
                stage="execution",
            )

        # Parse JSON body
        body = await request.body()
        if len(body) > max_body_size:
            return _error(
                400,
                ErrorCode.INVALID_DATA,
                f"Request body too large (limit: {max_body_size:,} bytes)",
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
        if req_zugferd is not None and req_zugferd not in ("en16931",):
            return _error(
                400,
                ErrorCode.INVALID_DATA,
                "'zugferd' must be 'en16931'",
                request_id,
                stage="execution",
            )

        # Ephemeral template source: write to temp file for pipeline consumption
        template_source = payload.get("template_source")
        ephemeral_path = None
        if template_source is not None:
            if not isinstance(template_source, str):
                return _error(400, ErrorCode.INVALID_DATA, "'template_source' must be a string", request_id, stage="execution")
            if len(template_source.encode("utf-8")) > MAX_TEMPLATE_SOURCE_SIZE:
                return _error(400, ErrorCode.INVALID_DATA, f"'template_source' exceeds {MAX_TEMPLATE_SOURCE_SIZE // 1024}KB limit", request_id, stage="execution")
            # Still validate that the base template exists (for include resolution context)
            base_path = (templates_dir / template_name).resolve()
            if not str(base_path).startswith(str(templates_dir)):
                return _error(400, ErrorCode.INVALID_DATA, "Invalid template path", request_id, stage="execution")
            if not base_path.exists():
                return _error(404, ErrorCode.TEMPLATE_NOT_FOUND, f"Base template not found: {template_name}", request_id, stage="execution")
            ephemeral_path = _write_ephemeral_template(template_name, template_source)
            template_path = ephemeral_path
        else:
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
        # Backpressure: semaphore limits concurrent renders; excess gets 503.
        use_debug = debug or req_debug
        if render_semaphore.locked():
            if ephemeral_path:
                ephemeral_path.unlink(missing_ok=True)
            logger.warning(
                "render.backpressure request_id=%s template=%s concurrent=%d",
                request_id, template_name, max_concurrent_renders,
            )
            return _error(
                503,
                ErrorCode.RENDER_TIMEOUT,
                f"Server at capacity ({max_concurrent_renders} concurrent renders)",
                request_id,
                stage="execution",
            )
        t_start = time.monotonic()
        logger.info("render.start request_id=%s template=%s zugferd=%s", request_id, template_name, req_zugferd)
        try:
            try:
                async with render_semaphore:
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
                            display_name=template_name if ephemeral_path else None,
                        ),
                        timeout=render_timeout + 5,  # watchdog — subprocess kill is primary
                    )
            except asyncio.TimeoutError:
                elapsed_ms = (time.monotonic() - t_start) * 1000
                logger.error(
                    "render.timeout request_id=%s template=%s elapsed_ms=%.0f",
                    request_id, template_name, elapsed_ms,
                )
                return _error(
                    504,
                    ErrorCode.RENDER_TIMEOUT,
                    f"Render timed out after {render_timeout}s (watchdog)",
                    request_id,
                    stage="execution",
                )
            except TrustRenderError as exc:
                elapsed_ms = (time.monotonic() - t_start) * 1000
                if exc.code == ErrorCode.RENDER_TIMEOUT:
                    status = 504
                elif exc.code in (ErrorCode.DATA_CONTRACT, ErrorCode.ZUGFERD_ERROR):
                    status = 422
                elif exc.code == ErrorCode.INVALID_DATA:
                    status = 400
                else:
                    status = 500
                logger.warning(
                    "render.error request_id=%s template=%s code=%s status=%d elapsed_ms=%.0f",
                    request_id, template_name, exc.code.value, status, elapsed_ms,
                )
                error_data = exc.to_dict(include_debug=use_debug)
                error_data["request_id"] = request_id
                return JSONResponse(
                    error_data,
                    status_code=status,
                    headers={"X-Request-ID": request_id},
                )

            elapsed_ms = (time.monotonic() - t_start) * 1000
            pdf_size = len(result.pdf_bytes)
            logger.info(
                "render.ok request_id=%s template=%s elapsed_ms=%.0f pdf_bytes=%d",
                request_id, template_name, elapsed_ms, pdf_size,
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
        finally:
            if ephemeral_path:
                ephemeral_path.unlink(missing_ok=True)

    async def preflight_endpoint(request: Request) -> JSONResponse:
        """Pre-render readiness check — no rendering, just validation."""
        from dataclasses import asdict

        from .readiness import preflight

        request_id = request.state.request_id

        # Same body parsing as /render
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > max_body_size:
            return _error(400, ErrorCode.INVALID_DATA, f"Request body too large (limit: {max_body_size:,} bytes)", request_id, stage="execution")

        body = await request.body()
        if len(body) > max_body_size:
            return _error(400, ErrorCode.INVALID_DATA, f"Request body too large (limit: {max_body_size:,} bytes)", request_id, stage="execution")

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
        if req_zugferd is not None and req_zugferd not in ("en16931",):
            return _error(400, ErrorCode.INVALID_DATA, "'zugferd' must be 'en16931'", request_id, stage="execution")

        # Ephemeral template source support
        template_source = payload.get("template_source")
        ephemeral_path = None
        if template_source is not None:
            if not isinstance(template_source, str):
                return _error(400, ErrorCode.INVALID_DATA, "'template_source' must be a string", request_id, stage="execution")
            if len(template_source.encode("utf-8")) > MAX_TEMPLATE_SOURCE_SIZE:
                return _error(400, ErrorCode.INVALID_DATA, f"'template_source' exceeds {MAX_TEMPLATE_SOURCE_SIZE // 1024}KB limit", request_id, stage="execution")
            base_path = (templates_dir / template_name).resolve()
            if not str(base_path).startswith(str(templates_dir)):
                return _error(400, ErrorCode.INVALID_DATA, "Invalid template path", request_id, stage="execution")
            if not base_path.exists():
                return _error(404, ErrorCode.TEMPLATE_NOT_FOUND, f"Base template not found: {template_name}", request_id, stage="execution")
            ephemeral_path = _write_ephemeral_template(template_name, template_source)
            template_path = ephemeral_path
        else:
            # Same path traversal protection as /render
            template_path = (templates_dir / template_name).resolve()
            if not str(template_path).startswith(str(templates_dir)):
                return _error(400, ErrorCode.INVALID_DATA, "Invalid template path", request_id, stage="execution")
            if not template_path.exists():
                return _error(404, ErrorCode.TEMPLATE_NOT_FOUND, f"Template not found: {template_name}", request_id, stage="execution")

        try:
            verdict = preflight(template_path, data, font_paths=resolved_fonts, zugferd=req_zugferd)
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
        finally:
            if ephemeral_path:
                ephemeral_path.unlink(missing_ok=True)

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
        Route("/template-source", template_source_endpoint, methods=["GET"]),
        Route("/templates", templates_list_endpoint, methods=["GET"]),
        Route("/template-data", template_data_endpoint, methods=["GET"]),
    ]

    # Always mount trace API (returns 503 if history not enabled).
    # All routes use bare paths — one canonical surface.  The Vite dev
    # proxy handles the /api/ prefix in development; the production
    # build calls these paths directly.
    from .dashboard import api_history, api_stats, api_trace

    routes.extend([
        Route("/history", api_history, methods=["GET"]),
        Route("/history/{trace_id}", api_trace, methods=["GET"]),
        Route("/stats", api_stats, methods=["GET"]),
    ])

    # /api/ route group: same endpoints under /api/ prefix for the bundled
    # playground frontend (which always calls /api/...).
    api_routes = [
        Route("/health", health, methods=["GET"]),
        Route("/render", render_endpoint, methods=["POST"]),
        Route("/preflight", preflight_endpoint, methods=["POST"]),
        Route("/template-source", template_source_endpoint, methods=["GET"]),
        Route("/templates", templates_list_endpoint, methods=["GET"]),
        Route("/template-data", template_data_endpoint, methods=["GET"]),
        Route("/history", api_history, methods=["GET"]),
        Route("/history/{trace_id}", api_trace, methods=["GET"]),
        Route("/stats", api_stats, methods=["GET"]),
    ]
    routes.append(Mount("/api", routes=api_routes))

    if dashboard and trace_store:
        from .dashboard import dashboard_routes

        routes.extend([r for r in dashboard_routes() if r.path == "/dashboard"])

    # Bundled playground: serve built static files at / if they exist.
    # Must be mounted last so API routes and /dashboard take precedence.
    playground_dir = Path(__file__).parent / "playground"
    if playground_dir.is_dir() and (playground_dir / "index.html").exists():
        from starlette.staticfiles import StaticFiles
        routes.append(Mount("/", app=StaticFiles(directory=str(playground_dir), html=True), name="playground"))

    middleware_stack = [
        Middleware(BaseHTTPMiddleware, dispatch=request_id_middleware),
    ]

    if cors_origins:
        from starlette.middleware.cors import CORSMiddleware

        middleware_stack.insert(0, Middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["Content-Type", "X-Request-ID"],
        ))
        logger.info("CORS enabled for origins: %s", cors_origins)

    app = Starlette(
        routes=routes,
        middleware=middleware_stack,
    )

    # Store trace_store on app state for dashboard API access
    app.state.trace_store = trace_store
    app.state.render_semaphore = render_semaphore

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
