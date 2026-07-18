"""
Redis hot-state wrapper.

Stage 1 usage: per-exchange connection/coverage state + heartbeat timestamp,
so /status (stage 3) and the signal_engine (stage 2) can read current
coverage without hitting Postgres. Active-signal state (TTL = Expiration)
is added when signal_engine lands.
"""
from __future__ import annotations

import json
import time
from typing import Any

import redis.asyncio as aioredis


class RedisState:
    def __init__(self, url: str):
        self._url = url
        self.client: aioredis.Redis | None = None

    async def connect(self) -> None:
        self.client = aioredis.from_url(self._url, decode_responses=True)
        await self.client.ping()

    async def close(self) -> None:
        if self.client:
            await self.client.aclose()

    # ---------------- coverage / connectivity ----------------
    async def set_exchange_status(self, exchange: str, status: dict[str, Any]) -> None:
        assert self.client is not None
        status = {**status, "updated_at": time.time()}
        await self.client.hset("exchange_status", exchange, json.dumps(status))

    async def get_all_exchange_status(self) -> dict[str, dict]:
        assert self.client is not None
        raw = await self.client.hgetall("exchange_status")
        return {k: json.loads(v) for k, v in raw.items()}

    async def set_heartbeat(self) -> None:
        assert self.client is not None
        await self.client.set("bot:last_heartbeat", time.time())

    async def get_heartbeat(self) -> float | None:
        assert self.client is not None
        val = await self.client.get("bot:last_heartbeat")
        return float(val) if val is not None else None
