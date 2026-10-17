from decimal import Decimal

from app.adapters.prices import apply_price, chainlink_usd
from app.models.position import Position

D = Decimal


def _position(**overrides) -> Position:
    fields = {
        "id": "ethereum:aave-v3:core:supply:0xweth",
        "user_address": "0xabc",
        "chain": "ethereum",
        "protocol": "aave-v3",
        "protocol_name": "Aave v3",
        "market": "core",
        "market_name": "Aave v3",
        "account_key": "ethereum:aave-v3:core",
        "type": "supply",
        "asset": "WETH",
        "asset_address": "0xweth",
        "amount": D("1"),
        "value_usd": D("3200"),
        "price_usd": D("3200"),
        "usage_as_collateral": True,
        "price_source": "aave_oracle",
    }
    fields.update(overrides)
    return Position(**fields)


def test_close_protocol_price_keeps_the_oracle_and_records_the_gap():
    marked, alert = apply_price(_position(), reference=D("3180"))
    assert marked.price_usd == D("3200")
    assert marked.price_source == "aave_oracle"
    assert marked.price_status == "protocol"
    assert marked.reference_price_usd == D("3180")
    assert marked.price_gap == (D("3200") - D("3180")) / D("3180")
    assert alert is None


def test_large_eth_gap_is_divergent_and_still_uses_the_protocol_price():
    marked, alert = apply_price(_position(price_usd=D("3600"), value_usd=D("3600")), reference=D("3200"))
    assert marked.price_usd == D("3600")
    assert marked.price_status == "divergent"
    assert alert is not None
    assert alert.code == "oracle_divergence"
    assert alert.severity == "high"


def test_stable_peg_uses_the_tighter_band():
    marked, alert = apply_price(
        _position(asset="USDC", price_usd=D("0.97"), value_usd=D("970"), amount=D("1000")),
        reference=D("1"),
    )
    assert marked.price_status == "divergent"
    assert alert is not None
    assert alert.severity == "elevated"


def test_lst_is_not_compared_with_spot_eth():
    marked, alert = apply_price(_position(asset="wstETH", price_usd=D("3700"), value_usd=D("3700")), reference=None)
    assert marked.price_status == "protocol"
    assert marked.reference_price_usd is None
    assert alert is None


def test_missing_oracle_is_filled_and_marked_fallback():
    marked, alert = apply_price(
        _position(price_usd=D("0"), value_usd=D("0"), type="borrow", usage_as_collateral=False),
        reference=D("3200"),
        fill=D("3200"),
        fill_source="chainlink",
    )
    assert marked.price_usd == D("3200")
    assert marked.value_usd == D("3200")
    assert marked.price_source == "chainlink"
    assert marked.price_status == "fallback"
    assert alert is not None
    assert alert.code == "price_fallback"


def test_missing_price_with_no_fill_stays_unpriced():
    marked, alert = apply_price(
        _position(price_usd=D("0"), value_usd=D("0")),
        reference=None,
    )
    assert marked.price_usd == D("0")
    assert marked.price_status == "unpriced"
    assert alert is not None
    assert alert.code == "price_missing"


def test_idle_supply_without_a_price_does_not_alert():
    marked, alert = apply_price(
        _position(price_usd=D("0"), value_usd=D("0"), usage_as_collateral=False),
        reference=None,
    )
    assert marked.price_status == "unpriced"
    assert alert is None


def test_stale_chainlink_round_is_dropped():
    now = 1_700_000_000
    assert chainlink_usd(3200 * 10**8, now - 86_401, now) is None
    assert chainlink_usd(0, now, now) is None
    assert chainlink_usd(3200 * 10**8, now - 60, now) == D("3200")
