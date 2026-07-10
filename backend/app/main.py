from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import APP_NAME, APP_VERSION, settings
from .routes import router
from .storage import ensure_data_dirs


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
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.on_event("startup")
def startup() -> None:
    ensure_data_dirs()


app.include_router(router)


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
        return FileResponse(FRONTEND_DIST / "index.html")
