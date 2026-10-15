"""Pure lending-risk math.

Health factor matches the lending-market definition:

    health = sum(collateral_usd * liquidation_threshold) / debt_usd

A uniform collateral price drop reaches liquidation after:

    drawdown = (health - 1) / health

A uniform debt price increase reaches liquidation after:

    increase = health - 1

Those two moves are not the same number. A book that borrows ETH against
stables is hurt by ETH rising, not by ETH falling. The engine classifies
that and keeps the debt-weighted portfolio health separate from the worst
single account. Collateral is not shared across accounts, chains, or protocols.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from app.core.assets import factor_bucket, is_volatile
from app.models.position import Position
from app.models.risk import (
    AccountRisk,
    Analysis,
    Concentration,
    Slice,
    StressAccount,
    StressScenario,
)

ZERO = Decimal("0")
ONE = Decimal("1")

SCENARIOS: tuple[dict, ...] = (
    {
        "id": "eth_minus_15",
        "label": "ETH −15%",
        "description": "ETH-family assets down 15%, with a smaller move in BTC and alts.",
        "shocks": {
            "eth": Decimal("-0.15"),
            "btc": Decimal("-0.08"),
            "alt": Decimal("-0.10"),
            "soft_stable": Decimal("-0.05"),
            "usdc": ZERO,
            "stable": ZERO,
        },
    },
    {
        "id": "eth_minus_20",
        "label": "ETH −20%",
        "description": "A sharper ETH drawdown. Stables are unchanged.",
        "shocks": {
            "eth": Decimal("-0.20"),
            "btc": Decimal("-0.10"),
            "alt": Decimal("-0.15"),
            "soft_stable": Decimal("-0.08"),
            "usdc": ZERO,
            "stable": ZERO,
        },
    },
    {
        "id": "eth_plus_20",
        "label": "ETH +20%",
        "description": "ETH rally. Books that borrow ETH against stables get tighter.",
        "shocks": {
            "eth": Decimal("0.20"),
            "btc": Decimal("0.10"),
            "alt": Decimal("0.12"),
            "soft_stable": Decimal("0.02"),
            "usdc": ZERO,
            "stable": ZERO,
        },
    },
    {
        "id": "btc_minus_20",
        "label": "BTC −20%",
        "description": "Bitcoin drawdown with a partial ETH and alt move.",
        "shocks": {
            "btc": Decimal("-0.20"),
            "eth": Decimal("-0.08"),
            "alt": Decimal("-0.10"),
            "soft_stable": Decimal("-0.03"),
            "usdc": ZERO,
            "stable": ZERO,
        },
    },
    {
        "id": "risk_off",
        "label": "Risk-off",
        "description": "ETH −25%, BTC −20%, alts −30%. Stables unchanged.",
        "shocks": {
            "eth": Decimal("-0.25"),
            "btc": Decimal("-0.20"),
            "alt": Decimal("-0.30"),
            "soft_stable": Decimal("-0.10"),
            "usdc": ZERO,
            "stable": ZERO,
        },
    },
    {
        "id": "usdc_minus_5",
        "label": "USDC −5%",
        "description": "USDC-family depeg. Other stables move 1%.",
        "shocks": {
            "usdc": Decimal("-0.05"),
            "stable": Decimal("-0.01"),
            "soft_stable": Decimal("-0.02"),
            "eth": ZERO,
            "btc": ZERO,
            "alt": ZERO,
        },
    },
)


def _d(value: Decimal | None) -> Decimal:
    return value if value is not None else ZERO


def _health(weighted: Decimal, debt: Decimal) -> Decimal | None:
    if debt <= ZERO:
        return None
    if weighted <= ZERO:
        return ZERO
    return weighted / debt


def _distances(health: Decimal | None) -> tuple[Decimal | None, Decimal | None]:
    if health is None:
        return None, None
    if health <= ZERO:
        return ZERO, ZERO
    drawdown = (health - ONE) / health
    increase = health - ONE
    if health < ONE:
        return ZERO, ZERO
    return drawdown, increase


def _volatile_share(positions: list[Position]) -> Decimal:
    total = sum((p.value_usd for p in positions), ZERO)
    if total <= ZERO:
        return ZERO
    weighted = ZERO
    for position in positions:
        weight = Decimal("0.5") if factor_bucket(position.asset) == "soft_stable" else ONE
        if is_volatile(position.asset):
            weighted += position.value_usd * weight
    return weighted / total


def _primary_risk(
    health: Decimal | None,
    collaterals: list[Position],
    debts: list[Position],
) -> tuple[str, Decimal | None]:
    drawdown, increase = _distances(health)
    if health is None:
        return "none", None
    collateral_vol = _volatile_share(collaterals)
    debt_vol = _volatile_share(debts)
    if debt_vol >= Decimal("0.6") and collateral_vol < Decimal("0.4"):
        return "debt_expansion", increase
    if collateral_vol >= Decimal("0.4") and debt_vol >= Decimal("0.4"):
        candidates = [item for item in (drawdown, increase) if item is not None]
        return "mixed", min(candidates) if candidates else None
    return "collateral_drawdown", drawdown


def _isolated_collateral_move(cushion: Decimal, contribution: Decimal) -> Decimal | None:
    if contribution <= ZERO:
        return None
    return cushion / contribution


def _annotate_position(position: Position, account: AccountRisk, cushion: Decimal) -> Position:
    updated = position.model_copy(deep=True)
    updated.health_factor = account.health_factor
    if account.health_factor is None:
        return updated

    if position.type == "supply" and position.usage_as_collateral and position.liquidation_threshold:
        contribution = position.value_usd * position.liquidation_threshold
        move = _isolated_collateral_move(cushion, contribution)
        if move is None or position.price_usd <= ZERO:
            return updated
        room = max(move, ZERO)
        updated.distance_to_liquidation_pct = min(room, ONE)
        updated.distance_to_liquidation_usd = position.value_usd * updated.distance_to_liquidation_pct
        boundary = position.price_usd * (ONE - move)
        updated.liquidation_price = boundary if boundary > ZERO else ZERO
        if move >= ONE:
            updated.metadata = {**updated.metadata, "safe_if_zero": True}
        return updated

    if position.type == "borrow" and position.value_usd > ZERO and position.price_usd > ZERO:
        move = cushion / position.value_usd
        room = max(move, ZERO)
        updated.distance_to_liquidation_pct = room
        updated.distance_to_liquidation_usd = position.value_usd * room
        updated.liquidation_price = position.price_usd * (ONE + move)
    return updated


def compute_account(
    account_key: str,
    positions: list[Position],
    *,
    use_protocol: bool = True,
) -> AccountRisk:
    sample = positions[0]
    supplies = [p for p in positions if p.type == "supply"]
    collaterals = [
        p
        for p in supplies
        if p.usage_as_collateral and p.liquidation_threshold is not None and p.liquidation_threshold > ZERO
    ]
    debts = [p for p in positions if p.type == "borrow"]
    collateral_usd = sum((p.value_usd for p in collaterals), ZERO)
    supplied_usd = sum((p.value_usd for p in supplies), ZERO)
    debt_usd = sum((p.value_usd for p in debts), ZERO)
    weighted = sum((p.value_usd * _d(p.liquidation_threshold) for p in collaterals), ZERO)
    computed = _health(weighted, debt_usd)

    protocol_values = [
        p.metadata.get("protocol_health_factor")
        for p in positions
        if use_protocol and p.metadata.get("protocol_health_factor") is not None
    ]
    protocol_health = Decimal(str(protocol_values[0])) if protocol_values else None

    protocol_lt_values = [
        p.metadata.get("protocol_liquidation_threshold")
        for p in positions
        if p.metadata.get("protocol_liquidation_threshold") is not None
    ]
    protocol_lt = Decimal(str(protocol_lt_values[0])) if protocol_lt_values else None

    headline = protocol_health if protocol_health is not None else computed
    drawdown, increase = _distances(headline)
    primary, primary_distance = _primary_risk(headline, collaterals, debts)
    return AccountRisk(
        account_key=account_key,
        chain=sample.chain,
        protocol=sample.protocol,
        protocol_name=sample.protocol_name,
        market=sample.market,
        market_name=sample.market_name,
        collateral_usd=collateral_usd,
        supplied_usd=supplied_usd,
        debt_usd=debt_usd,
        weighted_collateral_usd=weighted,
        health_factor=headline,
        computed_health_factor=computed,
        protocol_health_factor=protocol_health,
        protocol_liquidation_threshold=protocol_lt,
        collateral_drawdown_pct=drawdown,
        debt_increase_pct=increase,
        primary_risk=primary,
        primary_distance_pct=primary_distance,
        liquidatable=headline is not None and headline < ONE,
        collateral_assets=sorted({p.asset for p in collaterals}),
        debt_assets=sorted({p.asset for p in debts}),
    )


def _slices(pairs: list[tuple[str, Decimal]]) -> list[Slice]:
    totals: dict[str, Decimal] = defaultdict(lambda: ZERO)
    for key, value in pairs:
        if value > ZERO:
            totals[key] += value
    grand = sum(totals.values(), ZERO)
    rows = [
        Slice(key=key, value_usd=value, share=(value / grand if grand else ZERO))
        for key, value in totals.items()
    ]
    rows.sort(key=lambda row: row.value_usd, reverse=True)
    return rows


def _hhi(rows: list[Slice]) -> Decimal:
    return sum((row.share * row.share for row in rows), ZERO)


def _top(rows: list[Slice]) -> tuple[str, Decimal]:
    if not rows:
        return "", ZERO
    return rows[0].key, rows[0].share


def _concentration(positions: list[Position]) -> Concentration:
    collaterals = [p for p in positions if p.type == "supply" and p.usage_as_collateral]
    debts = [p for p in positions if p.type == "borrow"]

    def pack(rows: list[Position]) -> dict[str, list[Slice]]:
        return {
            "asset": _slices([(p.asset, p.value_usd) for p in rows]),
            "protocol": _slices([(p.protocol_name, p.value_usd) for p in rows]),
            "chain": _slices([(p.chain, p.value_usd) for p in rows]),
            "factor": _slices([(factor_bucket(p.asset), p.value_usd) for p in rows]),
        }

    collateral = pack(collaterals)
    debt = pack(debts)
    collateral_top_key, collateral_top_share = _top(collateral["asset"])
    debt_top_key, debt_top_share = _top(debt["asset"])
    return Concentration(
        collateral_by_asset=collateral["asset"],
        collateral_by_protocol=collateral["protocol"],
        collateral_by_chain=collateral["chain"],
        collateral_by_factor=collateral["factor"],
        debt_by_asset=debt["asset"],
        debt_by_protocol=debt["protocol"],
        debt_by_chain=debt["chain"],
        debt_by_factor=debt["factor"],
        collateral_hhi=_hhi(collateral["asset"]),
        debt_hhi=_hhi(debt["asset"]),
        collateral_top_key=collateral_top_key,
        collateral_top_share=collateral_top_share,
        debt_top_key=debt_top_key,
        debt_top_share=debt_top_share,
    )


def _apply_shock(positions: list[Position], shocks: dict[str, Decimal]) -> list[Position]:
    shocked: list[Position] = []
    for position in positions:
        move = shocks.get(factor_bucket(position.asset), ZERO)
        factor = ONE + move
        if factor < ZERO:
            factor = ZERO
        shocked.append(
            position.model_copy(
                update={
                    "price_usd": position.price_usd * factor,
                    "value_usd": position.value_usd * factor,
                }
            )
        )
    return shocked


def _portfolio_health(accounts: list[AccountRisk]) -> Decimal | None:
    debt = sum((account.debt_usd for account in accounts if account.health_factor is not None), ZERO)
    if debt <= ZERO:
        return None
    weighted = sum(
        (
            account.health_factor * account.debt_usd
            for account in accounts
            if account.health_factor is not None and account.debt_usd > ZERO
        ),
        ZERO,
    )
    return weighted / debt


def _worst(accounts: list[AccountRisk]) -> AccountRisk | None:
    indebted = [account for account in accounts if account.health_factor is not None]
    if not indebted:
        return None
    return min(indebted, key=lambda account: (account.health_factor, -account.debt_usd))


def _stress(positions: list[Position], baseline: Decimal | None) -> list[StressScenario]:
    scenarios: list[StressScenario] = []
    for spec in SCENARIOS:
        shocked = _apply_shock(positions, spec["shocks"])
        grouped: dict[str, list[Position]] = defaultdict(list)
        for position in shocked:
            grouped[position.account_key].append(position)
        accounts = [compute_account(key, rows, use_protocol=False) for key, rows in grouped.items()]
        portfolio_hf = _portfolio_health(accounts)
        worst = _worst(accounts)
        delta = None
        if portfolio_hf is not None and baseline is not None:
            delta = portfolio_hf - baseline
        scenarios.append(
            StressScenario(
                id=spec["id"],
                label=spec["label"],
                description=spec["description"],
                portfolio_health_factor=portfolio_hf,
                worst_health_factor=worst.health_factor if worst else None,
                health_factor_delta=delta,
                any_liquidatable=any(account.liquidatable for account in accounts),
                accounts=[
                    StressAccount(
                        account_key=account.account_key,
                        chain=account.chain,
                        protocol_name=account.protocol_name,
                        market_name=account.market_name,
                        health_factor=account.health_factor,
                        liquidatable=account.liquidatable,
                    )
                    for account in accounts
                    if account.debt_usd > ZERO
                ],
            )
        )
    return scenarios


def _sort_positions(positions: list[Position]) -> list[Position]:
    def key(position: Position) -> tuple:
        distance = position.distance_to_liquidation_pct
        missing = distance is None
        return (
            0 if position.health_factor is not None and position.health_factor < ONE else 1,
            1 if missing else 0,
            distance if distance is not None else ZERO,
            -position.value_usd,
        )

    return sorted(positions, key=key)


def analyze(positions: list[Position]) -> Analysis:
    grouped: dict[str, list[Position]] = defaultdict(list)
    for position in positions:
        grouped[position.account_key].append(position)

    accounts = [compute_account(key, rows) for key, rows in grouped.items()]
    accounts.sort(
        key=lambda account: (
            account.health_factor is None,
            account.health_factor if account.health_factor is not None else ZERO,
            -account.debt_usd,
        )
    )
    by_key = {account.account_key: account for account in accounts}

    enriched: list[Position] = []
    for key, rows in grouped.items():
        account = by_key[key]
        cushion = account.weighted_collateral_usd - account.debt_usd
        for position in rows:
            enriched.append(_annotate_position(position, account, cushion))

    portfolio_hf = _portfolio_health(accounts)
    worst = _worst(accounts)
    return Analysis(
        positions=_sort_positions(enriched),
        accounts=accounts,
        concentration=_concentration(enriched),
        stress=_stress(positions, portfolio_hf),
        total_supplied_usd=sum((p.value_usd for p in positions if p.type == "supply"), ZERO),
        total_collateral_usd=sum((account.collateral_usd for account in accounts), ZERO),
        total_debt_usd=sum((account.debt_usd for account in accounts), ZERO),
        portfolio_health_factor=portfolio_hf,
        worst_health_factor=worst.health_factor if worst else None,
        worst_account_key=worst.account_key if worst else None,
    )
