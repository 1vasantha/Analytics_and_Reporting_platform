from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.middleware import RateLimitMiddleware
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import AppException
from app.core.logging import configure_logging, get_logger
from app.db.redis import close_redis, get_redis
from app.db.session import engine
from app.schemas.common import ErrorResponse, HealthCheck
from app.websockets.manager import manager as ws_manager
from app.websockets.routes import router as ws_router

# Lifespan handler: configures logging and starts WS listener at boot.
@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    log = get_logger(__name__)
    log.info(
        "app.starting env=%s version=%s",
        settings.ENVIRONMENT,
        settings.VERSION,
    )

    await ws_manager.start_redis_listener()

    yield

    log.info("app.shutting_down")
    await ws_manager.stop_redis_listener()
    await close_redis()
    await engine.dispose()

# Application factory — keeps configuration declarative and testable.
def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
        lifespan=lifespan,
    )

    # Cors
    app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://analytics-and-reporting-platform.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
    
    # Rate limiting
    app.add_middleware(RateLimitMiddleware)

    # Routers
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)
    app.include_router(ws_router)

    # Exception handlers
    @app.exception_handler(AppException)
    async def handle_app_exception(_: Request, exc: AppException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                error_code=exc.error_code,
                message=exc.message,
                details=exc.details or None,
            ).model_dump(),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=ErrorResponse(
                error_code="validation_error",
                message="Request validation failed",
                details={"errors": exc.errors()},
            ).model_dump(),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(_: Request, exc: Exception) -> JSONResponse:
        log = get_logger(__name__)
        log.exception("unhandled_exception")
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error_code="internal_error",
                message="An unexpected error occurred",
            ).model_dump(),
        )

    # Health check
    @app.get("/health", response_model=HealthCheck, tags=["meta"])
    async def health() -> HealthCheck:
        db_ok = False
        redis_ok = False

        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
                db_ok = True
        except Exception:
            pass

        try:
            await get_redis().ping()
            redis_ok = True
        except Exception:
            pass

        return HealthCheck(
            status="healthy" if db_ok and redis_ok else "degraded",
            version=settings.VERSION,
            database=db_ok,
            redis=redis_ok,
        )

    # Root api
    @app.get("/", tags=["meta"])
    def root() -> dict[str, str]:
        return {
            "name": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "docs": "/docs",
        }

    return app

app = create_app()
