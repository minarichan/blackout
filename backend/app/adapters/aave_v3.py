from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from decimal import Decimal

from app.adapters.base import AdapterResult
from app.adapters.codec import checksum, decode_symbol, decode_types, encode_call
from app.adapters.rpc import ChainRpc, RpcError
from app.models.position import Position
from app.registry import PROTOCOL_NAMES, ChainConfig

logger = logging.getLogger("blackout.aave")

ZERO = Decimal("0")
BPS = Decimal("10000")
HF_SCALE = Decimal(10) ** 18
HF_SENTINEL = Decimal(10) ** 30
EMODE_SHIFT = 168


@dataclass
class ReserveState:
    address: str
    symbol: str
    decimals: int
    ltv: Decimal
    liquidation_threshold: Decimal
    reserve_collateral_enabled: bool
    emode_category: int
    supply_raw: int
    stable_debt_raw: int
    variable_debt_raw: int
    usage_as_collateral: bool
    price_raw: int


def build_aave_positions(
    *,
    user: str,
    chain: str,
    reserves: list[ReserveState],
    base_unit: int,
    protocol_health: Decimal | None,
    protocol_liquidation_threshold: Decimal | None,
    emode: int,
    emode_label: str,
    emode_ltv: Decimal | None,
    emode_liquidation_threshold: Decimal | None,
) -> list[Position]:
    unit = Decimal(base_unit if base_unit else 10**8)
    positions: list[Position] = []
    shared: dict[str, str] = {}
    if protocol_health is not None:
        shared["protocol_health_factor"] = format(protocol_health, "f")
    if protocol_liquidation_threshold is not None:
        shared["protocol_liquidation_threshold"] = format(protocol_liquidation_threshold, "f")
    if emode:
        shared["emode"] = str(emode)
        if emode_label:
            shared["emode_label"] = emode_label

    for reserve in reserves:
        scale = Decimal(10) ** reserve.decimals
        price = Decimal(reserve.price_raw) / unit if reserve.price_raw else ZERO
        ltv = reserve.ltv
        threshold = reserve.liquidation_threshold
        if (
            emode
            and reserve.emode_category == emode
            and emode_liquidation_threshold is not None
            and emode_liquidation_threshold > ZERO
        ):
            ltv = emode_ltv if emode_ltv is not None else ltv
            threshold = emode_liquidation_threshold

        if reserve.supply_raw > 0:
            amount = Decimal(reserve.supply_raw) / scale
            positions.append(
                _position(
                    user=user,
                    chain=chain,
                    reserve=reserve,
                    side="supply",
                    amount=amount,
                    price=price,
                    ltv=ltv,
                    threshold=threshold,
                    collateral=reserve.usage_as_collateral and threshold > ZERO,
                    metadata=shared,
                )
            )
        debt_raw = reserve.stable_debt_raw + reserve.variable_debt_raw
        if debt_raw > 0:
            amount = Decimal(debt_raw) / scale
            meta = dict(shared)
            if reserve.stable_debt_raw:
                meta["stable_debt"] = format(Decimal(reserve.stable_debt_raw) / scale, "f")
            if reserve.variable_debt_raw:
                meta["variable_debt"] = format(Decimal(reserve.variable_debt_raw) / scale, "f")
            positions.append(
                _position(
                    user=user,
                    chain=chain,
                    reserve=reserve,
                    side="borrow",
                    amount=amount,
                    price=price,
                    ltv=None,
                    threshold=None,
                    collateral=False,
                    metadata=meta,
                )
            )
    return positions


def _position(
    *,
    user: str,
    chain: str,
    reserve: ReserveState,
    side: str,
    amount: Decimal,
    price: Decimal,
    ltv: Decimal | None,
    threshold: Decimal | None,
    collateral: bool,
    metadata: dict,
) -> Position:
    return Position(
        id=f"{chain}:aave-v3:core:{side}:{reserve.address.lower()}",
        user_address=user,
        chain=chain,
        protocol="aave-v3",
        protocol_name=PROTOCOL_NAMES["aave-v3"],
        market="core",
        market_name="Aave v3",
        account_key=f"{chain}:aave-v3:core",
        type=side,  # type: ignore[arg-type]
        asset=reserve.symbol,
        asset_address=checksum(reserve.address),
        amount=amount,
        value_usd=amount * price,
        price_usd=price,
        collateral_factor=ltv if collateral else None,
        liquidation_threshold=threshold if collateral else None,
        usage_as_collateral=collateral,
        price_source="aave_oracle",
        metadata=dict(metadata),
    )


