"""One risk-reducing move. Nothing here is signed or sent."""

from __future__ import annotations

from decimal import Decimal

from app.core.assets import is_volatile
from app.models.position import Position
from app.models.risk import AccountRisk, Analysis, SuggestedAction

ZERO = Decimal("0")
DEFAULT_TARGET = Decimal("1.5")
MIN_REPAY_USD = Decimal("1")


def suggest_action(analysis: Analysis, target: Decimal = DEFAULT_TARGET) -> SuggestedAction | None:
    """Repay the borrow on the worst account until its health reaches `target`.

    The repay is sized from the account health already on the desk, which scales
    with 1 / debt when collateral stays put. Withdrawing collateral lowers health,
    so it is never the suggestion. A repay that leaves some other account equally
    close to liquidation is dropped, because the book's worst health would not move.
    """
    if target <= Decimal("1"):
        return None
    worst = _worst(analysis)
    if worst is None or worst.health_factor is None or worst.debt_usd <= ZERO:
        return None
    if worst.health_factor >= target:
        return None

    borrow = _choose_borrow(analysis.positions, worst)
    if borrow is None:
        return None

    remaining_debt = worst.debt_usd * worst.health_factor / target
    needed = worst.debt_usd - remaining_debt
    repay = min(needed, borrow.value_usd)
    if repay < MIN_REPAY_USD or borrow.price_usd <= ZERO:
        return None

    debt_left = worst.debt_usd - repay
    health_after = None if debt_left <= ZERO else worst.health_factor * worst.debt_usd / debt_left
    worst_before = analysis.worst_health_factor
    if worst_before is None:
        return None
    worst_after, worst_after_account = _book_worst_after(analysis, worst.account_key, health_after)
    if not _improves(worst_before, worst_after):
        return None

    return SuggestedAction(
        kind="repay",
        account_key=worst.account_key,
        chain=worst.chain,
        protocol_name=worst.protocol_name,
        market_name=worst.market_name,
        asset=borrow.asset,
        amount=repay / borrow.price_usd,
        amount_usd=repay,
        target_health=target,
        health_before=worst.health_factor,
        health_after=health_after,
        worst_before=worst_before,
        worst_after=worst_after,
        worst_after_account_key=None if worst_after_account is None else worst_after_account.account_key,
        worst_after_chain=None if worst_after_account is None else worst_after_account.chain,
        worst_after_market_name=None if worst_after_account is None else worst_after_account.market_name,
    )


def _worst(analysis: Analysis) -> AccountRisk | None:
    if analysis.worst_account_key is None:
        return None
    return next((account for account in analysis.accounts if account.account_key == analysis.worst_account_key), None)


def _choose_borrow(positions: list[Position], account: AccountRisk) -> Position | None:
    borrows = [
        position
        for position in positions
        if position.account_key == account.account_key and position.type == "borrow" and position.value_usd > ZERO
    ]
    if not borrows:
        return None
    if account.primary_risk == "debt_expansion":
        volatile = [position for position in borrows if is_volatile(position.asset)]
        if volatile:
            return max(volatile, key=lambda position: position.value_usd)
    return max(borrows, key=lambda position: position.value_usd)


def _book_worst_after(
    analysis: Analysis,
    acted_key: str,
    health_after: Decimal | None,
) -> tuple[Decimal | None, AccountRisk | None]:
    best: Decimal | None = None
    holder: AccountRisk | None = None
    for account in analysis.accounts:
        if account.health_factor is None or account.debt_usd <= ZERO:
            continue
        health = health_after if account.account_key == acted_key else account.health_factor
        if health is None:
            continue
        if best is None or health < best:
            best = health
            holder = account
    return best, holder


def _improves(before: Decimal, after: Decimal | None) -> bool:
    if after is None:
        return True
    return after > before
