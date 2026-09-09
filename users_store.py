from __future__ import annotations

from datetime import datetime
from typing import Optional
from redis_client import redis

USERS_INDEX_KEY = "users:index"


def user_key(chat_id: int) -> str:
    return f"user:{chat_id}"


class UsersStore:
    async def get_raw(self, chat_id: int) -> Optional[dict]:
        data = await redis.hgetall(user_key(chat_id))
        return data or None

    async def set_url(self, chat_id: int, url: str) -> None:
        existing = await self.get_raw(chat_id)
        muted = existing.get("muted") == "1" if existing else False
        await redis.hset(
            user_key(chat_id),
            mapping={
                "url": url,
                "muted": "1" if muted else "0",
                "updated_at": datetime.now().isoformat(timespec="seconds"),
            },
        )
        await redis.sadd(USERS_INDEX_KEY, chat_id)

    async def get_url(self, chat_id: int) -> Optional[str]:
        entry = await self.get_raw(chat_id)
        return entry["url"] if entry else None

    async def set_muted(self, chat_id: int, muted: bool) -> bool:
        if not await redis.exists(user_key(chat_id)):
            return False
        await redis.hset(user_key(chat_id), key="muted", value="1" if muted else "0")
        return True

    async def is_muted(self, chat_id: int) -> bool:
        entry = await self.get_raw(chat_id)
        return bool(entry) and entry.get("muted") == "1"

    async def remove(self, chat_id: int) -> bool:
        key = user_key(chat_id)
        existed = bool(await redis.exists(key))
        if existed:
            await redis.delete(key)
            await redis.srem(USERS_INDEX_KEY, chat_id)
        return existed

    async def items(self) -> list[tuple[int, str]]:
        chat_ids = await redis.smembers(USERS_INDEX_KEY)
        result = []
        for chat_id in chat_ids:
            url = await self.get_url(int(chat_id))
            if url:
                result.append((int(chat_id), url))
        return result
