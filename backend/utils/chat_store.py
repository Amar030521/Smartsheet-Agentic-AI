"""
Persistent chat history in Supabase.
Each user has sessions, each session has messages.
"""
from typing import Optional, List
from utils.logger import get_logger
from datetime import datetime

logger = get_logger(__name__)


def get_db():
    from utils.database import get_db as _get_db
    return _get_db()


# ── SESSIONS ─────────────────────────────────────────────────────

def create_session(user_id: str, title: str = "New Chat") -> Optional[dict]:
    try:
        result = get_db().table("chat_sessions").insert({
            "user_id": user_id,
            "title": title,
            "updated_at": datetime.utcnow().isoformat()
        }).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error("Failed to create session", error=str(e))
        return None


def update_session_title(session_id: str, title: str):
    try:
        get_db().table("chat_sessions")\
            .update({"title": title, "updated_at": datetime.utcnow().isoformat()})\
            .eq("id", session_id).execute()
    except Exception as e:
        logger.error("Failed to update session title", error=str(e))


def create_session_if_not_exists(session_id: str, user_id: str, title: str):
    """Create session with given ID if it doesn't exist yet."""
    try:
        existing = get_db().table("chat_sessions")            .select("id").eq("id", session_id).execute()
        if not existing.data:
            get_db().table("chat_sessions").insert({
                "id": session_id,
                "user_id": user_id,
                "title": title,
                "updated_at": datetime.utcnow().isoformat()
            }).execute()
    except Exception as e:
        logger.error("Failed to create session", error=str(e))


def touch_session(session_id: str):
    """Update updated_at timestamp."""
    try:
        get_db().table("chat_sessions")\
            .update({"updated_at": datetime.utcnow().isoformat()})\
            .eq("id", session_id).execute()
    except Exception:
        pass


def get_user_sessions(user_id: str, limit: int = 50) -> list:
    try:
        result = get_db().table("chat_sessions")\
            .select("id, title, created_at, updated_at")\
            .eq("user_id", user_id)\
            .order("updated_at", desc=True)\
            .limit(limit)\
            .execute()
        return result.data or []
    except Exception as e:
        logger.error("Failed to get sessions", error=str(e))
        return []


def delete_session(session_id: str, user_id: str) -> bool:
    try:
        # Delete messages first
        get_db().table("chat_messages")\
            .delete().eq("session_id", session_id).execute()
        # Delete session
        get_db().table("chat_sessions")\
            .delete().eq("id", session_id).eq("user_id", user_id).execute()
        return True
    except Exception as e:
        logger.error("Failed to delete session", error=str(e))
        return False


# ── MESSAGES ─────────────────────────────────────────────────────

def save_message(session_id: str, role: str, content: str,
                 tool_calls: list = None, dashboard_data: dict = None,
                 infographics: list = None, followups: list = None,
                 chart_data: dict = None) -> Optional[dict]:
    import json
    try:
        result = get_db().table("chat_messages").insert({
            "session_id": session_id,
            "role": role,
            "content": content,
            "tool_calls": json.dumps(tool_calls or []),
            "dashboard_data": json.dumps(dashboard_data) if dashboard_data else None,
            "infographics": json.dumps(infographics or []),
            "followups": json.dumps(followups or []),
            "chart_data": json.dumps(chart_data) if chart_data else None,
        }).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error("Failed to save message", error=str(e))
        return None


def get_session_messages(session_id: str) -> list:
    import json
    try:
        result = get_db().table("chat_messages")\
            .select("*")\
            .eq("session_id", session_id)\
            .order("created_at", desc=False)\
            .execute()
        messages = []
        for m in (result.data or []):
            try:
                def _p(v):
                    if v is None: return None
                    if isinstance(v, (dict, list)): return v
                    try: return json.loads(v)
                    except: return v
                messages.append({
                    "id": m["id"],
                    "role": m["role"],
                    "content": m["content"],
                    "tool_calls": _p(m.get("tool_calls")) or [],
                    "dashboard_data": _p(m.get("dashboard_data")),
                    "infographics": _p(m.get("infographics")) or [],
                    "followups": _p(m.get("followups")) or [],
                    "chart_data": _p(m.get("chart_data")),
                    "created_at": m.get("created_at"),
                })
            except Exception:
                continue
        return messages
    except Exception as e:
        logger.error("Failed to get messages", error=str(e))
        return []


def get_session_history_for_agent(session_id: str) -> list:
    """Get messages in Claude API format for the agent loop."""
    import json
    try:
        result = get_db().table("chat_messages")\
            .select("role, content")\
            .eq("session_id", session_id)\
            .order("created_at", desc=False)\
            .execute()
        return [{"role": m["role"], "content": m["content"]}
                for m in (result.data or [])]
    except Exception as e:
        logger.error("Failed to get agent history", error=str(e))
        return []