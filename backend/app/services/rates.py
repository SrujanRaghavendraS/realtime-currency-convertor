"""Builds the /api/rates response for a plan from Redis state. Never calls the provider."""
from __future__ import annotations

from typing import Optional

from app.config import BASE_CURRENCY, QUOTE_CURRENCIES, Settings
from app.fallback.ewma import ewma
from app.collector.schedule import OPEN, fmt_minutes, load_schedule
from app.metrics.recorder import MetricsRecorder, iso_from_field
from app.models.domain import STATUS_SEVERITY, FailureType, RateStatus, parse_iso
from app.providers.simulated import simulated_failure
from app.services.simulation import PREMIUM_STAGES, SimulationService
from app.services.store import Store

STAGE_LABELS = {
    "PRIMARY_PREMIUM": "Primary premium provider",
    "SECONDARY_PREMIUM": "Secondary premium provider",
    "PUBLIC_API": "Public API (exchangerate.dev)",
    "LAST_KNOWN_GOOD": "Last-known-good rate",
}
NOT_CONFIGURED_NOTE = "Demo only - no premium provider integrated"

FALLBACK_METHOD_BY_STATUS = {
    RateStatus.FALLBACK_ESTIMATED: "EWMA",
    RateStatus.STALE: "LAST_KNOWN_GOOD",
    RateStatus.UNAVAILABLE: "UNAVAILABLE",
}


