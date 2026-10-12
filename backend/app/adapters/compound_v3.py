from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from decimal import Decimal

from app.adapters.base import AdapterResult
from app.adapters.codec import checksum, decode_address, decode_symbol, decode_types, encode_call
from app.adapters.rpc import ChainRpc, RpcError
from app.models.position import Position
from app.registry import PROTOCOL_NAMES, ChainConfig, CompoundMarket

logger = logging.getLogger("blackout.compound")

ZERO = Decimal("0")
PRICE_SCALE = Decimal(10) ** 8
FACTOR_SCALE = Decimal(10) ** 18


def quote(raw_balance: int, raw_price: int, scale: int) -> tuple[Decimal, Decimal, Decimal]:
    if scale <= 0:
        return ZERO, ZERO, ZERO
    amount = Decimal(raw_balance) / Decimal(scale)
    price = Decimal(raw_price) / PRICE_SCALE
    return amount, price, amount * price


def _in_asset(assets_in: int, offset: int) -> bool:
    return (assets_in & (1 << offset)) != 0


@dataclass
class CollateralInfo:
    offset: int
    asset: str
    price_feed: str
    scale: int
    borrow_factor: Decimal
    liquidate_factor: Decimal
    symbol: str


@dataclass
class MarketMeta:
    market: CompoundMarket
    base_token: str
    base_symbol: str
    base_scale: int
    base_feed: str
    collaterals: list[CollateralInfo]


