from decimal import Decimal

from app.adapters.aave_v3 import ReserveState, build_aave_positions
from app.core.alerts import build_alerts
from app.core.risk_engine import analyze
from app.demo import demo_positions

D = Decimal


def _by_key(analysis, key):
    return next(account for account in analysis.accounts if account.account_key == key)


def test_single_collateral_health_and_distance():
    positions = build_aave_positions(
        user="0xabc",
        chain="ethereum",
        reserves=[
            ReserveState(
                address="0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
                symbol="WETH",
                decimals=18,
                ltv=D("0.80"),
                liquidation_threshold=D("0.80"),
                reserve_collateral_enabled=True,
                emode_category=0,
                supply_raw=10**18,
                stable_debt_raw=0,
                variable_debt_raw=0,
                usage_as_collateral=True,
                price_raw=2000 * 10**8,
            ),
            ReserveState(
                address="0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
                symbol="USDC",
                decimals=6,
                ltv=D("0"),
                liquidation_threshold=D("0"),
                reserve_collateral_enabled=False,
                emode_category=0,
                supply_raw=0,
                stable_debt_raw=0,
                variable_debt_raw=1000 * 10**6,
                usage_as_collateral=False,
                price_raw=10**8,
            ),
        ],
        base_unit=10**8,
        protocol_health=None,
        protocol_liquidation_threshold=None,
        emode=0,
        emode_label="",
        emode_ltv=None,
        emode_liquidation_threshold=None,
    )
    analysis = analyze(positions)
    account = analysis.accounts[0]
    assert account.computed_health_factor == D("1.6")
    assert account.collateral_drawdown_pct == (D("1.6") - 1) / D("1.6")
    eth = next(position for position in analysis.positions if position.asset == "WETH")
    assert eth.value_usd == D("2000")
    assert eth.liquidation_price == D("2000") * (1 - account.collateral_drawdown_pct)


def test_emode_threshold_replaces_reserve_threshold():
    positions = build_aave_positions(
        user="0xabc",
        chain="ethereum",
        reserves=[
            ReserveState(
                address="0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
                symbol="WETH",
                decimals=18,
                ltv=D("0.80"),
                liquidation_threshold=D("0.80"),
                reserve_collateral_enabled=True,
                emode_category=1,
                supply_raw=10**18,
                stable_debt_raw=0,
                variable_debt_raw=0,
                usage_as_collateral=True,
                price_raw=2000 * 10**8,
            ),
            ReserveState(
                address="0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
                symbol="USDC",
                decimals=6,
                ltv=D("0"),
                liquidation_threshold=D("0"),
                reserve_collateral_enabled=False,
                emode_category=0,
                supply_raw=0,
                stable_debt_raw=0,
                variable_debt_raw=1000 * 10**6,
                usage_as_collateral=False,
                price_raw=10**8,
            ),
        ],
        base_unit=10**8,
        protocol_health=None,
        protocol_liquidation_threshold=None,
        emode=1,
        emode_label="ETH",
        emode_ltv=D("0.90"),
        emode_liquidation_threshold=D("0.93"),
    )
    analysis = analyze(positions)
    assert analysis.accounts[0].computed_health_factor == D("2000") * D("0.93") / D("1000")


def test_protocol_health_is_the_headline_and_stress_ignores_it():
    positions = build_aave_positions(
        user="0xabc",
        chain="ethereum",
        reserves=[
            ReserveState(
                address="0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
                symbol="WETH",
                decimals=18,
                ltv=D("0.80"),
                liquidation_threshold=D("0.80"),
                reserve_collateral_enabled=True,
                emode_category=0,
                supply_raw=10**18,
                stable_debt_raw=0,
                variable_debt_raw=0,
                usage_as_collateral=True,
                price_raw=2000 * 10**8,
            ),
            ReserveState(
                address="0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
                symbol="USDC",
                decimals=6,
                ltv=D("0"),
                liquidation_threshold=D("0"),
                reserve_collateral_enabled=False,
                emode_category=0,
                supply_raw=0,
                stable_debt_raw=0,
                variable_debt_raw=1000 * 10**6,
                usage_as_collateral=False,
                price_raw=10**8,
            ),
        ],
        base_unit=10**8,
        protocol_health=D("1.05"),
        protocol_liquidation_threshold=D("0.80"),
        emode=0,
        emode_label="",
        emode_ltv=None,
        emode_liquidation_threshold=None,
    )
    analysis = analyze(positions)
    account = analysis.accounts[0]
    assert account.health_factor == D("1.05")
    assert account.computed_health_factor == D("1.6")
    shock = next(item for item in analysis.stress if item.id == "eth_minus_20")
    shocked = shock.accounts[0]
    assert shocked.health_factor == D("1.28")


def test_demo_book_flags_the_tight_long_and_the_eth_borrow():
    analysis = analyze(demo_positions())
    alerts = build_alerts(analysis)
    codes = {alert.code for alert in alerts}

    arb = _by_key(analysis, "arbitrum:aave-v3:core")
    optimism = _by_key(analysis, "optimism:aave-v3:core")
    assert analysis.worst_account_key == "arbitrum:aave-v3:core"
    assert arb.health_factor == D("66000") / D("60000")
    assert arb.primary_risk == "collateral_drawdown"
    assert optimism.health_factor == D("156000") / D("128000")
    assert optimism.primary_risk == "debt_expansion"
    assert analysis.portfolio_health_factor > arb.health_factor

    eth_down = next(item for item in analysis.stress if item.id == "eth_minus_20")
    shocked = {row.account_key: row for row in eth_down.accounts}
    assert shocked["arbitrum:aave-v3:core"].liquidatable is True
    assert shocked["arbitrum:aave-v3:core"].health_factor == D("0.88")
    assert shocked["optimism:aave-v3:core"].health_factor > optimism.health_factor

    weth_borrow = next(
        position
        for position in analysis.positions
        if position.account_key == "optimism:aave-v3:core" and position.asset == "WETH"
    )
    assert weth_borrow.liquidation_price == D("3900")
    assert "health_high" in codes
    assert "correlation_directional_short" in codes
    assert "correlation_directional_long" in codes
    assert "correlation_cross_chain" in codes
    assert "factor_concentration" in codes


def test_no_debt_has_no_health_factor():
    positions = demo_positions()
    idle = [position for position in positions if position.account_key == "base:aave-v3:core"]
    analysis = analyze(idle)
    assert analysis.accounts[0].health_factor is None
    assert build_alerts(analysis) == []
