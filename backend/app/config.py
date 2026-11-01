"""Application settings, loaded from environment variables (and an optional .env file)."""
from functools import lru_cache
from typing import Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_CURRENCY = "USD"
QUOTE_CURRENCIES = ("INR", "EUR", "GBP", "JPY")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Infrastructure
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    log_level: str = "INFO"

    # Provider
    provider_name: str = "exchangerate.dev"
    provider_base_url: str = "https://api.exchangerate.dev/v1"
    provider_api_key: str = ""  # optional; sent as "Authorization: Bearer <key>" only when set
    provider_timeout_seconds: float = 10.0
    provider_max_retries: int = 2
    provider_backoff_seconds: float = 1.0
    provider_monthly_limit: int = 5000
    provider_per_minute_limit: Optional[int] = 10
    provider_docs_url: str = "https://exchangerate.dev/free-plan-limits"
    provider_attribution_url: str = "https://exchangerate.dev"

    # Collector
    trading_interval_seconds: int = 600  # FX market open (Sun 22:00 -> Fri 22:00 UTC)
    non_trading_interval_seconds: int = 900  # weekend
    budget_safety: float = 0.9
    # Legacy alias: if explicitly set, overrides BOTH trading and non-trading intervals.
    collection_interval_seconds: Optional[int] = None
    collector_enabled: bool = True
    collector_lock_ttl_seconds: int = 120
    internal_per_minute_limit: int = 10

    # Tier refresh policy
    free_update_every_n: int = 5
    premium_update_every_n: int = 1

    # Sliding window / fallback
    window_size: int = 15
    window_ttl_seconds: int = 7 * 24 * 3600
    ewma_alpha: float = 0.4
    ewma_min_observations: int = 3
    max_data_age_seconds: int = 21600

    # Demo
    demo_mode: bool = False
    demo_stage_seconds: int = 8
    demo_duration_seconds: int = 120
    demo_recovery_seconds: int = 60

    @field_validator("provider_per_minute_limit", "collection_interval_seconds", mode="before")
    @classmethod
    def _empty_to_none(cls, v):
        if v in ("", "none", "None", "null"):
            return None
        return v

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