class CompoundV3Adapter:
    protocol = "compound-v3"

    def __init__(self, rpcs: dict[str, ChainRpc], metadata_ttl: int):
        self.rpcs = rpcs
        self.metadata_ttl = metadata_ttl
        self._meta: dict[str, tuple[float, MarketMeta]] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    async def fetch(self, chain: ChainConfig, user: str) -> AdapterResult:
        started = time.perf_counter()
        rpc = self.rpcs[chain.key]
        warnings: list[str] = []
        positions: list[Position] = []
        try:
            basics, scan_warnings = await self._basics(rpc, chain, user)
            warnings.extend(scan_warnings)
        except Exception as exc:
            logger.exception("compound scan failed on %s", chain.key)
            return AdapterResult(
                chain=chain.key,
                protocol=self.protocol,
                ok=False,
                error=_brief(exc),
                elapsed_ms=_elapsed(started),
            )

        for market, principal, assets_in in basics:
            if principal == 0 and assets_in == 0:
                continue
            try:
                meta = await self._market_meta(rpc, market)
                positions.extend(await self._positions(rpc, chain, user, meta, principal, assets_in))
            except Exception as exc:
                logger.warning("compound %s %s failed: %s", chain.key, market.name, exc)
                warnings.append(f"{market.name}: {_brief(exc)}")

        return AdapterResult(
            chain=chain.key,
            protocol=self.protocol,
            positions=positions,
            ok=True,
            warning="; ".join(warnings) or None,
            elapsed_ms=_elapsed(started),
        )

    async def _basics(
        self,
        rpc: ChainRpc,
        chain: ChainConfig,
        user: str,
    ) -> tuple[list[tuple[CompoundMarket, int, int]], list[str]]:
        calls = [
            (market.comet, encode_call("userBasic(address)", ["address"], [user]))
            for market in chain.compound
        ]
        rows = await rpc.multicall(calls, chunk=8)
        if rows and not any(ok and raw for ok, raw in rows):
            raise RpcError("Compound accounts unreadable")
        found: list[tuple[CompoundMarket, int, int]] = []
        warnings: list[str] = []
        for market, (ok, raw) in zip(chain.compound, rows, strict=True):
            if not ok or not raw:
                warnings.append(f"{market.name} account unreadable")
                continue
            principal, _index, _accrued, assets_in, _reserved = decode_types(
                ["int104", "uint64", "uint64", "uint16", "uint8"],
                raw,
            )
            found.append((market, int(principal), int(assets_in)))
        return found, warnings

    async def _market_meta(self, rpc: ChainRpc, market: CompoundMarket) -> MarketMeta:
        key = market.comet.lower()
        cached = self._meta.get(key)
        now = time.monotonic()
        if cached and cached[0] > now:
            return cached[1]
        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            cached = self._meta.get(key)
            now = time.monotonic()
            if cached and cached[0] > now:
                return cached[1]
            header_calls = [
                (market.comet, encode_call("baseToken()")),
                (market.comet, encode_call("baseScale()")),
                (market.comet, encode_call("baseTokenPriceFeed()")),
                (market.comet, encode_call("numAssets()")),
            ]
            header = await rpc.multicall(header_calls, chunk=4)
            if not all(ok and raw for ok, raw in header):
                raise RpcError(f"{market.name} market metadata unavailable")
            base_token = decode_address(header[0][1])
            base_scale = int(decode_types(["uint64"], header[1][1])[0])
            base_feed = decode_address(header[2][1])
            count = int(decode_types(["uint8"], header[3][1])[0])
            info_calls = [
                (market.comet, encode_call("getAssetInfo(uint8)", ["uint8"], [index]))
                for index in range(count)
            ]
            info_rows = await rpc.multicall(info_calls, chunk=8)
            collaterals: list[CollateralInfo] = []
            for ok, raw in info_rows:
                if not ok or not raw:
                    continue
                offset, asset, feed, scale, borrow_cf, liquidate_cf, _liq_factor, _cap = decode_types(
                    ["uint8", "address", "address", "uint64", "uint64", "uint64", "uint64", "uint128"],
                    raw,
                )
                collaterals.append(
                    CollateralInfo(
                        offset=int(offset),
                        asset=checksum(asset),
                        price_feed=checksum(feed),
                        scale=int(scale),
                        borrow_factor=Decimal(int(borrow_cf)) / FACTOR_SCALE,
                        liquidate_factor=Decimal(int(liquidate_cf)) / FACTOR_SCALE,
                        symbol="UNKNOWN",
                    )
                )
            symbol_calls = [(base_token, encode_call("symbol()"))]
            symbol_calls.extend((item.asset, encode_call("symbol()")) for item in collaterals)
            symbol_rows = await rpc.multicall(symbol_calls, chunk=16)
            base_symbol = decode_symbol(symbol_rows[0][1]) if symbol_rows[0][0] else market.name
            for item, (ok, raw) in zip(collaterals, symbol_rows[1:], strict=True):
                if ok and raw:
                    item.symbol = decode_symbol(raw)
            meta = MarketMeta(
                market=market,
                base_token=base_token,
                base_symbol=base_symbol or market.name,
                base_scale=base_scale,
                base_feed=base_feed,
                collaterals=collaterals,
            )
            self._meta[key] = (now + self.metadata_ttl, meta)
            return meta

    async def _positions(
        self,
        rpc: ChainRpc,
        chain: ChainConfig,
        user: str,
        meta: MarketMeta,
        principal: int,
        assets_in: int,
    ) -> list[Position]:
        held = [item for item in meta.collaterals if _in_asset(assets_in, item.offset)]
        calls: list[tuple[str, bytes]] = []
        kinds: list[tuple[str, CollateralInfo | None]] = []
        if principal > 0:
            calls.append((meta.market.comet, encode_call("balanceOf(address)", ["address"], [user])))
            kinds.append(("supply", None))
        elif principal < 0:
            calls.append((meta.market.comet, encode_call("borrowBalanceOf(address)", ["address"], [user])))
            kinds.append(("borrow", None))
        calls.append((meta.market.comet, encode_call("getPrice(address)", ["address"], [meta.base_feed])))
        kinds.append(("base_price", None))
        for item in held:
            calls.append(
                (
                    meta.market.comet,
                    encode_call("userCollateral(address,address)", ["address", "address"], [user, item.asset]),
                )
            )
            kinds.append(("collateral", item))
            calls.append((meta.market.comet, encode_call("getPrice(address)", ["address"], [item.price_feed])))
            kinds.append(("collateral_price", item))

        rows = await rpc.multicall(calls, chunk=12)
        base_balance = 0
        base_price = 0
        collateral_balance: dict[str, int] = {}
        collateral_price: dict[str, int] = {}
        for (kind, item), (ok, raw) in zip(kinds, rows, strict=True):
            if kind in {"supply", "borrow", "collateral"} and (not ok or not raw):
                raise RpcError(f"{meta.market.name} balance unreadable")
            if not ok or not raw:
                continue
            if kind in {"supply", "borrow"}:
                base_balance = int(decode_types(["uint256"], raw)[0])
            elif kind == "base_price":
                base_price = int(decode_types(["uint256"], raw)[0])
            elif kind == "collateral" and item is not None:
                balance, _reserved = decode_types(["uint128", "uint128"], raw)
                collateral_balance[item.asset] = int(balance)
            elif kind == "collateral_price" and item is not None:
                collateral_price[item.asset] = int(decode_types(["uint256"], raw)[0])

        positions: list[Position] = []
        if base_balance > 0:
            amount, price, value = quote(base_balance, base_price, meta.base_scale)
            side = "supply" if principal > 0 else "borrow"
            positions.append(
                self._make(
                    user=user,
                    chain=chain.key,
                    meta=meta,
                    side=side,
                    asset=meta.base_symbol,
                    asset_address=meta.base_token,
                    amount=amount,
                    price=price,
                    value=value,
                    collateral=False,
                    ltv=None,
                    threshold=None,
                )
            )
        for item in held:
            raw_balance = collateral_balance.get(item.asset, 0)
            if raw_balance <= 0:
                continue
            amount, price, value = quote(raw_balance, collateral_price.get(item.asset, 0), item.scale)
            collateral = item.liquidate_factor > ZERO
            positions.append(
                self._make(
                    user=user,
                    chain=chain.key,
                    meta=meta,
                    side="supply",
                    asset=item.symbol,
                    asset_address=item.asset,
                    amount=amount,
                    price=price,
                    value=value,
                    collateral=collateral,
                    ltv=item.borrow_factor if collateral else None,
                    threshold=item.liquidate_factor if collateral else None,
                )
            )
        return positions

    def _make(
        self,
        *,
        user: str,
        chain: str,
        meta: MarketMeta,
        side: str,
        asset: str,
        asset_address: str,
        amount: Decimal,
        price: Decimal,
        value: Decimal,
        collateral: bool,
        ltv: Decimal | None,
        threshold: Decimal | None,
    ) -> Position:
        market_id = meta.market.market_id
        return Position(
            id=f"{chain}:compound-v3:{market_id}:{side}:{asset_address.lower()}",
            user_address=user,
            chain=chain,
            protocol=self.protocol,
            protocol_name=PROTOCOL_NAMES[self.protocol],
            market=market_id,
            market_name=f"Compound v3 {meta.market.name}",
            account_key=f"{chain}:compound-v3:{market_id}",
            type=side,  # type: ignore[arg-type]
            asset=asset,
            asset_address=checksum(asset_address),
            amount=amount,
            value_usd=value,
            price_usd=price,
            collateral_factor=ltv,
            liquidation_threshold=threshold,
            usage_as_collateral=collateral,
            price_source="compound_oracle",
            metadata={},
        )


def _elapsed(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


def _brief(exc: Exception) -> str:
    text = str(exc).splitlines()[0].strip()
    return text[:180] or exc.__class__.__name__
