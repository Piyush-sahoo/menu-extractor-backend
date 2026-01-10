"""
Redis Cache Service.
Fast cache with 1-hour TTL for recent lookups.
"""
import json
import logging
from typing import Optional, Dict, Any
import redis.asyncio as redis
from app.core.config import settings

logger = logging.getLogger(__name__)

class CacheService:
    """Redis cache with 1-hour TTL."""
    
    def __init__(self):
        self.redis = redis.from_url(settings.REDIS_URL, decode_responses=True)
        self.ttl = 3600  # 1 hour cache (60 * 60 seconds)

    async def get_menu(self, key: str) -> Optional[Dict[str, Any]]:
        """Get menu from cache."""
        try:
            data = await self.redis.get(key)
            if data:
                logger.info(f"Cache HIT: {key[:50]}...")
                return json.loads(data)
        except Exception as e:
            logger.warning(f"Redis Get Error: {e}")
        return None

    async def set_menu(self, key: str, data: Dict[str, Any]):
        """Set menu in cache with 1-hour TTL."""
        try:
            await self.redis.setex(key, self.ttl, json.dumps(data, default=str))
            logger.info(f"Cache SET: {key[:50]}... (TTL: {self.ttl}s)")
        except Exception as e:
            logger.warning(f"Redis Set Error: {e}")

    async def delete(self, key: str):
        """Delete key from cache."""
        try:
            await self.redis.delete(key)
        except Exception as e:
            logger.warning(f"Redis Delete Error: {e}")

    async def close(self):
        await self.redis.close()
