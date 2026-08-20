from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
import time
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from .core.logs import log_manager
from .db.database import Database
from .handler.exceptions import register_exception_handlers
from .router.api import api
from .router.web import web


def create_app(db_path: str = ":memory:") -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        if hasattr(app.state, "db") and app.state.db:
            app.state.db.close()

    app = FastAPI(lifespan=lifespan)
    app.state.db = Database(db_path)
    register_exception_handlers(app)

    @app.middleware("http")
    async def audit_log_middleware(request: Request, call_next):
        start_time = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        path = request.url.path
        if path.startswith("/api"):
            parts = [p for p in path.split("/") if p]
            # /api/projects or /api/{slug}/...
            project_slug = None
            if len(parts) >= 2:
                if parts[1] == "projects" and len(parts) >= 3:
                    project_slug = parts[2]
                elif parts[1] != "projects":
                    project_slug = parts[1]

            log_event = {
                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                "method": request.method,
                "path": path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
                "project_slug": project_slug,
            }
            if project_slug:
                await log_manager.broadcast(project_slug, log_event)
            await log_manager.broadcast("__all__", log_event)

        return response

    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

    app.include_router(web)
    app.include_router(api)
    return app
