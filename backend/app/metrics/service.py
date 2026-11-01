"""Builds the /api/metrics response."""
from __future__ import annotations

from app.collector.schedule import base_intervals, load_schedule
from app.config import Settings
from app.metrics.recorder import MetricsRecorder, epoch_or_none, iso_from_field
from app.models.domain import month_key
from app.services.rates import RatesService
from app.services.store import K_LOCK, Store


def collector_health(state: dict, settings: Settings, now: float) -> str:
    last_run = epoch_or_none(state.get("last_run_at"))
    if last_run is None:
        return "STARTING"
    if now - last_run > 2 * max(base_intervals(settings)):
        return "DOWN"
    if state.get("last_attempt_ok") == "0":
        return "DEGRADED"
    return "HEALTHY"


class MetricsService:
    def __init__(self, store: Store, recorder: MetricsRecorder, rates: RatesService, settings: Settings):
        self.store = store
        self.rec = recorder
        self.rates = rates
        self.s = settings

    async def build(self, now: float) -> dict:
        s = self.s
        month = await self.rec.month_counts(now)
        rel = await self.rec.reliability()
        state = await self.store.get_collector_state()
        per_pair = await self.store.window_summary()
        counts = [p["count"] for p in per_pair.values()]
        latest = [p["latest_observation_at"] for p in per_pair.values() if p["latest_observation_at"]]
        observation_count = min(counts) if counts else 0
        free_rates = await self.rates.build("free", now)
        schedule = await load_schedule(self.store, self.rec, s, now)
        requests = month["requests"]
        remaining = max(0, s.provider_monthly_limit - requests)

        return {
            "provider": {
                "name": s.provider_name,
                "documented_monthly_limit": s.provider_monthly_limit,
                "documented_per_minute_limit": s.provider_per_minute_limit,
                "provider_reported_quota": await self.rec.get_provider_quota(),
                "price_delay_seconds": await self.rec.get_price_delay(),
                "docs_url": s.provider_docs_url,
            },
            "usage": {
                "month": month_key(now),
                "requests_this_month": requests,
                "monthly_limit": s.provider_monthly_limit,
                "remaining": remaining,
                "usage_percent": round(100.0 * requests / s.provider_monthly_limit, 2) if s.provider_monthly_limit else 0.0,
                "rolling_minute_count": await self.rec.rolling_minute_count(now),
                "per_minute_limit": s.internal_per_minute_limit,
            },
            "reliability": {
                "successful_requests": int(rel.get("success", 0)),
                "failed_requests": int(rel.get("failure", 0)),
                "http_429_count": int(rel.get("http_429", 0)),
                "last_success_at": iso_from_field(rel.get("last_success_at")),
                "last_failure_at": iso_from_field(rel.get("last_failure_at")),
                "last_failure_reason": rel.get("last_failure_reason") or None,
            },
            "sliding_window": {
                "max_observations": s.window_size,
                "ewma_alpha": s.ewma_alpha,
                "ewma_min_observations": s.ewma_min_observations,
                "per_pair": per_pair,
                "observation_count": observation_count,
                "latest_observation_at": max(latest) if latest else None,
                "ewma_status": "READY" if observation_count >= s.ewma_min_observations else "INSUFFICIENT_DATA",
                "fallback_status": free_rates["fallback"]["method"],
            },
            "collector": {
                "health": collector_health(state, s, now),
                "interval_seconds": schedule["current_interval_seconds"],
                "running_now": bool(await self.store.r.exists(K_LOCK)),
                "last_run_at": iso_from_field(state.get("last_run_at")),
                "next_run_at": iso_from_field(state.get("next_run_at")),
                "last_success_at": iso_from_field(state.get("last_success_at")),
                "last_outcome": state.get("last_outcome") or None,
                "successful_collections_total": int(state.get("successful_collections_total") or 0),
                "schedule": schedule,
            },
            "simulated": {
                "free": await self.rec.simulated("free"),
                "premium": await self.rec.simulated("premium"),
            },
        }


