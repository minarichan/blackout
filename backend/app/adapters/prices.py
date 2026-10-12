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
            current = position
            if position.price_usd <= ZERO:
                fill = spot.get(COINGECKO_IDS.get(token, ""))
                if fill is None and token in {"ETH", "WETH"}:
                    fill = chainlink.get("ETH")
                if fill is None and token in {"WBTC", "CBBTC"}:
                    fill = chainlink.get("BTC")
                if fill is not None and fill > ZERO:
                    current = position.model_copy(
                        update={
                            "price_usd": fill,
                            "value_usd": position.amount * fill,
                            "price_source": "coingecko" if token not in {"ETH", "WETH", "WBTC", "CBBTC"} else position.price_source,
                        }
                    )
                    if current.price_source == "coingecko" or position.price_usd <= ZERO:
                        current = current.model_copy(update={"price_source": "reference"})
            elif reference is not None and reference > ZERO:
                gap = abs(current.price_usd - reference) / reference
                kind = reference_asset(position.asset)
                elevated = PEG_ELEVATED if kind == "USD" else ORACLE_ELEVATED
                high = PEG_HIGH if kind == "USD" else ORACLE_HIGH
                key = f"{position.chain}:{token}"
                if gap >= elevated and key not in seen:
                    seen.add(key)
                    alerts.append(
                        Alert(
                            id=f"oracle:{key}",
                            severity="high" if gap >= high else "elevated",
                            code="oracle_divergence",
                            title=f"{position.asset} oracle is {gap * Decimal('100'):.1f}% off reference",
                            detail=(
                                f"Protocol price is {current.price_usd:.4f} and the {kind} reference is {reference:.4f} "
                                f"on {position.chain}. Liquidation math still uses the protocol oracle."
                            ),
                            chain=position.chain,
                            protocol=position.protocol,
                            asset=position.asset,
                        )
                    )
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
                    if int(answer) <= 0:
                        continue
                    if int(updated_at) and time.time() - int(updated_at) > 86_400:
                        continue
                    prices[symbol] = Decimal(int(answer)) / CHAINLINK_DECIMALS
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

    def _reference_price(self, token: str, chainlink: dict[str, Decimal]) -> Decimal | None:
        kind = reference_asset(token)
        if kind == "USD":
            return ONE
        if kind in {"ETH", "BTC"}:
            return chainlink.get(kind)
        return None
