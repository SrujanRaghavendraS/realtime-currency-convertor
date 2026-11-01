"""Internal domain types, enums and time helpers."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Callable, Optional

from pydantic import BaseModel

Clock = Callable[[], float]  # returns unix epoch seconds; injectable for tests


def system_clock() -> float:
    return time.time()


def to_iso(epoch: Optional[float]) -> Optional[str]:
    if epoch is None:
        return None
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(value: Optional[str]) -> Optional[float]:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


def month_key(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m")


class RateStatus(str, Enum):
    LIVE_FROM_PROVIDER = "LIVE_FROM_PROVIDER"
    CACHED = "CACHED"
    FALLBACK_ESTIMATED = "FALLBACK_ESTIMATED"
    STALE = "STALE"
    UNAVAILABLE = "UNAVAILABLE"


# Worst-first ordering used to compute overall_status.
STATUS_SEVERITY = {
    RateStatus.LIVE_FROM_PROVIDER: 0,
    RateStatus.CACHED: 1,
    RateStatus.FALLBACK_ESTIMATED: 2,
    RateStatus.STALE: 3,
    RateStatus.UNAVAILABLE: 4,
}


class FailureType(str, Enum):
    HTTP_429 = "HTTP_429"
    OUTAGE = "OUTAGE"
    TIMEOUT = "TIMEOUT"


class Plan(str, Enum):
    free = "free"
    premium = "premium"


class DemoStartRequest(BaseModel):
    failure_type: FailureType = FailureType.HTTP_429


@dataclass
class AttemptRecord:
    """One real HTTP request made to the provider (counts against quota)."""
    at: float
    ok: bool
    http_status: Optional[int] = None
    reason: Optional[str] = None


@dataclass
class ProviderResult:
    ok: bool
    base: str = "USD"
    rates: dict[str, float] = field(default_factory=dict)
    # Per-currency observation time reported by the provider (ISO string).
    provider_timestamps: dict[str, Optional[str]] = field(default_factory=dict)
    provider_sources: dict[str, Optional[str]] = field(default_factory=dict)
    retrieved_at: Optional[float] = None
    error_type: Optional[str] = None  # TIMEOUT | CONNECTION | HTTP_429 | HTTP_ERROR | INVALID_RESPONSE | PROVIDER_ERROR
    error_message: Optional[str] = None
    retry_after_seconds: Optional[float] = None
    quota: Optional[dict] = None  # parsed X-RateLimit-* headers, or None
    price_delay_seconds: Optional[int] = None
    market_session: Optional[str] = None  # provider's own market_session string, display only
    attempts: list[AttemptRecord] = field(default_factory=list)
    simulated: bool = False
