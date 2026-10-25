"""Read the wallet and simulate gas for one repay. No transaction is broadcast."""

from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal

from app.adapters.codec import checksum, decode_types, encode_call
from app.adapters.rpc import ChainRpc, RpcError
from app.core.quotes import (
    approve_call,
    assemble_quote,
    repay_call,
    repay_spender,
    token_amount,
    token_decimals,
    token_raw,
)
from app.models.position import Position
from app.models.risk import ActionQuote, SuggestedAction

logger = logging.getLogger("blackout.quote")


class RepayQuoter:
    def __init__(self, rpcs: dict[str, ChainRpc]):
        self.rpcs = rpcs

    async def quote(
        self,
        action: SuggestedAction,
        positions: list[Position],
        user: str,
        native_price_usd: Decimal | None,
        now: datetime,
    ) -> ActionQuote:
        position = _borrow(action, positions)
        rpc = self.rpcs.get(action.chain)
        if position is None or rpc is None:
            return assemble_quote(action, now=now, balance=None, readable=False)

        decimals = token_decimals(position)
        try:
            balance = await _erc20_amount(rpc, position.asset_address, "balanceOf(address)", [checksum(user)], decimals)
            spender = repay_spender(position)
            allowance = None
            if spender is not None:
                allowance = await _erc20_amount(
                    rpc,
                    position.asset_address,
                    "allowance(address,address)",
                    [checksum(user), spender],
                    decimals,
                )
        except RpcError:
            logger.warning("repay quote balance failed", exc_info=True)
            return assemble_quote(action, now=now, balance=None, readable=False)

        if balance < action.amount:
            return assemble_quote(action, now=now, balance=balance, allowance=allowance)

        raw = token_raw(action.amount, decimals)
        gas_price = await _optional(rpc.gas_price())
        approval_gas = None
        repay_gas = None
        if allowance is not None and allowance < action.amount:
            approval = approve_call(position, raw)
            if approval is not None:
                token, data = approval
                approval_gas = await _optional(rpc.estimate_gas({"from": checksum(user), "to": token, "data": data}))
        else:
            call = repay_call(position, raw, user)
            if call is not None:
                pool, data = call
                repay_gas = await _optional(rpc.estimate_gas({"from": checksum(user), "to": pool, "data": data}))

        return assemble_quote(
            action,
            now=now,
            balance=balance,
            allowance=allowance,
            gas_units=repay_gas,
            gas_price_wei=gas_price,
            native_price_usd=native_price_usd,
            approval_gas_units=approval_gas,
        )


def _borrow(action: SuggestedAction, positions: list[Position]) -> Position | None:
    matches = [
        position
        for position in positions
        if position.account_key == action.account_key and position.type == "borrow" and position.asset == action.asset
    ]
    if not matches:
        return None
    return max(matches, key=lambda position: position.value_usd)


async def _erc20_amount(rpc: ChainRpc, token: str, signature: str, args: list[str], decimals: int) -> Decimal:
    types = ["address"] * len(args)
    raw = await rpc.eth_call(token, encode_call(signature, types, args))
    amount = int(decode_types(["uint256"], raw)[0])
    return token_amount(amount, decimals)


async def _optional(awaitable) -> int | None:
    try:
        return await awaitable
    except RpcError:
        logger.warning("repay quote gas failed", exc_info=True)
        return None
