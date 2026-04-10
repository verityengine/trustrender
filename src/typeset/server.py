"""HTTP server for Typeset — thin wrapper over the render pipeline.

Endpoints:
    POST /render  — render a template to PDF
    GET  /health  — health check

Timeout note:
    Render timeout uses ``asyncio.wait_for`` around a thread-pool call.
    This is timeout-at-response-layer, not guaranteed render cancellation.
    If the timeout fires, the underlying render thread may still complete
    naturally.  Acceptable for now.
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

from . import TypesetError, __version__, render

MAX_BODY_SIZE = 1_048_576  # 1 MB
RENDER_TIMEOUT = 30  # seconds
ALLOWED_FIELDS = {"template", "data", "debug"}


def create_app(
    templates_dir: str | Path,
    *,
    debug: bool = False,
    font_paths: list[str | os.PathLike] | None = None,
    render_timeout: float = RENDER_TIMEOUT,
) -> Starlette:
    """Create the Starlette application.

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

    async def health(request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok", "version": __version__})

    async def render_endpoint(request: Request) -> Response:
        request_id = request.state.request_id

        # Enforce body size before parsing
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > MAX_BODY_SIZE:
            return _error(400, "Request body too large", request_id)

        # Parse JSON body
        body = await request.body()
        if len(body) > MAX_BODY_SIZE:
            return _error(400, "Request body too large", request_id)

        try:
            payload = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            return _error(400, f"Invalid JSON: {exc}", request_id)

        if not isinstance(payload, dict):
            return _error(400, "Request body must be a JSON object", request_id)

        # Validate fields
        unknown = set(payload.keys()) - ALLOWED_FIELDS
        if unknown:
            return _error(
                400,
                f"Unknown fields: {', '.join(sorted(unknown))}",
                request_id,
            )

        template_name = payload.get("template")
        data = payload.get("data")
        req_debug = payload.get("debug", False)

        if not template_name or not isinstance(template_name, str):
            return _error(400, "Missing or invalid 'template' field", request_id)
        if data is None or not isinstance(data, dict):
            return _error(400, "Missing or invalid 'data' field", request_id)
        if not isinstance(req_debug, bool):
            return _error(400, "'debug' must be a boolean", request_id)

        # Path traversal protection
        template_path = (templates_dir / template_name).resolve()
        if not str(template_path).startswith(str(templates_dir)):
            return _error(400, "Invalid template path", request_id)
        if not template_path.exists():
            return _error(404, f"Template not found: {template_name}", request_id)

        # Render with timeout
        use_debug = debug or req_debug
        try:
            pdf_bytes = await asyncio.wait_for(
                asyncio.to_thread(
                    render,
                    template_path,
                    data,
                    debug=use_debug,
                    font_paths=font_paths,
                ),
                timeout=render_timeout,
            )
        except asyncio.TimeoutError:
            return _error(504, "Render timed out", request_id)
        except TypesetError as exc:
            error_data: dict = {
                "error": "TypesetError",
                "message": str(exc).split("\n")[0],
                "request_id": request_id,
            }
            if use_debug and exc.source_path:
                error_data["source_path"] = exc.source_path
            return JSONResponse(error_data, status_code=500)

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


def _error(status: int, message: str, request_id: str) -> JSONResponse:
    return JSONResponse(
        {"error": message, "request_id": request_id},
        status_code=status,
        headers={"X-Request-ID": request_id},
    )
