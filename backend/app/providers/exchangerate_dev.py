"""exchangerate.dev adapter.

Endpoint: GET {PROVIDER_BASE_URL}/latest/{BASE}?symbols=INR,EUR,GBP,JPY
Auth: optional "Authorization: Bearer <key>" header (never in the query string, never logged).
"""
from __future__ import annotations

import asyncio
import logging
import math
from typing import Any, Awaitable, Callable, Optional, Sequence

import httpx

from app.config import Settings
from app.models.domain import AttemptRecord, Clock, ProviderResult, system_clock, to_iso

logger = logging.getLogger(__name__)

Sleep = Callable[[float], Awaitable[None]]


class InvalidResponse(Exception):
    pass


def parse_latest_response(body: Any, base: str, symbols: Sequence[str]) -> dict:
    """Validate and parse a success body. Raises InvalidResponse on any problem.

    Returns {"rates": {CCY: float}, "provider_timestamps": {CCY: iso}, "provider_sources": {CCY: str|None}}.
    """
    if not isinstance(body, dict):
        raise InvalidResponse("Response body is not a JSON object")
    if body.get("result") != "success":
        code = body.get("code") or "unknown"
        msg = body.get("message") or "provider reported an error"
        raise InvalidResponse(f"Provider error: {code} - {msg}")
    if body.get("base") != base:
        raise InvalidResponse(f"Unexpected base {body.get('base')!r}, expected {base}")
    rates = body.get("rates")
    if not isinstance(rates, dict):
        raise InvalidResponse("Missing rates object")

    effective_at = body.get("effective_at") if isinstance(body.get("effective_at"), dict) else {}
    sources = body.get("sources") if isinstance(body.get("sources"), dict) else {}
    data_updated_at = body.get("data_updated_at")

    parsed: dict[str, float] = {}
    timestamps: dict[str, Optional[str]] = {}
    for ccy in symbols:
        if ccy not in rates:
            raise InvalidResponse(f"Missing currency {ccy}")
        value = rates[ccy]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise InvalidResponse(f"Non-numeric rate for {ccy}")
        value = float(value)
        if not math.isfinite(value) or value <= 0:
            raise InvalidResponse(f"Invalid rate for {ccy}: {value}")
        parsed[ccy] = value
        # `timestamp` is response build time, NOT observation time -> use effective_at / data_updated_at.
        timestamps[ccy] = effective_at.get(ccy) or data_updated_at
    return {
        "rates": parsed,
        "provider_timestamps": timestamps,
        "provider_sources": {c: sources.get(c) for c in symbols},
        "market_session": body.get("market_session") if isinstance(body.get("market_session"), str) else None,
    }


def parse_quota_headers(headers: httpx.Headers, now: float) -> Optional[dict]:
    if "x-ratelimit-limit" not in headers and "x-ratelimit-remaining" not in headers:
        return None

    def _int(name: str) -> Optional[int]:
        try:
            return int(float(headers[name]))
        except (KeyError, ValueError):
            return None

    reset = _int("x-ratelimit-reset")
    return {
        "limit": _int("x-ratelimit-limit"),
        "remaining": _int("x-ratelimit-remaining"),
        "reset_at": to_iso(reset) if reset is not None else None,
        "scope": headers.get("x-ratelimit-scope"),
        "observed_at": to_iso(now),
    }


def _retry_after(headers: httpx.Headers) -> Optional[float]:
    try:
        return float(headers["retry-after"])
    except (KeyError, ValueError):
        return None