class RatesService:
    def __init__(self, store: Store, sims: SimulationService, settings: Settings, recorder: MetricsRecorder):
        self.store = store
        self.recorder = recorder
        self.sims = sims
        self.s = settings

    # ---- per-currency entries ------------------------------------------------
    def _entry(self, obs: Optional[dict], status: RateStatus, method: str, used: int,
               rate: Optional[float] = None) -> dict:
        if status == RateStatus.UNAVAILABLE or obs is None:
            return {
                "rate": None, "source": self.s.provider_name, "method": "NONE",
                "provider_timestamp": obs.get("provider_timestamp") if obs else None,
                "retrieved_at": obs.get("retrieved_at") if obs else None,
                "status": RateStatus.UNAVAILABLE.value, "is_estimated": False, "is_stale": True,
                "observations_used": 0,
            }
        return {
            "rate": obs["rate"] if rate is None else rate,
            "source": self.s.provider_name,
            "method": method,
            # never fabricated: timestamps of the latest valid observation used
            "provider_timestamp": obs.get("provider_timestamp"),
            "retrieved_at": obs.get("retrieved_at"),
            "status": status.value,
            "is_estimated": status == RateStatus.FALLBACK_ESTIMATED,
            "is_stale": status == RateStatus.STALE,
            "observations_used": used,
        }

    def _too_old(self, obs: Optional[dict], now: float) -> bool:
        # Max age is measured against OUR retrieval time (retrieved_at), not the provider's
        # effective_at: on weekends the ECB fix is ~2 days old, which is normal provider data.
        if not obs:
            return True
        retrieved = parse_iso(obs.get("retrieved_at"))
        return retrieved is None or now - retrieved > self.s.max_data_age_seconds

    async def _failing_entry(self, ccy: str, now: float) -> dict:
        window = await self.store.get_window(ccy)
        lkg = await self.store.get_lkg(ccy) or (window[-1] if window else None)
        if lkg is None or self._too_old(lkg, now):
            return self._entry(lkg, RateStatus.UNAVAILABLE, "NONE", 0)
        if len(window) >= self.s.ewma_min_observations:
            est = ewma([o["rate"] for o in window], self.s.ewma_alpha)
            return self._entry(window[-1], RateStatus.FALLBACK_ESTIMATED, "EWMA", len(window), rate=est)
        return self._entry(lkg, RateStatus.STALE, "LAST_KNOWN_GOOD", 1)

    async def _lkg_entry(self, ccy: str, now: float, status: RateStatus, method: str) -> dict:
        lkg = await self.store.get_lkg(ccy)
        if lkg is None or self._too_old(lkg, now):
            return self._entry(lkg, RateStatus.UNAVAILABLE, "NONE", 0)
        return self._entry(lkg, status, method, 1)

    # ---- main ------------------------------------------------------------------
    async def build(self, plan: str, now: float) -> dict:
        state = await self.store.get_collector_state()
        snapshot = await self.store.get_snapshot(plan)
        since_update = await self.store.get_since_update(plan)
        sim = await self.sims.get(plan)
        sim_active = self.sims.is_active(sim, now)
        successful_total = int(state.get("successful_collections_total") or 0)
        last_attempt_ok = state.get("last_attempt_ok")  # "1" | "0" | None (no attempt yet)

        failing = False
        reason: Optional[str] = None
        premium_stage_idx: Optional[int] = None

        if plan == "free" and sim_active:
            # Simulated provider result fed through the same fallback path; no HTTP, no quota.
            result = simulated_failure(FailureType(sim["failure_type"]))
            failing, reason = True, result.error_message
        elif plan == "premium" and sim_active:
            premium_stage_idx = self.sims.premium_stage_index(sim, now)
        elif last_attempt_ok == "0":
            failing, reason = True, state.get("last_failure_reason") or "Provider request failed"

        rates: dict[str, dict] = {}
        for ccy in QUOTE_CURRENCIES:
            if premium_stage_idx is not None:
                if premium_stage_idx < 3:
                    rates[ccy] = await self._lkg_entry(ccy, now, RateStatus.CACHED, "CACHE")
                else:
                    rates[ccy] = await self._lkg_entry(ccy, now, RateStatus.STALE, "LAST_KNOWN_GOOD")
            elif failing:
                rates[ccy] = await self._failing_entry(ccy, now)
            else:
                obs = (snapshot or {}).get("rates", {}).get(ccy)
                if obs is None or self._too_old(obs, now):
                    rates[ccy] = self._entry(obs, RateStatus.UNAVAILABLE, "NONE", 0)
                elif snapshot.get("success_seq") == successful_total:
                    rates[ccy] = self._entry(obs, RateStatus.LIVE_FROM_PROVIDER, "PROVIDER", 1)
                else:
                    rates[ccy] = self._entry(obs, RateStatus.CACHED, "CACHE", 1)

        overall = max((RateStatus(r["status"]) for r in rates.values()), key=STATUS_SEVERITY.get)

        if premium_stage_idx is not None:
            reason = PREMIUM_REASONS[premium_stage_idx]
        fallback_method = FALLBACK_METHOD_BY_STATUS.get(overall, "NONE")
        if premium_stage_idx is not None and premium_stage_idx < 3 and overall == RateStatus.CACHED:
            fallback_method = "NONE"
        fallback_active = fallback_method != "NONE" or failing

        every_n = self.s.free_update_every_n if plan == "free" else self.s.premium_update_every_n
        schedule = await load_schedule(self.store, self.recorder, self.s, now)
        return {
            "plan": plan,
            "base": BASE_CURRENCY,
            "provider": self.s.provider_name,
            "overall_status": overall.value,
            "message": self._message(plan, overall, reason, snapshot is None and successful_total == 0),
            "snapshot_updated_at": snapshot.get("updated_at") if snapshot else None,
            "last_successful_update": iso_from_field(state.get("last_success_at")),
            "refresh_policy": {
                "collection_interval_seconds": schedule["current_interval_seconds"],
                "update_every_n_successful_collections": every_n,
                "successful_collections_since_update": since_update,
                "description": self._policy_description(plan, every_n, schedule),
            },
            "rates": rates,
            "fallback": {
                "active": fallback_active,
                "method": fallback_method,
                "reason": reason if (fallback_active or premium_stage_idx is not None) else None,
            },
            "premium_hierarchy": self.hierarchy(premium_stage_idx, failing, overall) if plan == "premium" else None,
            "simulation_active": sim_active,
            "attribution": {"text": f"Rates by {self.s.provider_name}", "url": self.s.provider_attribution_url},
        }

    @staticmethod
    def _policy_description(plan: str, every_n: int, schedule: dict) -> str:
        span = fmt_minutes(every_n * schedule["current_interval_seconds"])
        when = "while market is open" if schedule["market_session"] == OPEN else "while market is closed"
        if every_n <= 1:
            return f"{plan.capitalize()} snapshot refreshes on every successful collection (~{span} {when})."
        return f"{plan.capitalize()} snapshot refreshes after every {every_n} successful collections (~{span} {when})."

    def _message(self, plan: str, overall: RateStatus, reason: Optional[str], never_collected: bool) -> str:
        p = self.s.provider_name
        why = f" ({reason})" if reason else ""
        if overall == RateStatus.LIVE_FROM_PROVIDER:
            return f"Rates are delayed public data from {p}."
        if overall == RateStatus.CACHED:
            if plan == "premium" and reason:
                return f"Premium providers unavailable{why}; serving the latest valid {p} observation."
            return f"Showing the {plan} plan snapshot from an earlier successful {p} update."
        if overall == RateStatus.FALLBACK_ESTIMATED:
            return f"The rate provider is currently unavailable{why}. Showing estimated rates based on recent observations."
        if overall == RateStatus.STALE:
            return f"The rate provider is currently unavailable{why}. Showing the last known good rates."
        if never_collected:
            return "No rates have been collected yet. Please check back shortly."
        return f"Rates are temporarily unavailable{why}. No sufficiently recent data to display."

    @staticmethod
    def hierarchy(stage_idx: Optional[int], failing: bool, overall: RateStatus) -> dict:
        def stage(key: str, state: str, note: Optional[str] = None) -> dict:
            return {"key": key, "label": STAGE_LABELS[key], "state": state, "note": note}

        if stage_idx is None:
            # Normal mode: premium providers are not configured; public API is the real source.
            if not failing:
                public, lkg, active = "ACTIVE", "STANDBY", "PUBLIC_API"
            else:
                public, active = "FAILED", "LAST_KNOWN_GOOD"
                lkg = "FAILED" if overall == RateStatus.UNAVAILABLE else "ACTIVE"
            return {"active_stage": active, "stages": [
                stage("PRIMARY_PREMIUM", "NOT_CONFIGURED", NOT_CONFIGURED_NOTE),
                stage("SECONDARY_PREMIUM", "NOT_CONFIGURED", NOT_CONFIGURED_NOTE),
                stage("PUBLIC_API", public),
                stage("LAST_KNOWN_GOOD", lkg),
            ]}

        sim_note = "Simulated failure"
        states = {
            0: ["SIMULATED_UNAVAILABLE", "CHECKING", "STANDBY", "STANDBY"],
            1: ["SIMULATED_UNAVAILABLE", "SIMULATED_UNAVAILABLE", "CHECKING", "STANDBY"],
            2: ["SIMULATED_UNAVAILABLE", "SIMULATED_UNAVAILABLE", "ACTIVE", "STANDBY"],
            3: ["SIMULATED_UNAVAILABLE", "SIMULATED_UNAVAILABLE", "SIMULATED_UNAVAILABLE", "ACTIVE"],
        }[stage_idx]
        if overall == RateStatus.UNAVAILABLE and stage_idx == 3:
            states[3] = "FAILED"
        return {"active_stage": PREMIUM_STAGES[stage_idx], "stages": [
            stage(key, st, sim_note if st == "SIMULATED_UNAVAILABLE" else None)
            for key, st in zip(PREMIUM_STAGES, states)
        ]}


PREMIUM_REASONS = (
    "Primary premium unavailable (simulated)",
    "Secondary premium unavailable (simulated)",
    "Premium providers unavailable (simulated)",
    "Public API unavailable (simulated)",
)
