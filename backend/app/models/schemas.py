from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SliceOut(BaseModel):
    key: str
    value_usd: float
    share: float


class ConcentrationOut(BaseModel):
    collateral_by_asset: list[SliceOut]
    collateral_by_protocol: list[SliceOut]
    collateral_by_chain: list[SliceOut]
    collateral_by_factor: list[SliceOut]
    debt_by_asset: list[SliceOut]
    debt_by_protocol: list[SliceOut]
    debt_by_chain: list[SliceOut]
    debt_by_factor: list[SliceOut]


class PositionOut(BaseModel):
    id: str
    user_address: str
    chain: str
    chain_name: str
    protocol: str
    protocol_name: str
    market: str
    market_name: str
    account_key: str
    type: str
    asset: str
    asset_address: str
    amount: float
    value_usd: float
    price_usd: float
    collateral_factor: float | None = None
    liquidation_threshold: float | None = None
    usage_as_collateral: bool = False
    health_factor: float | None = None
    liquidation_price: float | None = None
    distance_to_liquidation_pct: float | None = None
    distance_to_liquidation_usd: float | None = None
    entry_price: float | None = None
    price_source: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class AccountOut(BaseModel):
    account_key: str
    chain: str
    chain_name: str
    protocol: str
    protocol_name: str
    market: str
    market_name: str
    collateral_usd: float
    supplied_usd: float
    debt_usd: float
    weighted_collateral_usd: float
    health_factor: float | None = None
    computed_health_factor: float | None = None
    protocol_health_factor: float | None = None
    protocol_liquidation_threshold: float | None = None
    collateral_drawdown_pct: float | None = None
    debt_increase_pct: float | None = None
    primary_risk: str
    primary_distance_pct: float | None = None
    liquidatable: bool
    collateral_assets: list[str]
    debt_assets: list[str]


class StressAccountOut(BaseModel):
    account_key: str
    chain: str
    protocol_name: str
    market_name: str
    health_factor: float | None = None
    liquidatable: bool


class StressOut(BaseModel):
    id: str
    label: str
    description: str
    portfolio_health_factor: float | None = None
    worst_health_factor: float | None = None
    health_factor_delta: float | None = None
    any_liquidatable: bool
    accounts: list[StressAccountOut]


class AlertOut(BaseModel):
    id: str
    severity: str
    code: str
    title: str
    detail: str
    chain: str | None = None
    protocol: str | None = None
    asset: str | None = None
    account_key: str | None = None


class IngestionOut(BaseModel):
    chain: str
    protocol: str
    ok: bool
    error: str | None = None
    warning: str | None = None
    position_count: int
    elapsed_ms: int


class SummaryOut(BaseModel):
    total_supplied_usd: float
    total_collateral_usd: float
    total_debt_usd: float
    net_usd: float
    portfolio_health_factor: float | None = None
    worst_health_factor: float | None = None
    worst_account_key: str | None = None
    primary_risk: str
    primary_distance_pct: float | None = None
    collateral_drawdown_pct: float | None = None
    debt_increase_pct: float | None = None
    account_count: int
    position_count: int
    alert_count: int


class PortfolioOut(BaseModel):
    address: str
    demo: bool
    data_quality: str
    fetched_at: str
    elapsed_ms: int
    methodology: str
    summary: SummaryOut
    positions: list[PositionOut]
    accounts: list[AccountOut]
    concentration: ConcentrationOut
    stress: list[StressOut]
    alerts: list[AlertOut]
    ingestion: list[IngestionOut]


class SnapshotOut(BaseModel):
    timestamp: str
    total_collateral_usd: float
    total_debt_usd: float
    portfolio_health_factor: float | None = None
    worst_health_factor: float | None = None
    alert_count: int


class WatchIn(BaseModel):
    address: str
    label: str = ""


class WatchOut(BaseModel):
    address: str
    label: str
    created_at: str
