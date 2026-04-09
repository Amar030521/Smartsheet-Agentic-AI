"""
Supabase database client — user CRUD operations.
Uses supabase-py client library.
All Smartsheet tokens stored encrypted at rest by Supabase.
"""
from typing import Optional
from utils.config import get_settings
from utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()

_supabase = None


def get_db():
    """Return Supabase client singleton."""
    global _supabase
    if _supabase is None:
        from supabase import create_client
        _supabase = create_client(settings.supabase_url, settings.supabase_key)
    return _supabase


# ── USER OPERATIONS ──────────────────────────────────────────────

def get_user_by_email(email: str) -> Optional[dict]:
    """Fetch user by email. Returns user dict or None."""
    try:
        result = get_db().table("users").select("*").eq("email", email.lower()).single().execute()
        return result.data
    except Exception as e:
        logger.info("User not found", email=email, error=str(e))
        return None


def get_user_by_id(user_id: str) -> Optional[dict]:
    """Fetch user by UUID."""
    try:
        result = get_db().table("users").select("*").eq("id", user_id).single().execute()
        return result.data
    except Exception:
        return None


def get_all_users() -> list:
    """Return all users (admin only). Excludes password_hash and smartsheet_token."""
    try:
        result = get_db().table("users")\
            .select("id, email, name, is_active, is_admin, created_at, last_login")\
            .order("created_at", desc=True)\
            .execute()
        return result.data or []
    except Exception as e:
        logger.error("Failed to fetch users", error=str(e))
        return []


def create_user(email: str, password_hash: str, name: str,
                smartsheet_token: str, is_admin: bool = False) -> Optional[dict]:
    """Create a new user. Returns created user or None."""
    try:
        result = get_db().table("users").insert({
            "email": email.lower().strip(),
            "password_hash": password_hash,
            "name": name.strip(),
            "smartsheet_token": smartsheet_token.strip(),
            "is_active": True,
            "is_admin": is_admin,
        }).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error("Failed to create user", email=email, error=str(e))
        return None


def update_user(user_id: str, updates: dict) -> Optional[dict]:
    """Update user fields. Safe — only allows whitelisted fields."""
    allowed = {"name", "is_active", "is_admin", "smartsheet_token", "last_login"}
    safe_updates = {k: v for k, v in updates.items() if k in allowed}
    if not safe_updates:
        return None
    try:
        result = get_db().table("users")\
            .update(safe_updates)\
            .eq("id", user_id)\
            .execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error("Failed to update user", user_id=user_id, error=str(e))
        return None


def update_password(user_id: str, new_hash: str) -> bool:
    """Update user password hash."""
    try:
        get_db().table("users")\
            .update({"password_hash": new_hash})\
            .eq("id", user_id)\
            .execute()
        return True
    except Exception as e:
        logger.error("Failed to update password", error=str(e))
        return False


def delete_user(user_id: str) -> bool:
    """Soft delete — sets is_active=False rather than hard delete."""
    result = update_user(user_id, {"is_active": False})
    return result is not None


def record_login(user_id: str, ip: str = None):
    """Update last_login timestamp."""
    from datetime import datetime
    update_user(user_id, {"last_login": datetime.utcnow().isoformat()})
