"""Market-aware collection schedule with a monthly budget guard. Pure functions (clock passed in)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from app.config import Settings


async def load_schedule(store, recorder, settings: Settings, now: float) -> dict:
    """compute_schedule using current Redis state (requests this month, provider market_session)."""
    state = await store.get_collector_state()
    used = await recorder.requests_this_month(now)
    return compute_schedule(now, settings, used, state.get("provider_market_session"))


OPEN, CLOSED = "OPEN", "CLOSED"


def market_session(now: float) -> str:
    """FX market is OPEN from Sunday 22:00 UTC to Friday 22:00 UTC; otherwise CLOSED."""
    dt = datetime.fromtimestamp(now, tz=timezone.utc)
    wd, hour = dt.weekday(), dt.hour  # Mon=0 .. Sun=6
    if wd <= 3:
        return OPEN
    if wd == 4:
        return OPEN if hour < 22 else CLOSED
    if wd == 6:
        return OPEN if hour >= 22 else CLOSED
    return CLOSED


def _month_bounds(now: float) -> tuple[datetime, datetime]:
    dt = datetime.fromtimestamp(now, tz=timezone.utc)
    start = dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end = (start.replace(year=start.year + 1, month=1) if start.month == 12 else start.replace(month=start.month + 1))
    return start, end


def base_intervals(settings: Settings) -> tuple[int, int]:
    """(trading, non_trading). COLLECTION_INTERVAL_SECONDS, if explicitly set, overrides both (legacy alias)."""
    if settings.collection_interval_seconds:
        return settings.collection_interval_seconds, settings.collection_interval_seconds
    return settings.trading_interval_seconds, settings.non_trading_interval_seconds


def projected_monthly_calls(now: float, settings: Settings) -> int:
    trading, non_trading = base_intervals(settings)
    start, end = _month_bounds(now)
    open_s = closed_s = 0
    t = start
    while t < end:  # hourly granularity is exact: session boundaries are on the hour
        if market_session(t.timestamp()) == OPEN:
            open_s += 3600
        else:
            closed_s += 3600
        t += timedelta(hours=1)
    return round(open_s / trading + closed_s / non_trading)


def fmt_minutes(seconds: float) -> str:
    m = seconds / 60
    return f"{m:.0f} min" if abs(m - round(m)) < 0.05 else f"{m:.1f} min"


def compute_schedule(now: float, settings: Settings, requests_this_month: int,
                     provider_market_session: Optional[str] = None) -> dict:
    trading, non_trading = base_intervals(settings)
    session = market_session(now)
    base = trading if session == OPEN else non_trading
    _, month_end = _month_bounds(now)
    seconds_left = max(0.0, month_end.timestamp() - now)
    calls_left = max(1.0, (settings.provider_monthly_limit - requests_this_month) * settings.budget_safety)
    budget_interval = int(seconds_left / calls_left)
    effective = max(base, budget_interval)
    adjusted = effective > base

    limit_txt = f"{settings.provider_monthly_limit:,}/month budget"
    label = "FX market open" if session == OPEN else "FX market closed (weekend)"
    if adjusted:
        reason = f"{label}: interval stretched to {fmt_minutes(effective)} to stay within the {limit_txt}."
    else:
        reason = f"{label}: collecting every {fmt_minutes(effective)} (within {limit_txt})."
    return {
        "market_session": session,
        "provider_market_session": provider_market_session or None,
        "current_interval_seconds": effective,
        "trading_interval_seconds": trading,
        "non_trading_interval_seconds": non_trading,
        "budget_adjusted": adjusted,
        "budget_interval_seconds": budget_interval,
        "projected_monthly_calls": projected_monthly_calls(now, settings),
        "reason": reason,
    }
