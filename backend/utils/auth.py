"""
Auth utilities — JWT creation/verification, password hashing.
Model-agnostic — no AI-specific logic here.
"""
import jwt
import bcrypt
from datetime import datetime, timedelta
from typing import Optional
from utils.config import get_settings
from utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()

JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 8


def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    """Verify plaintext password against bcrypt hash."""
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except Exception:
        return False


def create_token(user: dict) -> str:
    """
    Create JWT containing user identity and their Smartsheet token.
    Payload: user_id, email, name, is_admin, smartsheet_token
    Expires in JWT_EXPIRY_HOURS hours.
    """
    payload = {
        "user_id": str(user["id"]),
        "email": user["email"],
        "name": user["name"],
        "is_admin": user.get("is_admin", False),
        "smartsheet_token": user["smartsheet_token"],
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRY_HOURS),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    """
    Decode and verify JWT. Returns payload dict or None if invalid/expired.
    """
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        logger.warning("JWT expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning("JWT invalid", error=str(e))
        return None


def extract_token_from_header(authorization: str) -> Optional[str]:
    """Extract Bearer token from Authorization header."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    return authorization[7:]
