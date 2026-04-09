"""
Auth routes — login, logout, admin user management.
All endpoints except /login require valid JWT.
"""
from fastapi import APIRouter, HTTPException, Header, Request
from typing import Optional
from utils.models import (
    LoginRequest, TokenResponse, CreateUserRequest,
    UpdateUserRequest, UserPublic
)
from utils.auth import (
    verify_password, create_token, decode_token,
    extract_token_from_header, hash_password
)
from utils.database import (
    get_user_by_email, create_user, get_all_users,
    update_user, update_password, delete_user, record_login
)
from utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def require_auth(authorization: str) -> dict:
    """Extract and validate JWT from Authorization header. Raises 401 if invalid."""
    token = extract_token_from_header(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="Authorization header missing or invalid")
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token expired or invalid — please log in again")
    return payload


def require_admin(authorization: str) -> dict:
    """Require valid JWT with is_admin=True."""
    payload = require_auth(authorization)
    if not payload.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    return payload


# ── PUBLIC ENDPOINTS ─────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, request: Request):
    """Authenticate user with email + password. Returns JWT on success."""
    user = get_user_by_email(req.email)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.get("is_active"):
        raise HTTPException(status_code=403, detail="Account deactivated — contact your administrator")
    if not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Record login
    ip = request.client.host if request.client else None
    record_login(user["id"], ip)

    token = create_token(user)
    logger.info("User logged in", email=user["email"])
    return TokenResponse(
        token=token,
        user_id=str(user["id"]),
        email=user["email"],
        name=user["name"],
        is_admin=user.get("is_admin", False)
    )


@router.post("/verify")
async def verify_token(authorization: str = Header(None)):
    """Verify JWT is valid and not expired. Used by frontend on app load."""
    payload = require_auth(authorization)
    return {
        "valid": True,
        "email": payload["email"],
        "name": payload["name"],
        "is_admin": payload.get("is_admin", False)
    }


@router.post("/logout")
async def logout(authorization: str = Header(None)):
    """Logout — client deletes JWT. Server-side is stateless."""
    require_auth(authorization)
    return {"message": "Logged out successfully"}


# ── ADMIN ENDPOINTS ──────────────────────────────────────────────

@router.get("/users")
async def list_users(authorization: str = Header(None)):
    """List all users. Admin only."""
    require_admin(authorization)
    users = get_all_users()
    return {"users": users, "total": len(users)}


@router.post("/users")
async def create_user_endpoint(req: CreateUserRequest, authorization: str = Header(None)):
    """Create a new user. Admin only."""
    require_admin(authorization)

    # Check email not already taken
    existing = get_user_by_email(req.email)
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    password_hash = hash_password(req.password)
    user = create_user(
        email=req.email,
        password_hash=password_hash,
        name=req.name,
        smartsheet_token=req.smartsheet_token,
        is_admin=req.is_admin
    )
    if not user:
        raise HTTPException(status_code=500, detail="Failed to create user")

    logger.info("User created", email=req.email, by=authorization[:20])
    return {"message": "User created", "user_id": str(user["id"]), "email": user["email"]}


@router.patch("/users/{user_id}")
async def update_user_endpoint(user_id: str, req: UpdateUserRequest,
                                authorization: str = Header(None)):
    """Update user name, active status, admin status, or Smartsheet token. Admin only."""
    require_admin(authorization)
    updates = {}
    if req.name is not None: updates["name"] = req.name
    if req.is_active is not None: updates["is_active"] = req.is_active
    if req.is_admin is not None: updates["is_admin"] = req.is_admin
    if req.smartsheet_token is not None: updates["smartsheet_token"] = req.smartsheet_token

    result = update_user(user_id, updates)
    if not result:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": "User updated", "user_id": user_id}


@router.post("/users/{user_id}/reset-password")
async def reset_password(user_id: str, req: dict, authorization: str = Header(None)):
    """Reset user password. Admin only."""
    require_admin(authorization)
    new_password = req.get("password", "")
    if len(new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    new_hash = hash_password(new_password)
    success = update_password(user_id, new_hash)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update password")
    return {"message": "Password reset successfully"}


@router.delete("/users/{user_id}")
async def deactivate_user(user_id: str, authorization: str = Header(None)):
    """Deactivate user (soft delete). Admin only."""
    require_admin(authorization)
    success = delete_user(user_id)
    if not success:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": "User deactivated"}
