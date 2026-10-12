from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
DEFAULT_DB = BACKEND_ROOT / "data" / "blackout.db"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(BACKEND_ROOT / ".env", REPO_ROOT / ".env"),
        extra="ignore",
    )

    app_name: str = "Blackout"
    log_level: str = "INFO"
    database_url: str = ""
    cors_origins: str = "http://localhost:5173,http://localhost:8080"
    cache_ttl_seconds: int = 45
    metadata_ttl_seconds: int = 600
    request_timeout_seconds: float = 20
    rate_limit_per_minute: int = 30
    min_position_usd: float = 1
    enabled_chains: str = "ethereum,arbitrum,base,optimism"
    eth_rpc_url: str = ""
    arbitrum_rpc_url: str = ""
    base_rpc_url: str = ""
    optimism_rpc_url: str = ""
    coingecko_api_key: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def enabled_chain_list(self) -> list[str]:
        return [item.strip().lower() for item in self.enabled_chains.split(",") if item.strip()]

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return "sqlite:///" + DEFAULT_DB.as_posix()

    @property
    def min_position_value(self) -> Decimal:
        return Decimal(str(self.min_position_usd))

    def rpc_overrides(self, chain_key: str) -> list[str]:
        field = {
            "ethereum": self.eth_rpc_url,
            "arbitrum": self.arbitrum_rpc_url,
            "base": self.base_rpc_url,
            "optimism": self.optimism_rpc_url,
        }.get(chain_key, "")
        return [item.strip() for item in field.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
