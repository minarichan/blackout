from decimal import Decimal

from app.models.position import Position

ZERO = Decimal("0")


def position_id(position: Position) -> str:
    return ":".join(
        [
            position.chain,
            position.protocol,
            position.market,
            position.type,
            position.asset_address.lower(),
        ]
    )


def clean(positions: list[Position], min_usd: Decimal) -> list[Position]:
    kept: list[Position] = []
    for position in positions:
        if position.amount <= ZERO:
            continue
        if position.price_usd > ZERO and position.value_usd < min_usd:
            continue
        symbol = position.asset.strip()
        updated = position.model_copy(
            update={
                "id": position_id(position),
                "asset": symbol or "UNKNOWN",
                "user_address": position.user_address,
            }
        )
        kept.append(updated)
    return kept
