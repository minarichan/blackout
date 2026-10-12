from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from eth_utils import is_address, to_checksum_address

from app.adapters.aave_v3 import AaveV3Adapter
from app.adapters.base import AdapterResult
from app.adapters.compound_v3 import CompoundV3Adapter
from app.adapters.prices import PriceService
from app.config import Settings
from app.core.alerts import build_alerts
from app.core.normalizer import clean
from app.core.risk_engine import analyze
from app.db.models import Snapshot, WatchItem
from app.db.session import session_scope
from app.demo import demo_positions
from app.models.schemas import IngestionOut, PortfolioOut, SnapshotOut, WatchOut
from app.registry import chain_configs
from app.services.cache import RateLimiter, TtlCache
from app.services.ingestion import IngestionService, build_rpcs
from app.services.presenter import present

logger = logging.getLogger("blackout.portfolio")


class AddressError(ValueError):
    pass


class RateLimitError(Exception):
    pass


def normalize_address(value: str) -> str:
    text = value.strip()
    if text.lower() == "demo":
        return "demo"
    if not is_address(text):
        raise AddressError("Enter a wallet address, or load the demo book.")
    return to_checksum_address(text.lower())


class PortfolioService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.chains = chain_configs(settings.enabled_chain_list)
        self.gate = asyncio.Semaphore(6)
        self.rpcs = build_rpcs(
            self.chains,
            settings.rpc_overrides,
            settings.request_timeout_seconds,
            self.gate,
        )
        self.aave = AaveV3Adapter(self.rpcs, settings.metadata_ttl_seconds)
        self.compound = CompoundV3Adapter(self.rpcs, settings.metadata_ttl_seconds)
        self.ingestion = IngestionService(self.chains, self.aave, self.compound)
        self.prices = PriceService(self.rpcs.get("ethereum"), settings.coingecko_api_key)
        self.cache = TtlCache()
        self.limiter = RateLimiter(settings.rate_limit_per_minute)

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        await self.prices.stop()
        for rpc in self.rpcs.values():
            await rpc.stop()

    async def get_portfolio(self, address: str, *, refresh: bool = False, client_key: str = "local") -> PortfolioOut:
        normalized = normalize_address(address)
        cache_key = normalized.lower()
        if not refresh:
            cached = self.cache.get(cache_key)
            if cached is not None:
                return cached.model_copy(deep=True)

        demo = normalized == "demo"
        if not demo and not self.limiter.allow(client_key):
            raise RateLimitError("Too many live reads from this client. Wait a minute and try again.")

        started = datetime.now(timezone.utc)
        timer = started.timestamp()
        ingestion: list[IngestionOut] = []
        if demo:
            positions = demo_positions()
            extra_alerts = []
            quality = "demo"
        else:
            results = await self.ingestion.collect(normalized)
            positions = [position for result in results for position in result.positions]
            positions, extra_alerts = await self.prices.enrich(positions)
            ingestion = [_ingestion(result) for result in results]
            quality = _quality(results)

        positions = clean(positions, self.settings.min_position_value)
        analysis = analyze(positions)
        alerts = build_alerts(analysis, extra_alerts)
        elapsed_ms = int((datetime.now(timezone.utc).timestamp() - timer) * 1000)
        book = present(
            address=normalized,
            demo=demo,
            data_quality=quality,
            fetched_at=started.isoformat(),
            elapsed_ms=max(elapsed_ms, 0),
            analysis=analysis,
            alerts=alerts,
            ingestion=ingestion,
        )
        self.cache.set(cache_key, book, self.settings.cache_ttl_seconds)
        if quality != "unavailable":
            self._snapshot(book)
        return book.model_copy(deep=True)

    def history(self, address: str) -> list[SnapshotOut]:
        normalized = normalize_address(address)
        with session_scope() as session:
            rows = (
                session.query(Snapshot)
                .filter(Snapshot.address == normalized)
                .order_by(Snapshot.id.desc())
                .limit(30)
                .all()
            )
        return [
            SnapshotOut(
                timestamp=row.created_at.isoformat(),
                total_collateral_usd=row.collateral_usd,
                total_debt_usd=row.debt_usd,
                portfolio_health_factor=row.portfolio_health_factor,
                worst_health_factor=row.worst_health_factor,
                alert_count=row.alert_count,
            )
            for row in rows
        ]

    def list_watchlist(self) -> list[WatchOut]:
        with session_scope() as session:
            rows = session.query(WatchItem).order_by(WatchItem.created_at.desc()).all()
            return [_watch(row) for row in rows]

    def save_watch(self, address: str, label: str) -> WatchOut:
        normalized = normalize_address(address)
        cleaned = label.strip()[:80]
        with session_scope() as session:
            row = session.get(WatchItem, normalized)
            if row is None:
                row = WatchItem(address=normalized, label=cleaned, created_at=datetime.now(timezone.utc))
                session.add(row)
            else:
                row.label = cleaned
            session.flush()
            return _watch(row)

    def delete_watch(self, address: str) -> bool:
        normalized = normalize_address(address)
        with session_scope() as session:
            row = session.get(WatchItem, normalized)
            if row is None:
                return False
            session.delete(row)
            return True

    def _snapshot(self, book: PortfolioOut) -> None:
        try:
            with session_scope() as session:
                session.add(
                    Snapshot(
                        address=book.address,
                        created_at=datetime.now(timezone.utc),
                        collateral_usd=book.summary.total_collateral_usd,
                        debt_usd=book.summary.total_debt_usd,
                        portfolio_health_factor=book.summary.portfolio_health_factor,
                        worst_health_factor=book.summary.worst_health_factor,
                        alert_count=book.summary.alert_count,
                        note=book.data_quality,
                    )
                )
                session.flush()
                stale = (
                    session.query(Snapshot)
                    .filter(Snapshot.address == book.address)
                    .order_by(Snapshot.id.desc())
                    .offset(30)
                    .all()
                )
                for row in stale:
                    session.delete(row)
        except Exception:
            logger.exception("failed to store risk snapshot")


def _ingestion(result: AdapterResult) -> IngestionOut:
    return IngestionOut(
        chain=result.chain,
        protocol=result.protocol,
        ok=result.ok,
        error=result.error,
        warning=result.warning,
        position_count=len(result.positions),
        elapsed_ms=result.elapsed_ms,
    )


def _quality(results: list[AdapterResult]) -> str:
    if not results or not any(result.ok for result in results):
        return "unavailable"
    if all(result.ok for result in results):
        return "live"
    return "partial"


def _watch(row: WatchItem) -> WatchOut:
    created = row.created_at.isoformat() if row.created_at else ""
    return WatchOut(address=row.address, label=row.label or "", created_at=created)
