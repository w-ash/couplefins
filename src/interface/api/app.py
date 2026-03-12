from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from src.application.runner import execute_use_case
from src.application.use_cases.seed_category_groups import seed_category_groups
from src.config.constants import AppConfig
from src.config.logging import setup_logging
from src.config.settings import get_settings
from src.infrastructure.persistence.database.db_connection import (
    dispose_engine,
    init_db,
)
from src.interface.api.middleware import register_exception_handlers
from src.interface.api.routes.category_groups import router as category_groups_router
from src.interface.api.routes.dashboard import router as dashboard_router
from src.interface.api.routes.health import router as health_router
from src.interface.api.routes.persons import router as persons_router
from src.interface.api.routes.reconciliation import router as reconciliation_router
from src.interface.api.routes.uploads import router as uploads_router


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    setup_logging()
    await init_db()
    await execute_use_case(seed_category_groups)
    logger.info("Application started")
    yield
    logger.info("Application shutting down")
    await dispose_engine()


def create_app() -> FastAPI:
    app = FastAPI(
        title=AppConfig.TITLE,
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )

    settings = get_settings()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)
    app.include_router(health_router, prefix=AppConfig.API_V1_PREFIX)
    app.include_router(persons_router, prefix=AppConfig.API_V1_PREFIX)
    app.include_router(uploads_router, prefix=AppConfig.API_V1_PREFIX)
    app.include_router(category_groups_router, prefix=AppConfig.API_V1_PREFIX)
    app.include_router(reconciliation_router, prefix=AppConfig.API_V1_PREFIX)
    app.include_router(dashboard_router, prefix=AppConfig.API_V1_PREFIX)

    return app


app = create_app()
