"""
Smartsheet AI Agent — Production FastAPI App
─────────────────────────────────────────────
Endpoints:
  POST /api/v1/chat          → Main chat endpoint
  DELETE /api/v1/session/{id} → Clear session
  GET  /api/v1/session/{id}/history → Session info
  GET  /health               → Health check
  GET  /docs                 → Swagger UI
"""
import os
import sys
from pathlib import Path

# Always run from the backend directory so relative imports and .env resolve correctly
_BACKEND_DIR = Path(__file__).resolve().parent
os.chdir(_BACKEND_DIR)
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))
if str(_BACKEND_DIR / "mcp") not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR / "mcp"))

import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from utils.config import get_settings
from utils.logger import setup_logging, get_logger
from utils.session_store import get_session_store
from routes.chat import router as chat_router
from routes.health import router as health_router
from routes.auth import router as auth_router

setup_logging()
logger = get_logger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info("Starting Smartsheet AI Agent", env=settings.app_env)

    # Initialize session store
    store = get_session_store()
    await store.init()

    logger.info(
        "Agent ready",
        claude_model=settings.claude_model,
        redis_enabled=settings.redis_enabled
    )

    yield

    logger.info("Shutting down Smartsheet AI Agent")


app = FastAPI(
    title="Smartsheet AI Agent",
    description="Production AI agent for Smartsheet — query, analyze, and act on your workspace data via natural language.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# ─── MIDDLEWARE ────────────────────────────────────────────────

app.add_middleware(GZipMiddleware, minimum_size=1000)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-Processing-Time"],
)


@app.middleware("http")
async def request_logger(request: Request, call_next):
    """Log all requests with timing."""
    request_id = str(uuid.uuid4())[:8]
    start = time.time()

    response: Response = await call_next(request)

    duration_ms = int((time.time() - start) * 1000)
    logger.info(
        "HTTP",
        request_id=request_id,
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        duration_ms=duration_ms
    )
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Processing-Time"] = str(duration_ms)
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception", path=request.url.path, error=str(exc), exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)}
    )

# ─── ROUTES ────────────────────────────────────────────────────

app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(health_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_env != "production",
        log_level=settings.log_level.lower(),
        workers=1,
        timeout_keep_alive=300,
        timeout_graceful_shutdown=300
    )