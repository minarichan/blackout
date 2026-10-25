from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.core.actions import suggest_action
from app.core.quotes import QUOTE_TTL_SECONDS, assemble_quote, interest_mode, repay_call, token_raw
from app.core.risk_engine import analyze
from app.demo import demo_positions
from app.models.position import Position

D = Decimal
NOW = datetime(2026, 10, 25, 20, 0, tzinfo=timezone.utc)


def _action():
    action = suggest_action(analyze(demo_positions()))
    assert action is not None
    return action


def test_demo_quote_stops_when_the_book_is_not_a_wallet():
    action = _action()
    quote = assemble_quote(action, now=NOW, balance=D("0"), demo=True)
    assert quote.status == "short"
    assert quote.slippage_bps == 0
    assert quote.shortfall == D("16000")
    assert quote.gas_units is None
    assert quote.health_after == D("1.5")
    assert "not a wallet" in quote.note
    assert datetime.fromisoformat(quote.expires_at) - NOW == timedelta(seconds=QUOTE_TTL_SECONDS)


def test_short_wallet_does_not_receive_a_gas_quote():
    action = _action()
    quote = assemble_quote(
        action,
        now=NOW,
        balance=D("1000"),
        gas_units=200_000,
        gas_price_wei=10**9,
        native_price_usd=D("3200"),
    )
    assert quote.status == "short"
    assert quote.gas_units is None
    assert quote.gas_usd is None
    assert quote.shortfall == D("15000")


def test_ready_quote_has_zero_slippage_gas_and_health_after_fill():
    action = _action()
    quote = assemble_quote(
        action,
        now=NOW,
        balance=D("20000"),
        allowance=D("20000"),
        gas_units=180_000,
        gas_price_wei=10**9,
        native_price_usd=D("3200"),
    )
    assert quote.status == "ready"
    assert quote.slippage_bps == 0
    assert quote.gas_units == 180_000
    assert quote.gas_native == D("180000") * D(10**9) / D(10**18)
    assert quote.gas_usd == quote.gas_native * D("3200")
    assert quote.health_after == D("1.5")
    assert quote.shortfall == D("0")


def test_approval_quotes_the_approval_and_stops_before_the_repay():
    action = _action()
    quote = assemble_quote(
        action,
        now=NOW,
        balance=D("20000"),
        allowance=D("0"),
        gas_units=180_000,
        approval_gas_units=46_000,
        gas_price_wei=10**9,
        native_price_usd=D("3200"),
    )
    assert quote.status == "approval"
    assert quote.gas_units == 46_000
    assert "repay is not" in quote.note


def test_aave_repay_call_targets_the_pool_and_variable_debt():
    action = _action()
    borrow = next(
        position
        for position in demo_positions()
        if position.account_key == action.account_key and position.asset == "USDC"
    )
    borrow = borrow.model_copy(update={"metadata": {"decimals": "6", "variable_debt": "60000"}})
    assert interest_mode(borrow) == 2
    call = repay_call(borrow, token_raw(D("16000"), 6), "0xd8da6bf26964af9d7eed9e03e53415d37aa96045")
    assert call is not None
    pool, data = call
    assert pool == "0x794a61358D6845594F94dc1DB02A252b5b4814aD"
    assert data[:4].hex() == "573ade81"  # repay(address,uint256,uint256,address)
    assert token_raw(D("16000"), 6) == 16_000_000_000


def test_stable_only_debt_uses_stable_interest_mode():
    position = Position(
        id="x",
        user_address="0xabc",
        chain="ethereum",
        protocol="aave-v3",
        protocol_name="Aave v3",
        market="core",
        market_name="Aave v3",
        account_key="ethereum:aave-v3:core",
        type="borrow",
        asset="USDC",
        asset_address="0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
        amount=D("1"),
        value_usd=D("1"),
        price_usd=D("1"),
        metadata={"stable_debt": "1"},
    )
    assert interest_mode(position) == 1
