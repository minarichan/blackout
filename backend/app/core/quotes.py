"""A read-only quote for one repay. Nothing here is signed or broadcast."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_UP

from app.adapters.codec import checksum, encode_call
from app.models.position import Position
from app.models.risk import ActionQuote, SuggestedAction
from app.registry import CHAINS

ZERO = Decimal("0")
QUOTE_TTL_SECONDS = 90
WEI = Decimal(10) ** 18


def assemble_quote(
    action: SuggestedAction,
    *,
    now: datetime,
    balance: Decimal | None,
    allowance: Decimal | None = None,
    gas_units: int | None = None,
    gas_price_wei: int | None = None,
    native_price_usd: Decimal | None = None,
    approval_gas_units: int | None = None,
    demo: bool = False,
    readable: bool = True,
) -> ActionQuote:
    """Turn a balance and a gas reading into a quote.

    A direct repay of the debt asset has no swap, so slippage is zero. If the
    wallet cannot cover the repay, gas is left unread and the quote stops.
    """
    expires = _expires(now)
    if not readable or balance is None:
        return ActionQuote(
            status="unavailable",
            slippage_bps=0,
            health_after=action.health_after,
            expires_at=expires,
            note="The wallet balance could not be read, so the quote stops. Nothing is sent.",
        )

    shortfall = action.amount - balance
    if shortfall > ZERO:
        note = (
            f"The demo book is not a wallet, so it holds no {action.asset} to repay. The quote stops here. Nothing is sent."
            if demo
            else f"The wallet holds less {action.asset} than this repay needs. The quote stops here. Nothing is sent."
        )
        return ActionQuote(
            status="short",
            slippage_bps=0,
            wallet_balance=balance,
            shortfall=shortfall,
            health_after=action.health_after,
            expires_at=expires,
            note=note,
        )

    if allowance is not None and allowance < action.amount:
        gas_native, gas_usd = _gas_cost(approval_gas_units, gas_price_wei, native_price_usd)
        return ActionQuote(
            status="approval",
            slippage_bps=0,
            wallet_balance=balance,
            shortfall=ZERO,
            gas_units=approval_gas_units,
            gas_native=gas_native,
            gas_usd=gas_usd,
            health_after=action.health_after,
            expires_at=expires,
            note="The wallet holds the asset, but the pool cannot pull it yet. Approval gas is quoted and the repay is not. Nothing is sent.",
        )

    if not gas_units or not gas_price_wei:
        return ActionQuote(
            status="unavailable",
            slippage_bps=0,
            wallet_balance=balance,
            shortfall=ZERO,
            health_after=action.health_after,
            expires_at=expires,
            note="Gas for the repay could not be estimated, so the quote stops. Nothing is sent.",
        )

    gas_native, gas_usd = _gas_cost(gas_units, gas_price_wei, native_price_usd)
    return ActionQuote(
        status="ready",
        slippage_bps=0,
        wallet_balance=balance,
        shortfall=ZERO,
        gas_units=gas_units,
        gas_native=gas_native,
        gas_usd=gas_usd,
        health_after=action.health_after,
        expires_at=expires,
        note="Direct repay of the debt asset. Slippage is zero because there is no swap. Nothing is sent.",
    )


def token_raw(amount: Decimal, decimals: int) -> int:
    scale = Decimal(10) ** decimals
    return int((amount * scale).to_integral_value(rounding=ROUND_UP))


def token_amount(raw: int, decimals: int) -> Decimal:
    return Decimal(raw) / (Decimal(10) ** decimals)


def token_decimals(position: Position) -> int:
    raw = position.metadata.get("decimals")
    if raw is not None and str(raw).isdigit():
        return int(raw)
    if position.asset in {"USDC", "USDT", "USDC.e", "USDbC", "USDS"}:
        return 6
    if position.asset in {"WBTC", "cbBTC"}:
        return 8
    return 18


def interest_mode(position: Position) -> int:
    variable = Decimal(str(position.metadata.get("variable_debt") or "0"))
    stable = Decimal(str(position.metadata.get("stable_debt") or "0"))
    if variable <= ZERO and stable > ZERO:
        return 1
    return 2


def repay_spender(position: Position) -> str | None:
    chain = CHAINS.get(position.chain)
    if chain is None:
        return None
    if position.protocol == "aave-v3":
        return checksum(chain.aave.pool)
    if position.protocol == "compound-v3":
        market = next((item for item in chain.compound if item.market_id == position.market), None)
        return None if market is None else checksum(market.comet)
    return None


def repay_call(position: Position, raw_amount: int, user: str) -> tuple[str, bytes] | None:
    spender = repay_spender(position)
    if spender is None:
        return None
    wallet = checksum(user)
    asset = checksum(position.asset_address)
    if position.protocol == "aave-v3":
        data = encode_call(
            "repay(address,uint256,uint256,address)",
            ["address", "uint256", "uint256", "address"],
            [asset, raw_amount, interest_mode(position), wallet],
        )
        return spender, data
    if position.protocol == "compound-v3":
        data = encode_call("supply(address,uint256)", ["address", "uint256"], [asset, raw_amount])
        return spender, data
    return None


def approve_call(position: Position, raw_amount: int) -> tuple[str, bytes] | None:
    spender = repay_spender(position)
    if spender is None:
        return None
    data = encode_call("approve(address,uint256)", ["address", "uint256"], [spender, raw_amount])
    return checksum(position.asset_address), data


def native_price(positions: list[Position]) -> Decimal | None:
    for position in positions:
        if position.asset in {"ETH", "WETH"} and position.price_usd > ZERO:
            return position.price_usd
    return None


def _expires(now: datetime) -> str:
    moment = now if now.tzinfo else now.replace(tzinfo=timezone.utc)
    return (moment + timedelta(seconds=QUOTE_TTL_SECONDS)).isoformat()


def _gas_cost(
    units: int | None,
    gas_price_wei: int | None,
    native_price_usd: Decimal | None,
) -> tuple[Decimal | None, Decimal | None]:
    if not units or not gas_price_wei:
        return None, None
    native = Decimal(units * gas_price_wei) / WEI
    usd = None if native_price_usd is None else native * native_price_usd
    return native, usd
