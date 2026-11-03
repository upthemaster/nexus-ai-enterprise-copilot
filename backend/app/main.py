"""
Main FastAPI application entry point for NexusAI Enterprise Copilot.

Why: Centralizes application lifecycle, middleware registration, API router
mounting, and global exception sanitization. Enforcing global exception handlers
ensures that internal stack traces, system paths, and raw file contents are never
leaked to external API consumers.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError

from app.core.config import settings
from app.core.errors import NexusBaseException
from app.api.v1.router import api_v1_router
from app.db.session import init_db

# Configure root logger
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("nexusai.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan context manager.
    
    Why: Handles startup and shutdown hooks cleanly, ensuring storage directories
    are prepared and resources released gracefully.
    """
    logger.info("Starting NexusAI API service [%s mode]", settings.APP_ENV)
    # Ensure upload directory exists at boot
    _ = settings.upload_path
    init_db()
    yield
    logger.info("Shutting down NexusAI API service")


def create_app() -> FastAPI:
    """
    FastAPI application factory.
    
    Why: The application factory pattern simplifies configuring isolated instances
    for test environments without shared mutable global state.
    """
    application = FastAPI(
        title=settings.APP_NAME,
        version="0.1.0",
        description="NexusAI Enterprise Knowledge & Workflow Copilot API",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan
    )

    # Cross-Origin Resource Sharing (CORS) Middleware
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount API v1 router
    application.include_router(api_v1_router, prefix="/api/v1")

    @application.get("/", tags=["Root"])
    async def root_index():
        """
        Public root endpoint confirming backend status and linking to documentation.
        """
        return {
            "status": "healthy",
            "service": "NexusAI Enterprise Knowledge & Workflow Copilot API",
            "version": "0.1.0",
            "documentation": "/docs",
            "health_check": "/api/v1/health"
        }

    # -------------------------------------------------------------------------
    # Centralized Exception Handlers (Safe Error Sanitization)
    # -------------------------------------------------------------------------

    @application.exception_handler(NexusBaseException)
    async def handle_nexus_domain_exception(request: Request, exc: NexusBaseException) -> JSONResponse:
        """
        Handle all known NexusAI domain exceptions.
        
        Why: Translates domain exceptions into structured JSON responses with appropriate
        HTTP status codes, hiding any internal system details.
        """
        logger.warning(
            "Domain exception caught: type=%s, status=%d, message=%s, path=%s",
            exc.error_type,
            exc.status_code,
            exc.message,
            request.url.path
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.message,
                "error_type": exc.error_type
            }
        )

    @application.exception_handler(RequestValidationError)
    async def handle_request_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        """
        Handle FastAPI/Pydantic request payload validation errors.
        
        Why: Standardizes validation failure messages without leaking Python class paths.
        """
        logger.warning("Request validation failed for path: %s", request.url.path)
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "Invalid request parameters or payload format.",
                "error_type": "ValidationError",
                "details": [
                    {"loc": err.get("loc", []), "msg": err.get("msg", "Invalid value")}
                    for err in exc.errors()
                ]
            }
        )

    @application.exception_handler(Exception)
    async def handle_unexpected_exception(request: Request, exc: Exception) -> JSONResponse:
        """
        Fallback exception handler for unhandled server errors.
        
        Why: Strictly protects against information disclosure by returning a generic
        internal error message rather than a raw Python stack trace or filesystem path.
        """
        logger.error(
            "Unhandled server exception on path %s: %s",
            request.url.path,
            exc.__class__.__name__,
            exc_info=True
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "An internal server error occurred.",
                "error_type": "InternalServerError"
            }
        )

    return application


# Default application instance for ASGI servers (uvicorn backend.app.main:app)
app = create_app()

