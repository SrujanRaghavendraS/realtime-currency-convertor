"""Simulated failing provider used by the free-plan demo. Never performs HTTP, never touches quota."""
from app.models.domain import FailureType, ProviderResult

SIMULATED_REASONS = {
    FailureType.HTTP_429: "HTTP 429 (simulated)",
    FailureType.OUTAGE: "Provider outage (simulated)",
    FailureType.TIMEOUT: "Timeout (simulated)",
}

SIMULATED_EVENTS = {
    FailureType.HTTP_429: "Simulated public API returned HTTP 429",
    FailureType.OUTAGE: "Simulated public API outage (HTTP 503)",
    FailureType.TIMEOUT: "Simulated public API request timed out",
}


def simulated_failure(failure_type: FailureType) -> ProviderResult:
    return ProviderResult(
        ok=False,
        error_type=failure_type.value,
        error_message=SIMULATED_REASONS[failure_type],
        simulated=True,
        attempts=[],  # no real requests -> nothing counted against quota
    )
