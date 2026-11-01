"""HTTP endpoints. None of these call the FX provider; they only read/write Redis."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request

from app.config import BASE_CURRENCY, QUOTE_CURRENCIES
from app.metrics.service import collector_health
from app.models.domain import DemoStartRequest, Plan, to_iso
from app.services.container import Services

router = APIRouter()


def get_services(request: Request) -> Services:
    return request.app.state.services


def require_demo(svc: Services = Depends(get_services)) -> Services:
    if not svc.settings.demo_mode:
        raise HTTPException(status_code=403, detail="Demo mode disabled")
    return svc


@router.get("/health")
async def health(svc: Services = Depends(get_services)):
    now = svc.clock()
    try:
        await svc.redis.ping()
        state = await svc.store.get_collector_state()
        redis_status, collector = "ok", collector_health(state, svc.settings, now)
    except Exception:
        redis_status, collector = "down", "DOWN"
    ok = redis_status == "ok" and collector in ("HEALTHY", "STARTING")
    return {"status": "ok" if ok else "degraded", "redis": redis_status, "collector": collector, "time": to_iso(now)}


@router.get("/api/rates")
async def get_rates(plan: Plan = Query(Plan.free), svc: Services = Depends(get_services)):
    return await svc.rates.build(plan.value, svc.clock())


@router.get("/api/metrics")
async def get_metrics(svc: Services = Depends(get_services)):
    return await svc.metrics.build(svc.clock())


@router.get("/api/history")
async def get_history(pair: str = Query(...), svc: Services = Depends(get_services)):
    """Sliding-window observations oldest -> newest, each with the running EWMA S(t)."""
    pair = pair.upper()
    if pair not in QUOTE_CURRENCIES:
        raise HTTPException(status_code=400, detail=f"Unsupported pair; use one of {', '.join(QUOTE_CURRENCIES)}")
    s = svc.settings
    window = await svc.store.get_window(pair)
    points, running = [], None
    for obs in window:
        rate = float(obs["rate"])
        running = rate if running is None else s.ewma_alpha * rate + (1 - s.ewma_alpha) * running
        points.append({
            "rate": rate,
            "ewma": running,
            "provider_timestamp": obs.get("provider_timestamp"),
            "retrieved_at": obs.get("retrieved_at"),
            "provider_source": obs.get("provider_source"),
        })
    return {
        "pair": pair,
        "base": BASE_CURRENCY,
        "window_size": s.window_size,
        "alpha": s.ewma_alpha,
        "ewma_min_observations": s.ewma_min_observations,
        "observations": points,
        "latest_ewma": running,
    }


async def demo_status(svc: Services) -> dict:
    now = svc.clock()
    sims = svc.sims
    free_sim = await sims.get("free")
    prem_sim = await sims.get("premium")
    free_rates = await svc.rates.build("free", now)
    prem_rates = await svc.rates.build("premium", now)

    def common(sim: Optional[dict]) -> dict:
        active = sims.is_active(sim, now)
        return {
            "active": active,
            "started_at": to_iso(sim["started_at"]) if sim else None,
            "expires_at": to_iso(sim["expires_at"]) if sim else None,
            "seconds_remaining": max(0, int(sim["expires_at"] - now)) if active else 0,
        }

    return {
        "demo_mode_enabled": svc.settings.demo_mode,
        "free": {
            **common(free_sim),
            "failure_type": free_sim.get("failure_type") if free_sim else None,
            "fallback_method": free_rates["fallback"]["method"],
            "resulting_status": free_rates["overall_status"],
            "recovery": sims.recovery(free_sim, now),
            "events": sims.events("free", free_sim, now),
        },
        "premium": {
            **common(prem_sim),
            "current_stage": prem_rates["premium_hierarchy"]["active_stage"],
            "stages": prem_rates["premium_hierarchy"]["stages"],
            "resulting_status": prem_rates["overall_status"],
            "recovery": sims.recovery(prem_sim, now),
            "events": sims.events("premium", prem_sim, now),
        },
    }


@router.get("/api/demo/status")
async def get_demo_status(svc: Services = Depends(get_services)):
    return await demo_status(svc)


@router.post("/api/demo/free/start")
async def start_free(body: Optional[DemoStartRequest] = Body(default=None), svc: Services = Depends(require_demo)):
    req = body or DemoStartRequest()
    await svc.sims.start("free", svc.clock(), req.failure_type)
    return await demo_status(svc)


@router.post("/api/demo/free/stop")
async def stop_free(svc: Services = Depends(require_demo)):
    await svc.sims.stop("free", svc.clock())
    return await demo_status(svc)


@router.post("/api/demo/premium/start")
async def start_premium(svc: Services = Depends(require_demo)):
    await svc.sims.start("premium", svc.clock())
    return await demo_status(svc)


@router.post("/api/demo/premium/stop")
async def stop_premium(svc: Services = Depends(require_demo)):
    await svc.sims.stop("premium", svc.clock())
    return await demo_status(svc)
