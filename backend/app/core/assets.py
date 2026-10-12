from __future__ import annotations

from decimal import Decimal

ETH_ASSETS = {
    "ETH",
    "WETH",
    "WSTETH",
    "WEETH",
    "RETH",
    "CBETH",
    "EZETH",
    "RSETH",
    "WRSETH",
    "ETHX",
    "OSETH",
    "METH",
    "SWETH",
    "FRXETH",
    "SFRXETH",
    "ANKRETH",
    "RSWETH",
    "TETH",
    "WOETH",
    "RSETH",
    "WSTETH",
    "WEETHS",
}

BTC_ASSETS = {"WBTC", "CBBTC", "TBTC", "LBTC", "EBTC", "FBTC", "BTCB"}

USDC_ASSETS = {"USDC", "USDBC", "USDCE"}

STABLE_ASSETS = {
    "USDT",
    "DAI",
    "USDS",
    "GHO",
    "CRVUSD",
    "FRAX",
    "LUSD",
    "PYUSD",
    "USDM",
    "GUSD",
    "TUSD",
    "SDAI",
    "SUSDS",
    "USD0",
    "EURC",
    "USDB",
}

SOFT_STABLE_ASSETS = {"SUSDE", "USDE"}

COINGECKO_IDS = {
    "ETH": "ethereum",
    "WETH": "ethereum",
    "WBTC": "wrapped-bitcoin",
    "CBBTC": "coinbase-wrapped-btc",
    "TBTC": "tbtc",
    "USDC": "usd-coin",
    "USDT": "tether",
    "DAI": "dai",
    "WSTETH": "wrapped-steth",
    "CBETH": "coinbase-wrapped-staked-eth",
    "RETH": "rocket-pool-eth",
    "WEETH": "wrapped-eeth",
    "LINK": "chainlink",
    "AAVE": "aave",
    "ARB": "arbitrum",
    "OP": "optimism",
    "AERO": "aerodrome-finance",
    "GHO": "gho",
    "USDS": "usds",
    "EZETH": "renzo-restaked-eth",
    "RSETH": "kelp-dao-restaked-eth",
    "USDBC": "bridged-usd-coin-base",
}


def canonical_symbol(symbol: str) -> str:
    cleaned = symbol.strip().upper().replace(" ", "")
    if cleaned.endswith(".E"):
        cleaned = cleaned[:-2] + "E"
    return cleaned.replace(".", "")


def factor_bucket(symbol: str) -> str:
    token = canonical_symbol(symbol)
    if token in USDC_ASSETS:
        return "usdc"
    if token in SOFT_STABLE_ASSETS:
        return "soft_stable"
    if token in STABLE_ASSETS or "USD" in token:
        return "stable"
    if token in BTC_ASSETS or token.endswith("BTC"):
        return "btc"
    if token in ETH_ASSETS or token == "ETH" or token.endswith("ETH"):
        return "eth"
    return "alt"


def reference_asset(symbol: str) -> str | None:
    """Map a token to ETH, BTC, or a $1 peg for oracle cross-checks.

    Liquid staking tokens are not compared with spot ETH. Their premium would
    look like an oracle break.
    """
    token = canonical_symbol(symbol)
    if token in {"ETH", "WETH"}:
        return "ETH"
    if token in {"WBTC", "CBBTC"}:
        return "BTC"
    if factor_bucket(symbol) in {"usdc", "stable"}:
        return "USD"
    return None


def is_volatile(symbol: str) -> bool:
    return factor_bucket(symbol) in {"eth", "btc", "alt", "soft_stable"}


def shock_weight(symbol: str) -> Decimal:
    bucket = factor_bucket(symbol)
    if bucket == "soft_stable":
        return Decimal("0.5")
    if bucket in {"eth", "btc", "alt"}:
        return Decimal("1")
    return Decimal("0")
