"""Background collector: the ONLY component that calls the real provider."""
from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Optional

from app.config import BASE_CURRENCY, QUOTE_CURRENCIES, Settings
from app.metrics.recorder import MetricsRecorder, epoch_or_none
from app.collector.schedule import load_schedule
from app.models.domain import Clock, parse_iso, to_iso
from app.providers.base import RateProvider
from app.services.store import K_LOCK, Store

logger = logging.getLogger(__name__)

SUCCESS, FAILURE, SKIPPED_LOCKED, SKIPPED_QUOTA = "SUCCESS", "FAILURE", "SKIPPED_LOCKED", "SKIPPED_QUOTA"


class Collector:
    def __init__(self, store: Store, metrics: MetricsRecorder, provider: RateProvider,
                 settings: Settings, clock: Clock):
        self.store = store
        self.metrics = metrics
        self.provider = provider
        self.s = settings
        self.clock = clock
        self._task: Optional[asyncio.Task] = None

    # ---- lock --------------------------------------------------------------
    async def _acquire_lock(self) -> Optional[str]:
        token = uuid.uuid4().hex
        ok = await self.store.r.set(K_LOCK, token, nx=True, ex=self.s.collector_lock_ttl_seconds)
        return token if ok else None

    async def _release_lock(self, token: str) -> None:
        if await self.store.r.get(K_LOCK) == token:
            await self.store.r.delete(K_LOCK)

    # ---- quota guard -------------------------------------------------------
    async def _quota_block_reason(self, now: float) -> Optional[str]:
        retry_until = await self.metrics.get_retry_after_until()
        if retry_until and retry_until > now:
            return f"Honouring provider Retry-After until {to_iso(retry_until)}"
        if await self.metrics.requests_this_month(now) >= self.s.provider_monthly_limit:
            return "Monthly request quota exhausted"
        reported = await self.metrics.get_provider_quota()
        if reported and reported.get("remaining") == 0:
            reset = parse_iso(reported.get("reset_at"))
            if reset is None or reset > now:
                return f"Provider-reported quota exhausted ({reported.get('scope')})"
        if await self.metrics.rolling_minute_count(now) >= self.s.internal_per_minute_limit:
            return "Internal per-minute request guard reached"
        return None

    # ---- one run -----------------------------------------------------------
    async def run_once(self) -> str:
        now = self.clock()
        token = await self._acquire_lock()
        if token is None:
            await self.store.set_collector_fields(last_run_at=now, last_outcome=SKIPPED_LOCKED)
            logger.info("Collection skipped: another run holds the lock")
            return SKIPPED_LOCKED
        try:
            block = await self._quota_block_reason(now)
            if block:
                await self.store.set_collector_fields(last_run_at=now, last_outcome=SKIPPED_QUOTA,
                                                      last_skip_reason=block)
                logger.warning("Collection skipped: %s", block)
                return SKIPPED_QUOTA

            result = await self.provider.fetch_latest(BASE_CURRENCY, QUOTE_CURRENCIES)
            for attempt in result.attempts:
                await self.metrics.record_attempt(attempt)
            if result.quota:
                await self.metrics.set_provider_quota(result.quota)
            if result.price_delay_seconds is not None:
                await self.metrics.set_price_delay(result.price_delay_seconds)
            if result.retry_after_seconds:
                await self.metrics.set_retry_after_until(self.clock() + result.retry_after_seconds)

            if not result.ok:
                await self.store.set_collector_fields(
                    last_run_at=now, last_outcome=FAILURE, last_attempt_ok=0,
                    last_failure_at=self.clock(), last_failure_reason=result.error_message,
                )
                logger.warning("Collection failed: %s", result.error_message)
                return FAILURE

            retrieved_at = result.retrieved_at or self.clock()
            retrieved_iso = to_iso(retrieved_at)
            observations = {}
            for ccy in QUOTE_CURRENCIES:
                obs = Store.make_observation(
                    ccy, result.rates[ccy], result.provider_timestamps.get(ccy), retrieved_iso,
                    self.provider.name, result.provider_sources.get(ccy),
                )
                await self.store.append_observation(ccy, obs, retrieved_at)
                observations[ccy] = obs
            if result.market_session:
                await self.store.set_collector_fields(provider_market_session=result.market_session)
            seq = await self.store.incr_successful_total()
            await self.store.update_tier_snapshots(observations, retrieved_iso, seq)
            await self.store.set_collector_fields(
                last_run_at=now, last_outcome=SUCCESS, last_attempt_ok=1, last_success_at=retrieved_at,
            )
            logger.info("Collection succeeded (#%d)", seq)
            return SUCCESS
        finally:
            await self._release_lock(token)

    # ---- loop --------------------------------------------------------------
    async def current_interval(self) -> int:
        """Effective interval (market-aware, stretched by the monthly budget guard)."""
        sched = await load_schedule(self.store, self.metrics, self.s, self.clock())
        return sched["current_interval_seconds"]

    async def initial_delay(self) -> float:
        """Collect immediately only if the last success is older than the interval (or none)."""
        state = await self.store.get_collector_state()
        last = epoch_or_none(state.get("last_success_at"))
        if last is None:
            return 0.0
        interval = await self.current_interval()
        return max(0.0, last + interval - self.clock())

    async def _loop(self) -> None:
        try:
            delay = await self.initial_delay()
        except Exception:
            logger.exception("Could not read collector state; collecting now")
            delay = 0.0
        while True:
            try:
                await self.store.set_collector_fields(next_run_at=self.clock() + delay)
            except Exception:
                logger.exception("Could not persist next_run_at")
            await asyncio.sleep(delay)
            try:
                await self.run_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Collector run crashed")
            try:
                delay = await self.current_interval()
            except Exception:
                logger.exception("Could not compute schedule; using non-trading interval")
                delay = self.s.collection_interval_seconds or self.s.non_trading_interval_seconds

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._loop(), name="fx-collector")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None
