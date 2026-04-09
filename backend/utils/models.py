from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    session_id: Optional[str] = None
    voice_input: bool = False  # Flag if message came from voice


class ToolCallInfo(BaseModel):
    tool: str
    input: dict
    display: str


class ChartData(BaseModel):
    chart_type: str = "bar"  # bar | line | pie
    chart_title: str = ""
    labels: List[str] = []
    values: List[float] = []


class ChatResponse(BaseModel):
    session_id: str
    response: str
    chart_data: Optional[ChartData] = None
    tool_calls: List[ToolCallInfo] = []
    needs_confirmation: bool = False
    followups: List[str] = []
    dashboard_data: Optional[dict] = None
    input_form: Optional[dict] = None  # Inline form for user input
    infographics: List[dict] = []  # Inline infographic blocks parsed from INFOGRAPHIC::
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    processing_time_ms: Optional[int] = None


class HealthResponse(BaseModel):
    status: str
    smartsheet_connected: bool
    anthropic_configured: bool
    active_sessions: int
    version: str = "1.0.0"


class SessionInfo(BaseModel):
    session_id: str
    message_count: int
    created_at: Optional[str] = None


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    code: Optional[str] = None


# ── AUTH MODELS ──────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=200)
    password: str = Field(..., min_length=1, max_length=200)


class TokenResponse(BaseModel):
    token: str
    user_id: str
    email: str
    name: str
    is_admin: bool = False


class UserPublic(BaseModel):
    id: str
    email: str
    name: str
    is_active: bool
    is_admin: bool
    created_at: Optional[str] = None
    last_login: Optional[str] = None


class CreateUserRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=200)
    password: str = Field(..., min_length=8, max_length=200)
    name: str = Field(..., min_length=1, max_length=100)
    smartsheet_token: str = Field(..., min_length=10)
    is_admin: bool = False


class UpdateUserRequest(BaseModel):
    name: Optional[str] = None
    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None
    smartsheet_token: Optional[str] = None