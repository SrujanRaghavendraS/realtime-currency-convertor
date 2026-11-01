"""Small, fast core tests (no real network, fakeredis only)."""
import fakeredis
import httpx
import pytest
import respx

from app.config import Settings
from app.fallback.ewma import ewma
from app.main import create_app
from app.providers.exchangerate_dev import ExchangeRateDevProvider

BASE_URL = "https://api.exchangerate.dev/v1"
SAMPLE = {
    "result": "success", "base": "USD", "source": "ecb_daily",
    "sources": {"INR": "ecb_daily", "EUR": "ecb_daily", "GBP": "ecb_daily", "JPY": "market_daily"},
    "timestamp": "2026-11-01T06:05:23Z", "data_updated_at": "2026-10-30T00:00:00Z",
    "effective_at": {"INR": "2026-10-30T00:00:00Z", "EUR": "2026-10-30T00:00:00Z",
                     "GBP": "2026-10-30T00:00:00Z", "JPY": "2026-10-30T00:00:00Z"},
    "rates": {"INR": 94.955, "EUR": 0.89509, "GBP": 0.74633, "JPY": 157.25},
}
HEADERS = {"X-RateLimit-Limit": "10", "X-RateLimit-Remaining": "9", "X-RateLimit-Reset": "1793520000",
           "X-RateLimit-Scope": "tier-rate-minute", "X-Price-Delay-Seconds": "900"}


class FakeClock:
    def __init__(self, t: float = 1793520000.0):
        self.t = t

    def __call__(self) -> float:
        return self.t


async def _nosleep(_):
    return None


@pytest.fixture
def env():
    clock = FakeClock()
    settings = Settings(demo_mode=True, provider_backoff_seconds=0, internal_per_minute_limit=1000, _env_file=None)
    redis = fakeredis.FakeAsyncRedis(decode_responses=True)
    provider = ExchangeRateDevProvider(settings, clock=clock, sleep=_nosleep)
    app = create_app(settings=settings, redis=redis, provider=provider, clock=clock, start_collector=False)
    return app, app.state.services, clock


def test_ewma_hand_computed():
    # s=10 -> 0.4*20+0.6*10=14 -> 0.4*30+0.6*14=20.4
    assert ewma([10, 20, 30], 0.4) == pytest.approx(20.4)
    assert ewma([5], 0.4) == 5


@respx.mock
async def test_provider_valid_and_invalid(env):
    _, svc, _ = env
    route = respx.get(f"{BASE_URL}/latest/USD").mock(return_value=httpx.Response(200, json=SAMPLE, headers=HEADERS))
    res = await svc.collector.provider.fetch_latest("USD", ["INR", "EUR", "GBP", "JPY"])
    assert res.ok and res.rates["INR"] == 94.955
    assert res.provider_timestamps["INR"] == "2026-10-30T00:00:00Z"
    assert res.quota["remaining"] == 9 and res.price_delay_seconds == 900
    assert route.calls.last.request.url.params["symbols"] == "INR,EUR,GBP,JPY"
    assert "authorization" not in route.calls.last.request.headers  # keyless by default

    bad = {**SAMPLE, "rates": {"INR": 94.9, "EUR": -1, "GBP": 0.7}}
    route.mock(return_value=httpx.Response(200, json=bad))
    res = await svc.collector.provider.fetch_latest("USD", ["INR", "EUR", "GBP", "JPY"])
    assert not res.ok and res.error_type == "INVALID_RESPONSE"
    assert len(res.attempts) == 1  # invalid responses are not retried


@respx.mock
async def test_window_trims_to_15(env):
    _, svc, clock = env
    respx.get(f"{BASE_URL}/latest/USD").mock(return_value=httpx.Response(200, json=SAMPLE))
    for _ in range(18):
        clock.t += 900
        assert await svc.collector.run_once() == "SUCCESS"
    assert len(await svc.store.get_window("INR")) == 15
    m = await svc.metrics.build(clock())
    assert m["usage"]["requests_this_month"] == 18


