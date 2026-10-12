from __future__ import annotations

import asyncio

from app.adapters.aave_v3 import AaveV3Adapter
from app.adapters.base import AdapterResult
from app.adapters.compound_v3 import CompoundV3Adapter
from app.adapters.rpc import ChainRpc
from app.registry import ChainConfig


class IngestionService:
    def __init__(
        self,
        chains: list[ChainConfig],
        aave: AaveV3Adapter,
        compound: CompoundV3Adapter,
    ):
        self.chains = chains
        self.aave = aave
        self.compound = compound

    async def collect(self, user: str) -> list[AdapterResult]:
        tasks = []
        for chain in self.chains:
            tasks.append(self.aave.fetch(chain, user))
            tasks.append(self.compound.fetch(chain, user))
        results = await asyncio.gather(*tasks)
        return list(results)


def build_rpcs(chains: list[ChainConfig], overrides, timeout: float, gate: asyncio.Semaphore) -> dict[str, ChainRpc]:
    clients: dict[str, ChainRpc] = {}
    for chain in chains:
        urls = overrides(chain.key) or list(chain.default_rpcs)
        clients[chain.key] = ChainRpc(chain.key, urls, timeout, gate)
    return clients
