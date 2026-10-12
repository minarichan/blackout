from dataclasses import dataclass


@dataclass(frozen=True)
class AaveDeployment:
    pool: str
    oracle: str
    data_provider: str
    pool_addresses_provider: str


@dataclass(frozen=True)
class CompoundMarket:
    market_id: str
    name: str
    comet: str


@dataclass(frozen=True)
class ChainConfig:
    key: str
    name: str
    chain_id: int
    default_rpcs: tuple[str, ...]
    aave: AaveDeployment
    compound: tuple[CompoundMarket, ...]


# Addresses from the Aave address book and Compound Comet deployment roots.
CHAINS: dict[str, ChainConfig] = {
    "ethereum": ChainConfig(
        key="ethereum",
        name="Ethereum",
        chain_id=1,
        default_rpcs=(
            "https://ethereum.publicnode.com",
            "https://eth.drpc.org",
            "https://rpc.ankr.com/eth",
        ),
        aave=AaveDeployment(
            pool="0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2",
            oracle="0x54586bE62E3c3580375aE3723C145253060Ca0C2",
            data_provider="0x0a16f2FCC0D44FaE41cc54e079281D84A363bECD",
            pool_addresses_provider="0x2f39d218133AFaB8F2B819B1066c7E434Ad94E9e",
        ),
        compound=(
            CompoundMarket("usdc", "USDC", "0xc3d688B66703497DAA19211EEdff47f25384cdc3"),
            CompoundMarket("weth", "WETH", "0xA17581A9E3356d9A858b789D68B4d866e593aE94"),
            CompoundMarket("usdt", "USDT", "0x3Afdc9BCA9213A35503b077a6072F3D0d5AB0840"),
            CompoundMarket("usds", "USDS", "0x5D409e56D886231aDAf00c8775665AD0f9897b56"),
        ),
    ),
    "arbitrum": ChainConfig(
        key="arbitrum",
        name="Arbitrum",
        chain_id=42161,
        default_rpcs=(
            "https://arbitrum-one.publicnode.com",
            "https://arb1.arbitrum.io/rpc",
        ),
        aave=AaveDeployment(
            pool="0x794a61358D6845594F94dc1DB02A252b5b4814aD",
            oracle="0xb56c2F0B653B2e0b10C9b928C8580Ac5Df02C7C7",
            data_provider="0x243Aa95cAC2a25651eda86e80bEe66114413c43b",
            pool_addresses_provider="0xa97684ead0e402dC232d5A977953DF7ECBaB3CDb",
        ),
        compound=(
            CompoundMarket("usdc.e", "USDC.e", "0xA5EDBDD9646f8dFF606d7448e414884C7d905dCA"),
            CompoundMarket("usdc", "USDC", "0x9c4ec768c28520B50860ea7a15bd7213a9fF58bf"),
            CompoundMarket("weth", "WETH", "0x6f7D514bbD4aFf3BcD1140B7344b32f063dEe486"),
        ),
    ),
    "base": ChainConfig(
        key="base",
        name="Base",
        chain_id=8453,
        default_rpcs=(
            "https://base.publicnode.com",
            "https://mainnet.base.org",
        ),
        aave=AaveDeployment(
            pool="0xA238Dd80C259a72e81d7e4664a9801593F98d1c5",
            oracle="0x2Cc0Fc26eD4563A5ce5e8bdcfe1A2878676Ae156",
            data_provider="0x0F43731EB8d45A581f4a36DD74F5f358bc90C73A",
            pool_addresses_provider="0xe20fCBdBfFC4Dd138cE8b2E6FBb6CB49777ad64D",
        ),
        compound=(
            CompoundMarket("usdc", "USDC", "0xb125E6687d4313864e53df431d5425969c15Eb2F"),
            CompoundMarket("usdbc", "USDbC", "0x9c4ec768c28520B50860ea7a15bd7213a9fF58bf"),
            CompoundMarket("weth", "WETH", "0x46e6b214b524310239732D51387075E0e70970bf"),
        ),
    ),
    "optimism": ChainConfig(
        key="optimism",
        name="Optimism",
        chain_id=10,
        default_rpcs=(
            "https://optimism.publicnode.com",
            "https://mainnet.optimism.io",
        ),
        aave=AaveDeployment(
            pool="0x794a61358D6845594F94dc1DB02A252b5b4814aD",
            oracle="0xD81eb3728a631871a7eBBaD631b5f424909f0c77",
            data_provider="0x243Aa95cAC2a25651eda86e80bEe66114413c43b",
            pool_addresses_provider="0xa97684ead0e402dC232d5A977953DF7ECBaB3CDb",
        ),
        compound=(
            CompoundMarket("usdc", "USDC", "0x2e44e174f7D53F0212823acC11C01A11d58c5bCB"),
            CompoundMarket("usdt", "USDT", "0x995E394b8B2437aC8Ce61Ee0bC610D617962B214"),
            CompoundMarket("weth", "WETH", "0xE36A30D249f7761327fd973001A32010b521b6Fd"),
        ),
    ),
}

CHAINLINK_USD = {
    "ETH": "0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419",
    "BTC": "0xF4030086522a5bEEa4988F8cA5B36dbC97BeE88c",
}

PROTOCOL_NAMES = {
    "aave-v3": "Aave v3",
    "compound-v3": "Compound v3",
}

MULTICALL3 = "0xcA11bde05977b3631167028862bE2a173976CA11"


def chain_configs(enabled: list[str]) -> list[ChainConfig]:
    unknown = [key for key in enabled if key not in CHAINS]
    if unknown:
        raise ValueError(f"Unknown chain: {', '.join(unknown)}")
    return [CHAINS[key] for key in enabled]


def protocols_payload(enabled: list[str]) -> dict:
    chains = chain_configs(enabled)
    return {
        "chains": [
            {"id": chain.key, "name": chain.name, "chain_id": chain.chain_id}
            for chain in chains
        ],
        "protocols": [
            {
                "id": "aave-v3",
                "name": "Aave v3",
                "kind": "lending",
                "chains": [chain.key for chain in chains],
            },
            {
                "id": "compound-v3",
                "name": "Compound v3",
                "kind": "lending",
                "chains": [chain.key for chain in chains],
                "markets": {
                    chain.key: [market.name for market in chain.compound] for chain in chains
                },
            },
        ],
    }
