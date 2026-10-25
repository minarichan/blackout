from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.position import Position


class Slice(BaseModel):
    key: str
    value_usd: Decimal
    share: Decimal


class Concentration(BaseModel):
    collateral_by_asset: list[Slice]
    collateral_by_protocol: list[Slice]
    collateral_by_chain: list[Slice]
    collateral_by_factor: list[Slice]
    debt_by_asset: list[Slice]
    debt_by_protocol: list[Slice]
    debt_by_chain: list[Slice]
    debt_by_factor: list[Slice]
    collateral_hhi: Decimal = Decimal("0")
    debt_hhi: Decimal = Decimal("0")
    collateral_top_key: str = ""
    collateral_top_share: Decimal = Decimal("0")
    debt_top_key: str = ""
    debt_top_share: Decimal = Decimal("0")


class AccountRisk(BaseModel):
    account_key: str
    chain: str
    protocol: str
    protocol_name: str
    market: str
    market_name: str
    collateral_usd: Decimal
    supplied_usd: Decimal
    debt_usd: Decimal
    weighted_collateral_usd: Decimal
    health_factor: Decimal | None
    computed_health_factor: Decimal | None
    protocol_health_factor: Decimal | None
    protocol_liquidation_threshold: Decimal | None = None
    collateral_drawdown_pct: Decimal | None
    debt_increase_pct: Decimal | None
    primary_risk: str
    primary_distance_pct: Decimal | None
    liquidatable: bool
    collateral_assets: list[str] = Field(default_factory=list)
    debt_assets: list[str] = Field(default_factory=list)


class StressAccount(BaseModel):
    account_key: str
    chain: str
    protocol_name: str
    market_name: str
    health_factor: Decimal | None
    liquidatable: bool


class StressScenario(BaseModel):
    id: str
    label: str
    description: str
    portfolio_health_factor: Decimal | None
    worst_health_factor: Decimal | None
    health_factor_delta: Decimal | None
    any_liquidatable: bool
    accounts: list[StressAccount]


class ActionQuote(BaseModel):
    status: str
    slippage_bps: int
    wallet_balance: Decimal | None = None
    shortfall: Decimal | None = None
    gas_units: int | None = None
    gas_native: Decimal | None = None
    gas_usd: Decimal | None = None
    health_after: Decimal | None = None
    expires_at: str
    note: str


class SuggestedAction(BaseModel):
    kind: str
    account_key: str
    chain: str
    protocol_name: str
    market_name: str
    asset: str
    amount: Decimal
    amount_usd: Decimal
    target_health: Decimal
    health_before: Decimal
    health_after: Decimal | None
    worst_before: Decimal
    worst_after: Decimal | None
    worst_after_account_key: str | None = None
    worst_after_chain: str | None = None
    worst_after_market_name: str | None = None
    quote: ActionQuote | None = None


class Alert(BaseModel):
    id: str
    severity: str
    code: str
    title: str
    detail: str
    chain: str | None = None
    protocol: str | None = None
    asset: str | None = None
    account_key: str | None = None


class Analysis(BaseModel):
    positions: list[Position]
    accounts: list[AccountRisk]
    concentration: Concentration
    stress: list[StressScenario]
    total_supplied_usd: Decimal
    total_collateral_usd: Decimal
    total_debt_usd: Decimal
    portfolio_health_factor: Decimal | None
    worst_health_factor: Decimal | None
    worst_account_key: str | None
