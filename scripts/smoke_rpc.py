import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.adapters.codec import decode_address, decode_types, encode_call
from app.config import get_settings
from app.db.session import init_db
from app.services.portfolio_service import PortfolioService


async def main() -> None:
    settings = get_settings()
    init_db(settings)
    service = PortfolioService(settings)
    try:
        for chain in service.chains:
            rpc = service.rpcs[chain.key]
            reserves = decode_types(
                ["address[]"],
                await rpc.eth_call(chain.aave.pool, encode_call("getReservesList()")),
            )[0]
            comet = chain.compound[0]
            base = decode_address(await rpc.eth_call(comet.comet, encode_call("baseToken()")))
            print(f"{chain.key}: aave reserves={len(reserves)} compound {comet.name} base={base}")
    finally:
        await service.stop()


if __name__ == "__main__":
    asyncio.run(main())
