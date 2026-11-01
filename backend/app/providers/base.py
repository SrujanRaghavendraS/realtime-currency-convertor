"""Provider interface."""
from typing import Protocol, Sequence

from app.models.domain import ProviderResult


class RateProvider(Protocol):
    name: str

    async def fetch_latest(self, base: str, symbols: Sequence[str]) -> ProviderResult:
        """Fetch latest rates for all symbols in ONE logical request (with limited retries)."""
        ...
