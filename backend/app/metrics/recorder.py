"""Real provider quota/reliability accounting and simulated-failure counters (kept strictly separate)."""
from __future__ import annotations

import json
import uuid
from typing import Optional

from redis.asyncio import Redis

from app.models.domain import AttemptRecord, month_key, to_iso

PREFIX = "fx:"
K_MINUTE = f"{PREFIX}minute"
K_RELIABILITY = f"{PREFIX}reliability"
K_PROVIDER_QUOTA = f"{PREFIX}provider_quota"
K_PRICE_DELAY = f"{PREFIX}price_delay_seconds"
K_RETRY_AFTER_UNTIL = f"{PREFIX}retry_after_until"
MONTH_TTL_SECONDS = 62 * 24 * 3600


def k_quota(month: str) -> str:
    return f"{PREFIX}quota:{month}"


def k_simulated(plan: str) -> str:
    return f"{PREFIX}simulated:{plan}"


class MetricsRecorder:
    def __init__(self, redis: Redis):
        self.r = redis

    # ---- real attempts -----------------------------------------------------
    async def record_attempt(self, attempt: AttemptRecord) -> None:
        qkey = k_quota(month_key(attempt.at))
        is_429 = attempt.http_status == 429
        pipe = self.r.pipeline()
        pipe.hincrby(qkey, "requests", 1)
        pipe.hincrby(qkey, "success" if attempt.ok else "failure", 1)
        if is_429:
            pipe.hincrby(qkey, "http_429", 1)
        pipe.expire(qkey, MONTH_TTL_SECONDS)
        pipe.zadd(K_MINUTE, {f"{attempt.at}:{uuid.uuid4().hex}": attempt.at})
        pipe.hincrby(K_RELIABILITY, "success" if attempt.ok else "failure", 1)
        if is_429:
            pipe.hincrby(K_RELIABILITY, "http_429", 1)
        if attempt.ok:
            pipe.hset(K_RELIABILITY, "last_success_at", attempt.at)
        else:
            pipe.hset(K_RELIABILITY, mapping={
                "last_failure_at": attempt.at,
                "last_failure_reason": attempt.reason or "Unknown error",
            })
        await pipe.execute()

    async def requests_this_month(self, now: float) -> int:
        return int(await self.r.hget(k_quota(month_key(now)), "requests") or 0)

    async def month_counts(self, now: float) -> dict:
        raw = await self.r.hgetall(k_quota(month_key(now)))
        return {k: int(raw.get(k, 0)) for k in ("requests", "success", "failure", "http_429")}

    async def rolling_minute_count(self, now: float) -> int:
        await self.r.zremrangebyscore(K_MINUTE, "-inf", now - 60)
        return int(await self.r.zcount(K_MINUTE, now - 60, "+inf"))

    async def reliability(self) -> dict:
        return await self.r.hgetall(K_RELIABILITY)

    # ---- provider-reported quota / retry-after ------------------------------
    async def set_provider_quota(self, quota: dict) -> None:
        await self.r.set(K_PROVIDER_QUOTA, json.dumps(quota))

    async def get_provider_quota(self) -> Optional[dict]:
        raw = await self.r.get(K_PROVIDER_QUOTA)
        return json.loads(raw) if raw else None

    async def set_price_delay(self, seconds: int) -> None:
        await self.r.set(K_PRICE_DELAY, seconds)

    async def get_price_delay(self) -> Optional[int]:
        raw = await self.r.get(K_PRICE_DELAY)
        return int(raw) if raw else None

    async def set_retry_after_until(self, epoch: float) -> None:
        await self.r.set(K_RETRY_AFTER_UNTIL, epoch)

    async def get_retry_after_until(self) -> Optional[float]:
        raw = await self.r.get(K_RETRY_AFTER_UNTIL)
        return float(raw) if raw else None

    # ---- simulated (never mixed with real counts) ---------------------------
    async def record_simulated_failure(self, plan: str, reason: str) -> None:
        pipe = self.r.pipeline()
        pipe.hincrby(k_simulated(plan), "simulated_failures", 1)
        pipe.hset(k_simulated(plan), "last_simulated_failure_reason", reason)
        await pipe.execute()

    async def simulated(self, plan: str) -> dict:
        raw = await self.r.hgetall(k_simulated(plan))
        return {
            "simulated_failures": int(raw.get("simulated_failures", 0)),
            "last_simulated_failure_reason": raw.get("last_simulated_failure_reason") or None,
        }


def epoch_or_none(value) -> Optional[float]:
    if value in (None, ""):
        return None
    return float(value)


def iso_from_field(value) -> Optional[str]:
    return to_iso(epoch_or_none(value))
