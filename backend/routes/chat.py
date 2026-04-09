"""
Chat API Routes
"""
import uuid
import time
from fastapi import APIRouter, HTTPException, Request, Header
from typing import Optional
from utils.models import ChatRequest, ChatResponse, ToolCallInfo, ChartData
from utils.auth import decode_token, extract_token_from_header
from utils.session_store import get_session_store
from utils.agent import run_agent
from utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, request: Request, authorization: Optional[str] = Header(None)):
    """
    Main chat endpoint.
    - Creates session if session_id not provided
    - Runs agent with full conversation history
    - Returns response + optional chart data + tool calls
    """
    start_time = time.time()
    store = get_session_store()

    # Session management
    session_id = req.session_id or str(uuid.uuid4())
    messages = await store.get(session_id)

    logger.info(
        "Chat request",
        session_id=session_id,
        message_preview=req.message[:80],
        history_length=len(messages),
        voice_input=req.voice_input
    )

    try:
        # Extract per-user Smartsheet token from JWT if auth enabled
        smartsheet_token = None
        if authorization:
            token = extract_token_from_header(authorization)
            if token:
                payload = decode_token(token)
                if payload:
                    smartsheet_token = payload.get("smartsheet_token")

        result = await run_agent(messages, req.message, smartsheet_token=smartsheet_token)

        # Persist updated conversation history
        await store.set(session_id, result["messages"])

        processing_ms = int((time.time() - start_time) * 1000)
        logger.info(
            "Chat response",
            session_id=session_id,
            tool_calls=len(result["tool_calls"]),
            has_chart=result["chart_data"] is not None,
            processing_ms=processing_ms
        )

        # Build response
        chart = None
        if result.get("chart_data"):
            cd = result["chart_data"]
            chart = ChartData(
                chart_type=cd.get("chart_type", "bar"),
                chart_title=cd.get("chart_title", ""),
                labels=[str(l) for l in cd.get("labels", [])],
                values=[float(v) for v in cd.get("values", []) if v is not None]
            )

        tool_calls = [
            ToolCallInfo(tool=t["tool"], input=t["input"], display=t["display"])
            for t in result.get("tool_calls", [])
        ]

        return ChatResponse(
            session_id=session_id,
            response=result["response"],
            chart_data=chart,
            tool_calls=tool_calls,
            needs_confirmation=result.get("needs_confirmation", False),
            followups=result.get("followups", []),
            dashboard_data=result.get("dashboard_data"),
            input_form=result.get("input_form"),
            infographics=result.get("infographics", []),
            processing_time_ms=processing_ms
        )

    except Exception as e:
        logger.error("Chat error", session_id=session_id, error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/session/{session_id}")
async def clear_session(session_id: str):
    """Clear conversation history for a session."""
    store = get_session_store()
    await store.delete(session_id)
    logger.info("Session cleared", session_id=session_id)
    return {"message": "Session cleared", "session_id": session_id}


@router.get("/session/{session_id}/history")
async def get_history(session_id: str):
    """Get message count for a session (not full content for security)."""
    store = get_session_store()
    messages = await store.get(session_id)
    return {
        "session_id": session_id,
        "message_count": len(messages),
        "exists": len(messages) > 0
    }


@router.get("/sidebar")
async def get_sidebar_data(authorization: Optional[str] = Header(None)):
    """
    Fast sidebar load: workspaces list + recent sheets + dashboards.
    Uses the logged-in user's Smartsheet token if provided.
    """
    from utils.smartsheet_client import get_client as get_smartsheet_client, get_client_for_token
    try:
        # Use per-user token from JWT if available
        ss_client = None
        if authorization:
            token = extract_token_from_header(authorization)
            if token:
                payload = decode_token(token)
                if payload and payload.get("smartsheet_token"):
                    ss_client = get_client_for_token(payload["smartsheet_token"])
        if not ss_client:
            ss_client = get_smartsheet_client()
        client = ss_client

        # Fast: just workspace names and IDs (no folder loading)
        ws_list = client.Workspaces.list_workspaces(include_all=True)
        workspaces = [
            {"id": str(ws.id), "name": ws.name, "type": "workspace", "folders": [], "sheets": [], "dashboards": [], "loaded": False}
            for ws in (ws_list.data or [])
        ]

        # Recent sheets
        try:
            sheets_result = client.Sheets.list_sheets(include_all=True)
            all_sheets = sorted(sheets_result.data or [], key=lambda s: str(getattr(s, 'modified_at', '') or ''), reverse=True)
            recent_sheets = [{"id": str(s.id), "name": s.name} for s in all_sheets[:8]]
        except Exception:
            recent_sheets = []

        # Dashboards
        try:
            dash_result = client.Sights.list_sights(include_all=True)
            dashboards = [{"id": str(s.id), "name": s.name} for s in (dash_result.data or [])]
        except Exception:
            dashboards = []

        return {"workspaces": workspaces, "recent_sheets": recent_sheets, "dashboards": dashboards}
    except Exception as e:
        return {"workspaces": [], "recent_sheets": [], "dashboards": [], "error": str(e)}


@router.get("/sidebar/workspace/{workspace_id}")
async def get_workspace_tree(workspace_id: str, authorization: Optional[str] = Header(None)):
    """
    Lazy-load folder/sheet tree for a specific workspace when user expands it.
    Uses the logged-in user's Smartsheet token if provided.
    """
    from utils.smartsheet_client import get_client as get_smartsheet_client, get_client_for_token
    try:
        ss_client = None
        if authorization:
            token = extract_token_from_header(authorization)
            if token:
                payload = decode_token(token)
                if payload and payload.get("smartsheet_token"):
                    ss_client = get_client_for_token(payload["smartsheet_token"])
        if not ss_client:
            ss_client = get_smartsheet_client()
        client = ss_client

        def build_folder_tree(folder):
            result = {
                "id": str(folder.id),
                "name": folder.name,
                "type": "folder",
                "sheets": [{"id": str(s.id), "name": s.name, "type": "sheet"} for s in (folder.sheets or [])],
                "reports": [{"id": str(r.id), "name": r.name, "type": "report"} for r in (folder.reports or [])],
                "dashboards": [{"id": str(s.id), "name": s.name, "type": "dashboard"} for s in (folder.sights or [])],
                "subfolders": []
            }
            for sub in (folder.folders or []):
                result["subfolders"].append(build_folder_tree(sub))
            return result

        full_ws = client.Workspaces.get_workspace(int(workspace_id), load_all=True)
        return {
            "id": workspace_id,
            "name": full_ws.name,
            "type": "workspace",
            "loaded": True,
            "folders": [build_folder_tree(f) for f in (full_ws.folders or [])],
            "sheets": [{"id": str(s.id), "name": s.name, "type": "sheet"} for s in (full_ws.sheets or [])],
            "dashboards": [{"id": str(s.id), "name": s.name, "type": "dashboard"} for s in (full_ws.sights or [])],
        }
    except Exception as e:
        return {"error": str(e), "workspace_id": workspace_id}