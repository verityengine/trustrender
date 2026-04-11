"""HTTP server for Formforge — thin wrapper over the render pipeline.

Endpoints:
    POST /render  — render a template to PDF
    GET  /health  — health check

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

from . import FormforgeError, __version__, _build_font_paths
from .engine import TypstCliBackend, compile_typst, compile_typst_file
from .errors import ErrorCode
from .templates import render_template

MAX_BODY_SIZE = 1_048_576  # 1 MB
RENDER_TIMEOUT = 30  # seconds
ALLOWED_FIELDS = {"template", "data", "debug"}


def _server_render(
    template_path: Path,
    data: dict,
    *,
    debug: bool,
    font_paths: list[str] | None,
    timeout: float,
) -> bytes:
    """Server render path: CLI subprocess backend for killable execution.

    Replicates ``render()``'s pipeline semantics exactly — same template
    resolution, Jinja behavior, debug artifacts, font precedence, error
    classification, and asset resolution.  The only difference is the
    execution model: subprocess boundary enables real timeout/kill.

    This bypass exists only for killable execution, not to change semantics.
    """
    backend = TypstCliBackend(compile_timeout=timeout)

    if template_path.name.endswith(".j2.typ"):
        rendered = render_template(template_path, data)
        return compile_typst(
            rendered,
            template_path.parent,
            debug=debug,
            font_paths=font_paths,
            template_path=template_path,
            backend=backend,
            timeout=timeout,
        )
    else:
        return compile_typst_file(
            template_path,
            font_paths=font_paths,
            backend=backend,
            timeout=timeout,
        )


def create_app(
    templates_dir: str | Path,
    *,
    debug: bool = False,
    font_paths: list[str | os.PathLike] | None = None,
    render_timeout: float = RENDER_TIMEOUT,
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
            pdf_bytes = await asyncio.wait_for(
                asyncio.to_thread(
                    _server_render,
                    template_path,
                    data,
                    debug=use_debug,
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
            status = 504 if exc.code == ErrorCode.RENDER_TIMEOUT else 500
            error_data = exc.to_dict(include_debug=use_debug)
            error_data["request_id"] = request_id
            return JSONResponse(
                error_data,
                status_code=status,
                headers={"X-Request-ID": request_id},
            )

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": "inline",
                "X-Request-ID": request_id,
            },
        )

    async def request_id_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    from starlette.middleware.base import BaseHTTPMiddleware

    app = Starlette(
        routes=[
            Route("/health", health, methods=["GET"]),
            Route("/render", render_endpoint, methods=["POST"]),
        ],
        middleware=[
            Middleware(BaseHTTPMiddleware, dispatch=request_id_middleware),
        ],
    )
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
