from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.core.actions import suggest_action
from app.models.risk import ActionQuote, Alert, Analysis, Slice, SuggestedAction
from app.models.schemas import (
    AccountOut,
    AlertOut,
    ActionOut,
    ConcentrationOut,
    IngestionOut,
    PortfolioOut,
    PositionOut,
    QuoteOut,
    SliceOut,
    StressAccountOut,
    StressOut,
    SummaryOut,
)
from app.registry import CHAINS

METHODOLOGY = (
    "Health is calculated inside each lending account. Collateral is not shared across protocols or chains, "
    "so a debt-weighted portfolio health factor can hide one weak account. The worst health factor is the liquidation signal. "
    "Distance is the uniform collateral drawdown, or the uniform debt increase, depending on which leg is volatile."
)


def num(value: Decimal | None, digits: int = 8) -> float | None:
    if value is None:
        return None
    return float(round(value, digits))


def required(value: Decimal | None, digits: int = 8) -> float:
    return num(value, digits) or 0.0


def _jsonish(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {key: _jsonish(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonish(item) for item in value]
    return value


def _slices(rows: list[Slice]) -> list[SliceOut]:
    return [SliceOut(key=row.key, value_usd=required(row.value_usd), share=required(row.share)) for row in rows]


def _action(action: SuggestedAction | None) -> ActionOut | None:
    if action is None:
        return None
    return ActionOut(
        kind=action.kind,
        account_key=action.account_key,
        chain=action.chain,
        protocol_name=action.protocol_name,
        market_name=action.market_name,
        asset=action.asset,
        amount=required(action.amount),
        amount_usd=required(action.amount_usd),
        target_health=required(action.target_health),
        health_before=required(action.health_before),
        health_after=num(action.health_after),
        worst_before=required(action.worst_before),
        worst_after=num(action.worst_after),
        worst_after_account_key=action.worst_after_account_key,
        worst_after_chain=action.worst_after_chain,
        worst_after_market_name=action.worst_after_market_name,
        quote=_quote(action.quote),
    )


def _quote(quote: ActionQuote | None) -> QuoteOut | None:
    if quote is None:
        return None
    return QuoteOut(
        status=quote.status,
        slippage_bps=quote.slippage_bps,
        wallet_balance=num(quote.wallet_balance),
        shortfall=num(quote.shortfall),
        gas_units=quote.gas_units,
        gas_native=num(quote.gas_native),
        gas_usd=num(quote.gas_usd),
        health_after=num(quote.health_after),
        expires_at=quote.expires_at,
        note=quote.note,
    )


def _chain_name(chain: str) -> str:
    config = CHAINS.get(chain)
    return config.name if config else chain


def present(
    *,
    address: str,
    demo: bool,
    data_quality: str,
    fetched_at: str,
    elapsed_ms: int,
    analysis: Analysis,
    alerts: list[Alert],
    ingestion: list[IngestionOut],
    quote: ActionQuote | None = None,
) -> PortfolioOut:
    worst = next((account for account in analysis.accounts if account.account_key == analysis.worst_account_key), None)
    concentration = analysis.concentration
    action = suggest_action(analysis)
    if action is not None and quote is not None:
        action = action.model_copy(update={"quote": quote})
    return PortfolioOut(
        address=address,
        demo=demo,
        data_quality=data_quality,
        fetched_at=fetched_at,
        elapsed_ms=elapsed_ms,
        methodology=METHODOLOGY,
        summary=SummaryOut(
            total_supplied_usd=required(analysis.total_supplied_usd),
            total_collateral_usd=required(analysis.total_collateral_usd),
            total_debt_usd=required(analysis.total_debt_usd),
            net_usd=required(analysis.total_supplied_usd - analysis.total_debt_usd),
            portfolio_health_factor=num(analysis.portfolio_health_factor),
            worst_health_factor=num(analysis.worst_health_factor),
            worst_account_key=analysis.worst_account_key,
            primary_risk=worst.primary_risk if worst else "none",
            primary_distance_pct=num(worst.primary_distance_pct) if worst else None,
            collateral_drawdown_pct=num(worst.collateral_drawdown_pct) if worst else None,
            debt_increase_pct=num(worst.debt_increase_pct) if worst else None,
            account_count=len(analysis.accounts),
            position_count=len(analysis.positions),
            alert_count=len(alerts),
        ),
        positions=[
            PositionOut(
                id=position.id,
                user_address=position.user_address,
                chain=position.chain,
                chain_name=_chain_name(position.chain),
                protocol=position.protocol,
                protocol_name=position.protocol_name,
                market=position.market,
                market_name=position.market_name,
                account_key=position.account_key,
                type=position.type,
                asset=position.asset,
                asset_address=position.asset_address,
                amount=required(position.amount),
                value_usd=required(position.value_usd),
                price_usd=required(position.price_usd),
                collateral_factor=num(position.collateral_factor),
                liquidation_threshold=num(position.liquidation_threshold),
                usage_as_collateral=position.usage_as_collateral,
                health_factor=num(position.health_factor),
                liquidation_price=num(position.liquidation_price),
                distance_to_liquidation_pct=num(position.distance_to_liquidation_pct),
                distance_to_liquidation_usd=num(position.distance_to_liquidation_usd),
                entry_price=num(position.entry_price),
                price_source=position.price_source,
                reference_price_usd=num(position.reference_price_usd),
                price_gap=num(position.price_gap),
                price_status=position.price_status,
                metadata=_jsonish(position.metadata),
            )
            for position in analysis.positions
        ],
        accounts=[
            AccountOut(
                account_key=account.account_key,
                chain=account.chain,
                chain_name=_chain_name(account.chain),
                protocol=account.protocol,
                protocol_name=account.protocol_name,
                market=account.market,
                market_name=account.market_name,
                collateral_usd=required(account.collateral_usd),
                supplied_usd=required(account.supplied_usd),
                debt_usd=required(account.debt_usd),
                weighted_collateral_usd=required(account.weighted_collateral_usd),
                health_factor=num(account.health_factor),
                computed_health_factor=num(account.computed_health_factor),
                protocol_health_factor=num(account.protocol_health_factor),
                protocol_liquidation_threshold=num(account.protocol_liquidation_threshold),
                collateral_drawdown_pct=num(account.collateral_drawdown_pct),
                debt_increase_pct=num(account.debt_increase_pct),
                primary_risk=account.primary_risk,
                primary_distance_pct=num(account.primary_distance_pct),
                liquidatable=account.liquidatable,
                collateral_assets=account.collateral_assets,
                debt_assets=account.debt_assets,
            )
            for account in analysis.accounts
        ],
        concentration=ConcentrationOut(
            collateral_by_asset=_slices(concentration.collateral_by_asset),
            collateral_by_protocol=_slices(concentration.collateral_by_protocol),
            collateral_by_chain=_slices(concentration.collateral_by_chain),
            collateral_by_factor=_slices(concentration.collateral_by_factor),
            debt_by_asset=_slices(concentration.debt_by_asset),
            debt_by_protocol=_slices(concentration.debt_by_protocol),
            debt_by_chain=_slices(concentration.debt_by_chain),
            debt_by_factor=_slices(concentration.debt_by_factor),
            collateral_hhi=required(concentration.collateral_hhi),
            debt_hhi=required(concentration.debt_hhi),
            collateral_top_key=concentration.collateral_top_key,
            collateral_top_share=required(concentration.collateral_top_share),
            debt_top_key=concentration.debt_top_key,
            debt_top_share=required(concentration.debt_top_share),
        ),
        stress=[
            StressOut(
                id=scenario.id,
                label=scenario.label,
                description=scenario.description,
                portfolio_health_factor=num(scenario.portfolio_health_factor),
                worst_health_factor=num(scenario.worst_health_factor),
                health_factor_delta=num(scenario.health_factor_delta),
                any_liquidatable=scenario.any_liquidatable,
                accounts=[
                    StressAccountOut(
                        account_key=row.account_key,
                        chain=row.chain,
                        protocol_name=row.protocol_name,
                        market_name=row.market_name,
                        health_factor=num(row.health_factor),
                        liquidatable=row.liquidatable,
                    )
                    for row in scenario.accounts
                ],
            )
            for scenario in analysis.stress
        ],
        action=_action(action),
        alerts=[
            AlertOut(
                id=alert.id,
                severity=alert.severity,
                code=alert.code,
                title=alert.title,
                detail=alert.detail,
                chain=alert.chain,
                protocol=alert.protocol,
                asset=alert.asset,
                account_key=alert.account_key,
            )
            for alert in alerts
        ],
        ingestion=ingestion,
    )
