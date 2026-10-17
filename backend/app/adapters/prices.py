from __future__ import annotations

import logging
import time
from decimal import Decimal

import httpx

from app.adapters.codec import decode_types, encode_call
from app.adapters.rpc import ChainRpc
from app.core.assets import COINGECKO_IDS, canonical_symbol, reference_asset
from app.models.position import Position
from app.models.risk import Alert
from app.registry import CHAINLINK_USD

logger = logging.getLogger("blackout.prices")

ZERO = Decimal("0")
ONE = Decimal("1")
PEG_ELEVATED = Decimal("0.02")
PEG_HIGH = Decimal("0.05")
ORACLE_ELEVATED = Decimal("0.03")
ORACLE_HIGH = Decimal("0.07")
CHAINLINK_DECIMALS = Decimal(10) ** 8
CHAINLINK_STALE_SECONDS = 86_400


def chainlink_usd(answer: int, updated_at: int, now: float) -> Decimal | None:
    """Return a Chainlink USD answer, or nothing when the round is empty or stale."""
    if answer <= 0:
        return None
    if updated_at and now - updated_at > CHAINLINK_STALE_SECONDS:
        return None
    return Decimal(answer) / CHAINLINK_DECIMALS


def apply_price(
    position: Position,
    *,
    reference: Decimal | None,
    fill: Decimal | None = None,
    fill_source: str | None = None,
) -> tuple[Position, Alert | None]:
    """Attach a reference and a status without replacing a live protocol price.

    A missing protocol price may be filled from Chainlink or CoinGecko. That fill
    is marked fallback so health is not mistaken for a protocol-oracle figure.
    """
    kind = reference_asset(position.asset)
    if position.price_usd > ZERO:
        gap = None
        status = "protocol"
        if reference is not None and reference > ZERO:
            gap = (position.price_usd - reference) / reference
            elevated = PEG_ELEVATED if kind == "USD" else ORACLE_ELEVATED
            if abs(gap) >= elevated:
                status = "divergent"
        updated = position.model_copy(
            update={
                "reference_price_usd": reference if reference and reference > ZERO else None,
                "price_gap": gap,
                "price_status": status,
            }
        )
        alert = _divergence_alert(updated, kind) if status == "divergent" and gap is not None else None
        return updated, alert

    if fill is not None and fill > ZERO and fill_source:
        updated = position.model_copy(
            update={
                "price_usd": fill,
                "value_usd": position.amount * fill,
                "price_source": fill_source,
                "reference_price_usd": fill,
                "price_gap": ZERO,
                "price_status": "fallback",
            }
        )
        return updated, _fallback_alert(updated)
    return position.model_copy(update={"price_status": "unpriced", "price_gap": None, "reference_price_usd": None}), _missing_alert(position)


def _divergence_alert(position: Position, kind: str | None) -> Alert:
    gap = position.price_gap or ZERO
    high = PEG_HIGH if kind == "USD" else ORACLE_HIGH
    reference = position.reference_price_usd or ZERO
    label = kind or "reference"
    return Alert(
        id=f"oracle:{position.chain}:{canonical_symbol(position.asset)}",
        severity="high" if abs(gap) >= high else "elevated",
        code="oracle_divergence",
        title=f"{position.asset} oracle is {abs(gap) * Decimal('100'):.1f}% off reference",
        detail=(
            f"Protocol price is {position.price_usd:.4f} and the {label} reference is {reference:.4f} "
            f"on {position.chain}. Liquidation math still uses the protocol oracle."
        ),
        chain=position.chain,
        protocol=position.protocol,
        asset=position.asset,
    )


def _fallback_alert(position: Position) -> Alert | None:
    if position.type != "borrow" and not position.usage_as_collateral:
        return None
    source = "Chainlink" if position.price_source == "chainlink" else "CoinGecko"
    return Alert(
        id=f"fallback:{position.chain}:{canonical_symbol(position.asset)}",
        severity="elevated",
        code="price_fallback",
        title=f"{position.asset} health uses a {source} price",
        detail=(
            f"The protocol oracle had no price on {position.chain}, so this leg is marked {position.price_usd:.4f} "
            f"from {source}. Health and liquidation distance for the account include that substitute."
        ),
        chain=position.chain,
        protocol=position.protocol,
        asset=position.asset,
    )


