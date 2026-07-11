from pathlib import Path
import asyncio
from contextlib import suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.errors import AppError, app_error_handler, unhandled_error_handler
from app.core.logging import request_context_middleware
from app.jobs.content_pipeline import content_pipeline_scheduler_loop
from app.services.content_pipeline.ai.article_generator import recover_interrupted_generation_jobs

settings = get_settings()

app = FastAPI(
    title="VoltScope API",
    version="0.1.0",
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None if settings.is_production else "/redoc",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[str(settings.frontend_url)],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.middleware("http")(request_context_middleware)
app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(Exception, unhandled_error_handler)
app.include_router(api_router)

upload_dir = Path(settings.upload_dir)
upload_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=upload_dir), name="uploads")


@app.on_event("startup")
async def start_ai_scheduler() -> None:
    if settings.app_env == "test":
        return
    await recover_interrupted_generation_jobs()
    if settings.content_pipeline_daily_enabled:
        app.state.content_pipeline_scheduler_task = asyncio.create_task(content_pipeline_scheduler_loop())


@app.on_event("shutdown")
async def stop_ai_scheduler() -> None:
    for task_name in ("content_pipeline_scheduler_task",):
        task = getattr(app.state, task_name, None)
        if task is not None:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task


@app.get("/")
async def root() -> dict[str, str]:
    return {"service": "voltscope-api", "status": "ok"}