class AaveV3Adapter:
    protocol = "aave-v3"

    def __init__(self, rpcs: dict[str, ChainRpc], metadata_ttl: int):
        self.rpcs = rpcs
        self.metadata_ttl = metadata_ttl
        self._meta: dict[str, tuple[float, tuple[list[dict], int]]] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    async def fetch(self, chain: ChainConfig, user: str) -> AdapterResult:
        started = time.perf_counter()
        rpc = self.rpcs[chain.key]
        try:
            reserves, base_unit = await self._market(chain, rpc)
            account = await self._account(rpc, chain.aave.pool, user)
            if account["collateral"] == 0 and account["debt"] == 0:
                return self._ok(chain, started)
            emode, emode_ltv, emode_lt, emode_label = await self._emode(rpc, chain.aave.pool, user)
            states = await self._user_states(rpc, chain, reserves, user, emode)
            positions = build_aave_positions(
                user=user,
                chain=chain.key,
                reserves=states,
                base_unit=base_unit,
                protocol_health=account["health"],
                protocol_liquidation_threshold=account["liquidation_threshold"],
                emode=emode,
                emode_label=emode_label,
                emode_ltv=emode_ltv,
                emode_liquidation_threshold=emode_lt,
            )
            warning = _reconciliation_warning(account, positions, base_unit)
            return self._ok(chain, started, positions, warning)
        except Exception as exc:
            logger.exception("aave fetch failed on %s", chain.key)
            return AdapterResult(
                chain=chain.key,
                protocol=self.protocol,
                ok=False,
                error=_brief(exc),
                elapsed_ms=_elapsed(started),
            )

    async def _market(self, chain: ChainConfig, rpc: ChainRpc) -> tuple[list[dict], int]:
        cached = self._meta.get(chain.key)
        now = time.monotonic()
        if cached and cached[0] > now:
            return cached[1]
        lock = self._locks.setdefault(chain.key, asyncio.Lock())
        async with lock:
            cached = self._meta.get(chain.key)
            now = time.monotonic()
            if cached and cached[0] > now:
                return cached[1]
            listed = decode_types(["address[]"], await rpc.eth_call(chain.aave.pool, encode_call("getReservesList()")))[0]
            base_raw = await rpc.eth_call(chain.aave.oracle, encode_call("BASE_CURRENCY_UNIT()"))
            base_unit = int(decode_types(["uint256"], base_raw)[0])
            calls: list[tuple[str, bytes]] = []
            for asset in listed:
                calls.append((asset, encode_call("symbol()")))
                calls.append((chain.aave.data_provider, encode_call("getReserveConfigurationData(address)", ["address"], [asset])))
                calls.append((chain.aave.pool, encode_call("getConfiguration(address)", ["address"], [asset])))
            rows = await rpc.multicall(calls, chunk=18)
            reserves: list[dict] = []
            for index, asset in enumerate(listed):
                symbol_ok, symbol_raw = rows[index * 3]
                config_ok, config_raw = rows[index * 3 + 1]
                bitmap_ok, bitmap_raw = rows[index * 3 + 2]
                if not config_ok:
                    continue
                decimals, ltv, threshold, _bonus, _factor, can_collateral, _borrow, _stable, _active, _frozen = decode_types(
                    ["uint256", "uint256", "uint256", "uint256", "uint256", "bool", "bool", "bool", "bool", "bool"],
                    config_raw,
                )
                category = 0
                if bitmap_ok and bitmap_raw:
                    try:
                        word = int(decode_types(["uint256"], bitmap_raw)[0])
                        category = (word >> EMODE_SHIFT) & 0xFF
                    except Exception:
                        category = 0
                symbol = decode_symbol(symbol_raw) if symbol_ok else "UNKNOWN"
                reserves.append(
                    {
                        "address": checksum(asset),
                        "symbol": symbol,
                        "decimals": int(decimals),
                        "ltv": Decimal(int(ltv)) / BPS,
                        "liquidation_threshold": Decimal(int(threshold)) / BPS,
                        "reserve_collateral_enabled": bool(can_collateral),
                        "emode_category": category,
                    }
                )
            payload = (reserves, base_unit or 10**8)
            self._meta[chain.key] = (now + self.metadata_ttl, payload)
            return payload

    async def _account(self, rpc: ChainRpc, pool: str, user: str) -> dict:
        raw = await rpc.eth_call(pool, encode_call("getUserAccountData(address)", ["address"], [user]))
        collateral, debt, _available, liquidation_threshold, _ltv, health = decode_types(
            ["uint256"] * 6,
            raw,
        )
        health_dec = Decimal(int(health)) / HF_SCALE
        protocol_health = None if debt == 0 or health_dec >= HF_SENTINEL else health_dec
        protocol_lt = None if collateral == 0 else Decimal(int(liquidation_threshold)) / BPS
        return {
            "collateral": int(collateral),
            "debt": int(debt),
            "health": protocol_health,
            "liquidation_threshold": protocol_lt,
        }

    async def _emode(self, rpc: ChainRpc, pool: str, user: str) -> tuple[int, Decimal | None, Decimal | None, str]:
        try:
            raw = await rpc.eth_call(pool, encode_call("getUserEMode(address)", ["address"], [user]))
            emode = int(decode_types(["uint256"], raw)[0])
        except Exception:
            return 0, None, None, ""
        if emode == 0:
            return 0, None, None, ""
        try:
            data = await rpc.eth_call(pool, encode_call("getEModeCategoryData(uint8)", ["uint8"], [emode]))
            ltv, threshold, _bonus, _source, label = decode_types(
                ["uint16", "uint16", "uint16", "address", "string"],
                data,
            )
            return emode, Decimal(int(ltv)) / BPS, Decimal(int(threshold)) / BPS, str(label)
        except Exception:
            logger.info("e-mode category %s unreadable", emode)
            return emode, None, None, ""

    async def _user_states(
        self,
        rpc: ChainRpc,
        chain: ChainConfig,
        reserves: list[dict],
        user: str,
        emode: int,
    ) -> list[ReserveState]:
        if not reserves:
            return []
        calls = [
            (
                chain.aave.data_provider,
                encode_call("getUserReserveData(address,address)", ["address", "address"], [item["address"], user]),
            )
            for item in reserves
        ]
        rows = await rpc.multicall(calls, chunk=10)
        active: list[tuple[dict, int, int, int, bool]] = []
        for item, (ok, raw) in zip(reserves, rows, strict=True):
            if not ok or not raw:
                continue
            supply, stable, variable, *_rest, used = decode_types(
                ["uint256", "uint256", "uint256", "uint256", "uint256", "uint256", "uint256", "uint40", "bool"],
                raw,
            )
            if supply == 0 and stable == 0 and variable == 0:
                continue
            active.append((item, int(supply), int(stable), int(variable), bool(used)))
        if not active:
            return []
        price_rows = await rpc.multicall(
            [
                (chain.aave.oracle, encode_call("getAssetPrice(address)", ["address"], [item["address"]]))
                for item, *_rest in active
            ],
            chunk=20,
        )
        states: list[ReserveState] = []
        for (item, supply, stable, variable, used), (ok, raw) in zip(active, price_rows, strict=True):
            price = int(decode_types(["uint256"], raw)[0]) if ok and raw else 0
            states.append(
                ReserveState(
                    address=item["address"],
                    symbol=item["symbol"],
                    decimals=item["decimals"],
                    ltv=item["ltv"],
                    liquidation_threshold=item["liquidation_threshold"],
                    reserve_collateral_enabled=item["reserve_collateral_enabled"],
                    emode_category=item["emode_category"] if emode else item["emode_category"],
                    supply_raw=supply,
                    stable_debt_raw=stable,
                    variable_debt_raw=variable,
                    usage_as_collateral=used,
                    price_raw=price,
                )
            )
        return states

    def _ok(
        self,
        chain: ChainConfig,
        started: float,
        positions: list[Position] | None = None,
        warning: str | None = None,
    ) -> AdapterResult:
        return AdapterResult(
            chain=chain.key,
            protocol=self.protocol,
            positions=positions or [],
            ok=True,
            warning=warning,
            elapsed_ms=_elapsed(started),
        )


def _reconciliation_warning(account: dict, positions: list[Position], base_unit: int) -> str | None:
    unit = Decimal(base_unit or 10**8)
    notes: list[str] = []
    reported_debt = Decimal(account["debt"]) / unit
    reported_collateral = Decimal(account["collateral"]) / unit
    summed_debt = sum((p.value_usd for p in positions if p.type == "borrow"), ZERO)
    summed_collateral = sum((p.value_usd for p in positions if p.usage_as_collateral), ZERO)
    if reported_debt > Decimal("10") and abs(summed_debt - reported_debt) / reported_debt > Decimal("0.08"):
        notes.append("recomputed debt differs from Aave's account total")
    if (
        reported_collateral > Decimal("10")
        and abs(summed_collateral - reported_collateral) / reported_collateral > Decimal("0.08")
    ):
        notes.append("recomputed collateral differs from Aave's account total")
    return "; ".join(notes) or None


def _elapsed(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


def _brief(exc: Exception) -> str:
    if isinstance(exc, RpcError):
        return str(exc)
    text = str(exc).splitlines()[0].strip()
    return text[:180] or exc.__class__.__name__
