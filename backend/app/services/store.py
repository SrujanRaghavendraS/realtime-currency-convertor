"""Redis persistence for observations, sliding windows, last-known-good, tier snapshots and collector state."""
from __future__ import annotations

import json
from typing import Optional

from redis.asyncio import Redis

from app.config import BASE_CURRENCY, QUOTE_CURRENCIES, Settings

PREFIX = "fx:"


def k_window(ccy: str) -> str:
    return f"{PREFIX}window:{ccy}"


def k_lkg(ccy: str) -> str:
    return f"{PREFIX}lkg:{ccy}"


def k_snapshot(plan: str) -> str:
    return f"{PREFIX}snapshot:{plan}"


def k_since_update(plan: str) -> str:
    return f"{PREFIX}snapshot:{plan}:since_update"


K_COLLECTOR = f"{PREFIX}collector"
K_LOCK = f"{PREFIX}lock:collector"


class Store:
    def __init__(self, redis: Redis, settings: Settings):
        self.r = redis
        self.s = settings

    # ---- observations / window -------------------------------------------------
    @staticmethod
    def make_observation(ccy: str, rate: float, provider_timestamp: Optional[str], retrieved_at: str,
                         provider: str, provider_source: Optional[str] = None) -> dict:
        return {
            "pair": f"{BASE_CURRENCY}/{ccy}",
            "rate": rate,
            "provider_timestamp": provider_timestamp,
            "retrieved_at": retrieved_at,
            "provider": provider,
            "provider_source": provider_source,
        }

    async def append_observation(self, ccy: str, obs: dict, score: float) -> None:
        key = k_window(ccy)
        pipe = self.r.pipeline()
        pipe.zadd(key, {json.dumps(obs, sort_keys=True): score})
        # keep only the newest WINDOW_SIZE members
        pipe.zremrangebyrank(key, 0, -(self.s.window_size + 1))
        pipe.expire(key, self.s.window_ttl_seconds)
        pipe.set(k_lkg(ccy), json.dumps(obs))
        await pipe.execute()

    async def get_window(self, ccy: str) -> list[dict]:
        """Observations ordered oldest -> newest."""
        members = await self.r.zrange(k_window(ccy), 0, -1)
        return [json.loads(m) for m in members]

    async def get_lkg(self, ccy: str) -> Optional[dict]:
        raw = await self.r.get(k_lkg(ccy))
        return json.loads(raw) if raw else None

    # ---- snapshots --------------------------------------------------------------
    async def get_snapshot(self, plan: str) -> Optional[dict]:
        raw = await self.r.get(k_snapshot(plan))
        return json.loads(raw) if raw else None

    async def set_snapshot(self, plan: str, snapshot: dict) -> None:
        await self.r.set(k_snapshot(plan), json.dumps(snapshot))

    async def get_since_update(self, plan: str) -> int:
        return int(await self.r.get(k_since_update(plan)) or 0)

    async def set_since_update(self, plan: str, value: int) -> None:
        await self.r.set(k_since_update(plan), value)

    async def update_tier_snapshots(self, observations: dict[str, dict], updated_at: str, success_seq: int) -> None:
        """Premium every PREMIUM_UPDATE_EVERY_N successes, free every FREE_UPDATE_EVERY_N; empty snapshot fills at once."""
        for plan, every_n in (("premium", self.s.premium_update_every_n), ("free", self.s.free_update_every_n)):
            existing = await self.get_snapshot(plan)
            count = await self.get_since_update(plan) + 1
            if existing is None or count >= max(1, every_n):
                await self.set_snapshot(plan, {
                    "updated_at": updated_at,
                    "success_seq": success_seq,
                    "rates": observations,
                })
                count = 0
            await self.set_since_update(plan, count)

    # ---- collector state --------------------------------------------------------
    async def get_collector_state(self) -> dict:
        return await self.r.hgetall(K_COLLECTOR)

    async def set_collector_fields(self, **fields) -> None:
        mapping = {k: ("" if v is None else v) for k, v in fields.items()}
        if mapping:
            await self.r.hset(K_COLLECTOR, mapping=mapping)

    async def incr_successful_total(self) -> int:
        return int(await self.r.hincrby(K_COLLECTOR, "successful_collections_total", 1))

    async def window_summary(self) -> dict[str, dict]:
        out = {}
        for ccy in QUOTE_CURRENCIES:
            window = await self.get_window(ccy)
            out[ccy] = {
                "count": len(window),
                "latest_observation_at": window[-1]["retrieved_at"] if window else None,
            }
        return out
