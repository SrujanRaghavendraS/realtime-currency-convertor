"""Wires all services together (simple manual dependency injection)."""
from __future__ import annotations

from dataclasses import dataclass

from redis.asyncio import Redis

from app.collector.runner import Collector
from app.config import Settings
from app.metrics.recorder import MetricsRecorder
from app.metrics.service import MetricsService
from app.models.domain import Clock
from app.providers.base import RateProvider
from app.services.rates import RatesService
from app.services.simulation import SimulationService
from app.services.store import Store


@dataclass
class Services:
    settings: Settings
    redis: Redis
    clock: Clock
    store: Store
    recorder: MetricsRecorder
    sims: SimulationService
    rates: RatesService
    metrics: MetricsService
    collector: Collector


def build_services(settings: Settings, redis: Redis, provider: RateProvider, clock: Clock) -> Services:
    store = Store(redis, settings)
    recorder = MetricsRecorder(redis)
    sims = SimulationService(redis, settings, recorder)
    rates = RatesService(store, sims, settings, recorder)
    metrics = MetricsService(store, recorder, rates, settings)
    collector = Collector(store, recorder, provider, settings, clock)
    return Services(settings, redis, clock, store, recorder, sims, rates, metrics, collector)
