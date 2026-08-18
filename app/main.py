from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from app.api.routes import plan, generate, status as status_route, artifacts
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.services.job_manager import JobManager


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    app.state.settings = settings
    app.state.job_manager = JobManager(settings)

    yield

    await app.state.job_manager.shutdown()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title = settings.app_name, lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(plan.router, prefix="/api")
    app.include_router(generate.router, prefix="/api")
    app.include_router(status_route.router, prefix="/api")
    app.include_router(artifacts.router, prefix="/api")

    @app.get("/health", tags=["meta"])
    async def health():
        return {"status": "ok"}

    return app

app = create_app()

