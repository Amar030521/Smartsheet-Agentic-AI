from fastapi import APIRouter
from utils.models import HealthResponse
from utils.session_store import get_session_store
from utils.config import get_settings
from utils.logger import get_logger
import smartsheet

logger = get_logger(__name__)
settings = get_settings()
router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health():
    """Health check — verifies Smartsheet + Anthropic connectivity."""
    store = get_session_store()
    active_sessions = await store.count()

    # Test Smartsheet connectivity
    ss_ok = False
    try:
        client = smartsheet.Smartsheet(settings.smartsheet_api_token)
        client.errors_as_exceptions(True)
        client.Users.get_current_user()
        ss_ok = True
    except Exception as e:
        logger.warning("Smartsheet health check failed", error=str(e))

    return HealthResponse(
        status="ok" if ss_ok else "degraded",
        smartsheet_connected=ss_ok,
        anthropic_configured=bool(settings.anthropic_api_key),
        active_sessions=active_sessions
    )


@router.get("/")
async def root():
    return {
        "service": "Smartsheet AI Agent",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }
