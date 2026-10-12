from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field


class Position(BaseModel):
    id: str
    user_address: str
    chain: str
    protocol: str
    protocol_name: str
    market: str
    market_name: str
    account_key: str
    type: Literal["supply", "borrow"]
    asset: str
    asset_address: str
    amount: Decimal
    value_usd: Decimal
    price_usd: Decimal
    collateral_factor: Decimal | None = None
    liquidation_threshold: Decimal | None = None
    usage_as_collateral: bool = False
    health_factor: Decimal | None = None
    liquidation_price: Decimal | None = None
    distance_to_liquidation_pct: Decimal | None = None
    distance_to_liquidation_usd: Decimal | None = None
    entry_price: Decimal | None = None
    price_source: str = "protocol_oracle"
    metadata: dict[str, Any] = Field(default_factory=dict)