@respx.mock
async def test_free_vs_premium_snapshot_policy(env):
    _, svc, clock = env
    respx.get(f"{BASE_URL}/latest/USD").mock(return_value=httpx.Response(200, json=SAMPLE))
    statuses = []
    for _ in range(6):
        clock.t += 900
        await svc.collector.run_once()
        free = await svc.rates.build("free", clock())
        prem = await svc.rates.build("premium", clock())
        assert prem["overall_status"] == "LIVE_FROM_PROVIDER"
        statuses.append(free["overall_status"])
    # 1st fills empty snapshot, 2-5 hold (CACHED), 6th = 5th success since update refreshes.
    assert statuses == ["LIVE_FROM_PROVIDER", "CACHED", "CACHED", "CACHED", "CACHED", "LIVE_FROM_PROVIDER"]


@respx.mock
async def test_free_sim_does_not_affect_premium(env):
    app, svc, clock = env
    route = respx.get(f"{BASE_URL}/latest/USD").mock(return_value=httpx.Response(200, json=SAMPLE))
    for _ in range(3):
        clock.t += 900
        await svc.collector.run_once()
    calls_before = route.call_count

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post("/api/demo/free/start", json={"failure_type": "HTTP_429"})
        assert r.status_code == 200 and r.json()["free"]["active"] is True
        free = (await c.get("/api/rates?plan=free")).json()
        prem = (await c.get("/api/rates?plan=premium")).json()
        assert free["overall_status"] == "FALLBACK_ESTIMATED"
        assert free["fallback"]["reason"] == "HTTP 429 (simulated)"
        assert prem["overall_status"] == "LIVE_FROM_PROVIDER" and prem["simulation_active"] is False

        await c.post("/api/demo/premium/start")
        clock.t += 30  # stage index 3 -> LAST_KNOWN_GOOD
        prem = (await c.get("/api/rates?plan=premium")).json()
        assert prem["overall_status"] == "STALE"
        assert prem["premium_hierarchy"]["active_stage"] == "LAST_KNOWN_GOOD"

        await c.post("/api/demo/free/stop")
        status = (await c.get("/api/demo/status")).json()
        assert status["free"]["recovery"]["state"] == "RECOVERED"
        assert status["premium"]["active"] is True

        metrics = (await c.get("/api/metrics")).json()
        assert metrics["simulated"]["free"]["simulated_failures"] == 1
        assert metrics["usage"]["requests_this_month"] == 3  # simulations never count
        assert (await c.get("/health")).json()["redis"] == "ok"
    assert route.call_count == calls_before  # no provider calls from API/demo endpoints


def test_interval_picker_open_closed_and_budget_stretch():
    from datetime import datetime, timezone

    from app.collector.schedule import compute_schedule

    s = Settings(_env_file=None)
    sunday_noon = datetime(2026, 11, 1, 12, tzinfo=timezone.utc).timestamp()
    sunday_late = datetime(2026, 11, 1, 22, 30, tzinfo=timezone.utc).timestamp()
    closed = compute_schedule(sunday_noon, s, 0)
    opened = compute_schedule(sunday_late, s, 0)
    assert (closed["market_session"], closed["current_interval_seconds"], closed["budget_adjusted"]) == ("CLOSED", 900, False)
    assert (opened["market_session"], opened["current_interval_seconds"]) == ("OPEN", 600)
    # 4,990 of 5,000 used: 10 calls * 0.9 left for ~29 days -> stretched far beyond 600 s
    stretched = compute_schedule(sunday_late, s, 4990)
    assert stretched["budget_adjusted"] is True and stretched["current_interval_seconds"] > 600
    assert stretched["current_interval_seconds"] == stretched["budget_interval_seconds"]


@respx.mock
async def test_history_endpoint_shape(env):
    app, svc, clock = env
    respx.get(f"{BASE_URL}/latest/USD").mock(return_value=httpx.Response(200, json=SAMPLE))
    for _ in range(2):
        clock.t += 900
        await svc.collector.run_once()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        body = (await c.get("/api/history?pair=INR")).json()
        assert (await c.get("/api/history?pair=XYZ")).status_code == 400
    assert body["pair"] == "INR" and body["base"] == "USD" and body["window_size"] == 15
    assert len(body["observations"]) == 2
    first = body["observations"][0]
    assert set(first) == {"rate", "ewma", "provider_timestamp", "retrieved_at", "provider_source"}
    assert first["ewma"] == first["rate"] == 94.955 and first["provider_source"] == "ecb_daily"
    assert body["latest_ewma"] == pytest.approx(94.955)
