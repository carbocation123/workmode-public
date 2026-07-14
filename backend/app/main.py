from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import APP_NAME, APP_VERSION, settings
from .history_repair import repair_stale_tool_runs
from .literature_routes import router as literature_router
from .routes import router
from .storage import data_dir, ensure_data_dirs, sessions_dir


logger = logging.getLogger(__name__)


app = FastAPI(title=APP_NAME, version=APP_VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.allowed_origins),
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-Workmode-Token"],
)


@app.middleware("http")
async def local_security_boundary(request: Request, call_next):
    if settings.auth_token and request.url.path.startswith("/api") and request.url.path != "/api/health":
        token = request.headers.get("X-Workmode-Token") or request.query_params.get("token")
        if token != settings.auth_token:
            return JSONResponse({"detail": "Invalid X-Workmode-Token"}, status_code=401)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    is_media_preview = (
        (
            request.url.path.startswith("/api/work/projects/")
            and request.url.path.endswith("/fs/media")
        )
        or (
            request.url.path.startswith("/api/work/projects/")
            and "/literature/papers/" in request.url.path
            and request.url.path.endswith("/pdf")
        )
    )
    if is_media_preview:
        response.headers["Content-Security-Policy"] = (
            "frame-ancestors 'self' tauri://localhost http://tauri.localhost "
            "https://tauri.localhost http://127.0.0.1:* http://localhost:*"
        )
    else:
        response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.on_event("startup")
def startup() -> None:
    ensure_data_dirs()
    report = repair_stale_tool_runs(
        sessions_dir(),
        data_dir() / "backups" / "history-repair",
    )
    if report.inserted_results or report.failed_files:
        logger.info(
            "historical tool repair: scanned=%s repaired=%s inserted=%s failed=%s backup=%s",
            report.scanned_files,
            report.repaired_files,
            report.inserted_results,
            report.failed_files,
            report.backup_dir,
        )


app.include_router(router)
app.include_router(literature_router)


FRONTEND_DIST = settings.static_dir
if FRONTEND_DIST.exists() and (FRONTEND_DIST / "index.html").exists():
    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        target = FRONTEND_DIST / path
        if path and target.exists() and target.is_file():
            return FileResponse(target)
        nested_index = target / "index.html"
        if path and target.is_dir() and nested_index.exists():
            return FileResponse(nested_index)
        return FileResponse(FRONTEND_DIST / "index.html")
