"""
Session store for conversation history.
Uses Redis if available, falls back to in-memory dict.
TTL: 2 hours per session.
"""
import json
from typing import Optional
from utils.config import get_settings
from utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()

SESSION_TTL = 7200  # 2 hours

# In-memory fallback
_memory_store: dict = {}


class SessionStore:
    def __init__(self):
        self._redis = None
        self._use_redis = settings.redis_enabled

    async def init(self):
        if self._use_redis:
            try:
                import aioredis
                self._redis = await aioredis.from_url(
                    settings.redis_url,
                    encoding="utf-8",
                    decode_responses=True
                )
                await self._redis.ping()
                logger.info("Redis session store connected")
            except Exception as e:
                logger.warning("Redis unavailable, using in-memory store", error=str(e))
                self._use_redis = False

    async def get(self, session_id: str) -> list:
        try:
            if self._use_redis and self._redis:
                data = await self._redis.get(f"session:{session_id}")
                return json.loads(data) if data else []
            return _memory_store.get(session_id, [])
        except Exception:
            return _memory_store.get(session_id, [])

    async def set(self, session_id: str, messages: list):
        try:
            if self._use_redis and self._redis:
                await self._redis.setex(
                    f"session:{session_id}",
                    SESSION_TTL,
                    json.dumps(messages, default=str)
                )
            else:
                _memory_store[session_id] = messages
        except Exception as e:
            logger.error("Session save failed", error=str(e))
            _memory_store[session_id] = messages

    async def delete(self, session_id: str):
        _memory_store.pop(session_id, None)
        if self._use_redis and self._redis:
            await self._redis.delete(f"session:{session_id}")

    async def count(self) -> int:
        if self._use_redis and self._redis:
            keys = await self._redis.keys("session:*")
            return len(keys)
        return len(_memory_store)


# Singleton
_store: Optional[SessionStore] = None


def get_session_store() -> SessionStore:
    global _store
    if _store is None:
        _store = SessionStore()
    return _store