class ExchangeRateDevProvider:
    def __init__(
        self,
        settings: Settings,
        client: Optional[httpx.AsyncClient] = None,
        clock: Clock = system_clock,
        sleep: Sleep = asyncio.sleep,
    ):
        self.settings = settings
        self.name = settings.provider_name
        self._client = client
        self._clock = clock
        self._sleep = sleep

    def _headers(self) -> dict:
        key = self.settings.provider_api_key.strip()
        return {"Authorization": f"Bearer {key}"} if key else {}

    async def fetch_latest(self, base: str, symbols: Sequence[str]) -> ProviderResult:
        url = f"{self.settings.provider_base_url.rstrip('/')}/latest/{base}"
        params = {"symbols": ",".join(symbols)}
        attempts: list[AttemptRecord] = []
        result = ProviderResult(ok=False, base=base)
        max_tries = 1 + max(0, self.settings.provider_max_retries)

        client = self._client or httpx.AsyncClient(timeout=self.settings.provider_timeout_seconds)
        try:
            for i in range(max_tries):
                retryable = False
                now = self._clock()
                try:
                    resp = await client.get(
                        url, params=params, headers=self._headers(),
                        timeout=self.settings.provider_timeout_seconds,
                    )
                except httpx.TimeoutException:
                    reason = f"Timeout after {self.settings.provider_timeout_seconds:g}s"
                    attempts.append(AttemptRecord(at=now, ok=False, reason=reason))
                    result = ProviderResult(ok=False, base=base, error_type="TIMEOUT", error_message=reason)
                    retryable = True
                except httpx.TransportError as exc:
                    reason = f"Connection error ({type(exc).__name__})"
                    attempts.append(AttemptRecord(at=now, ok=False, reason=reason))
                    result = ProviderResult(ok=False, base=base, error_type="CONNECTION", error_message=reason)
                    retryable = True
                else:
                    result, retryable = self._handle_response(resp, base, symbols, now)
                    attempts.append(AttemptRecord(
                        at=now, ok=result.ok, http_status=resp.status_code, reason=result.error_message,
                    ))
                if result.ok or not retryable or i == max_tries - 1:
                    break
                delay = self.settings.provider_backoff_seconds * (2 ** i)
                logger.warning("Provider attempt %d failed (%s); retrying in %.1fs", i + 1, result.error_message, delay)
                await self._sleep(delay)
        finally:
            if self._client is None:
                await client.aclose()

        result.attempts = attempts
        return result

    def _handle_response(self, resp: httpx.Response, base: str, symbols: Sequence[str], now: float):
        quota = parse_quota_headers(resp.headers, now)
        delay_hdr = resp.headers.get("x-price-delay-seconds")
        price_delay = int(float(delay_hdr)) if delay_hdr and delay_hdr.replace(".", "", 1).isdigit() else None
        common = dict(base=base, quota=quota, price_delay_seconds=price_delay)

        def _err_detail() -> str:
            try:
                body = resp.json()
                if isinstance(body, dict) and body.get("code"):
                    return f" ({body['code']})"
            except ValueError:
                pass
            return ""

        if resp.status_code == 429:
            # Never retried within this run; Retry-After is honoured by the next collector run.
            return ProviderResult(
                ok=False, error_type="HTTP_429", error_message=f"HTTP 429{_err_detail()}",
                retry_after_seconds=_retry_after(resp.headers), **common,
            ), False
        if resp.status_code >= 500:
            return ProviderResult(ok=False, error_type="HTTP_ERROR",
                                  error_message=f"HTTP {resp.status_code}", **common), True
        if resp.status_code >= 400:
            return ProviderResult(ok=False, error_type="HTTP_ERROR",
                                  error_message=f"HTTP {resp.status_code}{_err_detail()}", **common), False
        try:
            body = resp.json()
        except ValueError:
            return ProviderResult(ok=False, error_type="INVALID_RESPONSE",
                                  error_message="Invalid response: body is not JSON", **common), False
        try:
            parsed = parse_latest_response(body, base, symbols)
        except InvalidResponse as exc:
            return ProviderResult(ok=False, error_type="INVALID_RESPONSE",
                                  error_message=f"Invalid response: {exc}", **common), False
        return ProviderResult(ok=True, retrieved_at=now, **parsed, **common), False