def _missing_alert(position: Position) -> Alert | None:
    if position.type != "borrow" and not position.usage_as_collateral:
        return None
    return Alert(
        id=f"unpriced:{position.chain}:{canonical_symbol(position.asset)}",
        severity="high",
        code="price_missing",
        title=f"{position.asset} has no price",
        detail=(
            f"Neither the protocol oracle nor a reference returned a price on {position.chain}. "
            "This leg is excluded from dollar value, so the account health is incomplete."
        ),
        chain=position.chain,
        protocol=position.protocol,
        asset=position.asset,
    )


class PriceService:
    """Protocol oracles stay authoritative. Chainlink and CoinGecko only cross-check or fill gaps."""

    def __init__(self, ethereum: ChainRpc | None, coingecko_api_key: str = ""):
        self.ethereum = ethereum
        self.coingecko_api_key = coingecko_api_key
        self._client: httpx.AsyncClient | None = None
        self._chainlink: tuple[float, dict[str, Decimal]] | None = None

    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=8)
        return self._client

    async def stop(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def enrich(self, positions: list[Position]) -> tuple[list[Position], list[Alert]]:
        if not positions:
            return positions, []
        chainlink = await self._chainlink_prices()
        needed: set[str] = set()
        for position in positions:
            token = canonical_symbol(position.asset)
            if position.price_usd <= ZERO and token in COINGECKO_IDS:
                needed.add(COINGECKO_IDS[token])
        if "ETH" not in chainlink:
            needed.add("ethereum")
        if "BTC" not in chainlink:
            needed.add("bitcoin")
        spot = await self._coingecko(needed)
        if "ETH" not in chainlink and "ethereum" in spot:
            chainlink["ETH"] = spot["ethereum"]
        if "BTC" not in chainlink and "bitcoin" in spot:
            chainlink["BTC"] = spot["bitcoin"]

        updated: list[Position] = []
        seen: set[str] = set()
        alerts: list[Alert] = []
        for position in positions:
            token = canonical_symbol(position.asset)
            reference = self._reference_price(token, chainlink)
            fill, fill_source = self._fill(token, chainlink, spot)
            current, alert = apply_price(position, reference=reference, fill=fill, fill_source=fill_source)
            if alert is not None and alert.id not in seen:
                seen.add(alert.id)
                alerts.append(alert)
            updated.append(current)
        return updated, alerts

    async def _chainlink_prices(self) -> dict[str, Decimal]:
        now = time.monotonic()
        if self._chainlink and self._chainlink[0] > now:
            return dict(self._chainlink[1])
        prices: dict[str, Decimal] = {}
        if self.ethereum is not None:
            for symbol, feed in CHAINLINK_USD.items():
                try:
                    raw = await self.ethereum.eth_call(feed, encode_call("latestRoundData()"))
                    _round_id, answer, _started, updated_at, _answered = decode_types(
                        ["uint80", "int256", "uint256", "uint256", "uint80"],
                        raw,
                    )
                    price = chainlink_usd(int(answer), int(updated_at), time.time())
                    if price is None:
                        continue
                    prices[symbol] = price
                except Exception:
                    logger.info("chainlink %s unavailable", symbol)
        self._chainlink = (now + 60, prices)
        return dict(prices)

    async def _coingecko(self, ids: set[str]) -> dict[str, Decimal]:
        if not ids:
            return {}
        headers = {"accept": "application/json"}
        if self.coingecko_api_key:
            headers["x-cg-demo-api-key"] = self.coingecko_api_key
        try:
            response = await self._http().get(
                "https://api.coingecko.com/api/v3/simple/price",
                params={"ids": ",".join(sorted(ids)), "vs_currencies": "usd"},
                headers=headers,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception:
            logger.info("coingecko lookup failed", exc_info=True)
            return {}
        prices: dict[str, Decimal] = {}
        for asset_id, row in payload.items():
            usd = row.get("usd") if isinstance(row, dict) else None
            if usd:
                prices[asset_id] = Decimal(str(usd))
        return prices

    def _fill(self, token: str, chainlink: dict[str, Decimal], spot: dict[str, Decimal]) -> tuple[Decimal | None, str | None]:
        if token in {"ETH", "WETH"} and chainlink.get("ETH"):
            return chainlink["ETH"], "chainlink"
        if token in {"WBTC", "CBBTC"} and chainlink.get("BTC"):
            return chainlink["BTC"], "chainlink"
        spot_price = spot.get(COINGECKO_IDS.get(token, ""))
        if spot_price is not None and spot_price > ZERO:
            return spot_price, "coingecko"
        return None, None

    def _reference_price(self, token: str, chainlink: dict[str, Decimal]) -> Decimal | None:
        kind = reference_asset(token)
        if kind == "USD":
            return ONE
        if kind in {"ETH", "BTC"}:
            return chainlink.get(kind)
        return None
