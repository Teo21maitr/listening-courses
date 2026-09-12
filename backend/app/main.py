import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.jobs import router as jobs_router
from app.config import Settings, get_settings
from app.errors import AppError
from app.jobs.manager import JobManager
from app.services.tts_service import TTSEngine

logger = logging.getLogger(__name__)

PURGE_INTERVAL_SECONDS = 600


def create_app(settings: Settings | None = None, engine: TTSEngine | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        manager = JobManager(settings, engine)
        removed = manager.cleanup_orphans()
        if removed:
            logger.info("Removed %d orphan job folder(s)", removed)
        app.state.job_manager = manager
        purge_task = asyncio.create_task(_purge_periodically(manager, settings))
        try:
            yield
        finally:
            purge_task.cancel()
            manager.shutdown()

    app = FastAPI(title="PDF to Audio", version="1.0.0", lifespan=lifespan)
    app.dependency_overrides[get_settings] = lambda: settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_exception_handler(AppError, _handle_app_error)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, _handle_unexpected_error)
    app.include_router(jobs_router)

    dist_dir = settings.frontend_dist_dir
    if dist_dir and dist_dir.is_dir():
        app.mount("/", StaticFiles(directory=dist_dir, html=True), name="frontend")
        logger.info("Serving frontend from %s", dist_dir)
    return app


async def _purge_periodically(manager: JobManager, settings: Settings) -> None:
    while True:
        await asyncio.sleep(PURGE_INTERVAL_SECONDS)
        removed = manager.cleanup_expired(timedelta(hours=settings.job_ttl_hours))
        if removed:
            logger.info("Purged %d expired job(s)", removed)


def _handle_app_error(request: Request, error: AppError) -> JSONResponse:
    return JSONResponse(status_code=error.status_code, content={"detail": error.message})


def _handle_unexpected_error(request: Request, error: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error."})


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
app = create_app()
