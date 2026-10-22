from decimal import Decimal

from app.adapters.aave_v3 import ReserveState, build_aave_positions
from app.core.actions import suggest_action
from app.core.risk_engine import analyze
from app.demo import demo_positions

D = Decimal


def test_demo_book_repays_usdc_on_the_tight_arbitrum_account():
    action = suggest_action(analyze(demo_positions()))
    assert action is not None
    assert action.kind == "repay"
    assert action.account_key == "arbitrum:aave-v3:core"
    assert action.asset == "USDC"
    assert action.amount == D("16000")
    assert action.amount_usd == D("16000")
    assert action.health_before == D("1.1")
    assert action.health_after == D("1.5")
    assert action.worst_before == D("1.1")
    assert action.worst_after == D("156000") / D("128000")
    assert action.worst_after_account_key == "optimism:aave-v3:core"


def test_repay_is_withheld_when_health_is_already_above_the_buffer():
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
    assert suggest_action(analyze(positions), target=D("1.5")) is None


def test_repay_scales_aave_reported_health_with_debt():
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
    action = suggest_action(analyze(positions))
    assert action is not None
    assert action.health_before == D("1.05")
    assert action.amount_usd == D("1000") * (1 - D("1.05") / D("1.5"))
    assert action.health_after == D("1.5")


def test_eth_borrow_is_repaid_when_that_account_is_the_worst():
    positions = [position for position in demo_positions() if position.account_key == "optimism:aave-v3:core"]
    action = suggest_action(analyze(positions))
    assert action is not None
    assert action.asset == "WETH"
    assert action.amount == D("7.5")
    assert action.health_after == D("1.5")


def test_no_suggestion_without_debt():
    idle = [position for position in demo_positions() if position.account_key == "base:aave-v3:core"]
    assert suggest_action(analyze(idle)) is None
