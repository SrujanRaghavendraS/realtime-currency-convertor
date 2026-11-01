"""Demo simulations for the free and premium plans. Stored in Redis, fully independent of each other.

All state is derived from timestamps (started_at / expires_at / stopped_at) and the injected clock,
so the stage timeline and auto-expiry need no background task.
"""
from __future__ import annotations

import json
from typing import Optional

from redis.asyncio import Redis

from app.config import Settings
from app.metrics.recorder import MetricsRecorder
from app.models.domain import FailureType, to_iso
from app.providers.simulated import SIMULATED_EVENTS, SIMULATED_REASONS

PREMIUM_STAGES = ("PRIMARY_PREMIUM", "SECONDARY_PREMIUM", "PUBLIC_API", "LAST_KNOWN_GOOD")
PREMIUM_SIM_REASON = "Primary premium unavailable (simulated)"
PREMIUM_STAGE_EVENTS = (
    "Primary premium provider unavailable (simulated)",
    "Secondary premium provider unavailable (simulated)",
    "Serving premium from latest valid public API observation",
    "Public API also failing (simulated); serving last-known-good rate",
)


def k_sim(plan: str) -> str:
    return f"fx:sim:{plan}"


class SimulationService:
    def __init__(self, redis: Redis, settings: Settings, metrics: MetricsRecorder):
        self.r = redis
        self.s = settings
        self.metrics = metrics

    async def get(self, plan: str) -> Optional[dict]:
        raw = await self.r.get(k_sim(plan))
        return json.loads(raw) if raw else None

    @staticmethod
    def is_active(sim: Optional[dict], now: float) -> bool:
        return bool(sim) and sim.get("stopped_at") is None and now < sim["expires_at"]

    @staticmethod
    def ended_at(sim: Optional[dict], now: float) -> Optional[float]:
        if not sim:
            return None
        if sim.get("stopped_at") is not None:
            return sim["stopped_at"]
        if now >= sim["expires_at"]:
            return sim["expires_at"]
        return None

    def recovery(self, sim: Optional[dict], now: float) -> dict:
        if self.is_active(sim, now):
            return {"state": "FAILING", "recovered_at": None}
        ended = self.ended_at(sim, now)
        if ended is not None and now - ended <= self.s.demo_recovery_seconds:
            return {"state": "RECOVERED", "recovered_at": to_iso(ended)}
        return {"state": "IDLE", "recovered_at": None}

    def premium_stage_index(self, sim: dict, now: float) -> int:
        elapsed = max(0.0, now - sim["started_at"])
        return min(len(PREMIUM_STAGES) - 1, int(elapsed // max(1, self.s.demo_stage_seconds)))

    async def start(self, plan: str, now: float, failure_type: FailureType = FailureType.HTTP_429) -> dict:
        sim = {
            "started_at": now,
            "expires_at": now + self.s.demo_duration_seconds,
            "stopped_at": None,
            "failure_type": failure_type.value if plan == "free" else None,
        }
        await self.r.set(k_sim(plan), json.dumps(sim))
        reason = SIMULATED_REASONS[failure_type] if plan == "free" else PREMIUM_SIM_REASON
        await self.metrics.record_simulated_failure(plan, reason)
        return sim

    async def stop(self, plan: str, now: float) -> Optional[dict]:
        sim = await self.get(plan)
        if self.is_active(sim, now):
            sim["stopped_at"] = now
            await self.r.set(k_sim(plan), json.dumps(sim))
        return sim

    def events(self, plan: str, sim: Optional[dict], now: float) -> list[dict]:
        if not sim:
            return []
        start = sim["started_at"]
        end = self.ended_at(sim, now)
        horizon = end if end is not None else now
        events: list[dict] = []
        if plan == "free":
            ft = FailureType(sim["failure_type"])
            events.append({"at": to_iso(start), "message": SIMULATED_EVENTS[ft]})
            events.append({"at": to_iso(start), "message": "Free plan switched to fallback (no real provider call made)"})
        else:
            idx = self.premium_stage_index(sim, horizon)
            for i in range(idx + 1):
                events.append({"at": to_iso(start + i * self.s.demo_stage_seconds), "message": PREMIUM_STAGE_EVENTS[i]})
        if end is not None:
            how = "stopped" if sim.get("stopped_at") is not None else "expired"
            events.append({"at": to_iso(end), "message": f"Simulation {how}; provider recovered"})
        return events
