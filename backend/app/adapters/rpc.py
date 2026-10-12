from __future__ import annotations

import asyncio
import logging
from urllib.parse import urlparse

from web3 import AsyncWeb3, Web3

from app.adapters.codec import checksum, decode_aggregate3, encode_aggregate3
from app.registry import MULTICALL3

logger = logging.getLogger("blackout.rpc")


class RpcError(Exception):
    pass


def _host(url: str) -> str:
    return urlparse(url).netloc or "rpc"


class ChainRpc:
    """Small multi-URL client. web3.py performs the calls; Multicall3 batches them."""

    def __init__(self, name: str, urls: list[str], timeout: float, gate: asyncio.Semaphore):
        self.name = name
        self.urls = urls
        self.timeout = timeout
        self.gate = gate
        self._clients: dict[str, AsyncWeb3] = {}

    def _client(self, url: str) -> AsyncWeb3:
        client = self._clients.get(url)
        if client is None:
            client = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(url, request_kwargs={"timeout": self.timeout}))
            self._clients[url] = client
        return client

    async def stop(self) -> None:
        for client in self._clients.values():
            disconnect = getattr(client.provider, "disconnect", None)
            if disconnect is not None:
                try:
                    await disconnect()
                except Exception:
                    logger.debug("rpc disconnect failed", exc_info=True)
        self._clients.clear()

    async def eth_call(self, to: str, data: bytes) -> bytes:
        if not self.urls:
            raise RpcError(f"{self.name} has no RPC URL")
        target = checksum(to)
        payload = {"to": target, "data": data}
        last: Exception | None = None
        async with self.gate:
            for url in self.urls:
                try:
                    client = self._client(url)
                    result = await asyncio.wait_for(client.eth.call(payload), timeout=self.timeout + 2)
                    raw = bytes(result)
                    if not raw:
                        raise RpcError("empty eth_call result")
                    return raw
                except Exception as exc:
                    last = exc
                    logger.warning("%s call via %s failed: %s", self.name, _host(url), _short(exc))
        raise RpcError(f"{self.name} RPC failed: {_short(last)}")

    async def multicall(self, calls: list[tuple[str, bytes]], chunk: int = 12) -> list[tuple[bool, bytes]]:
        if not calls:
            return []
        rows: list[tuple[bool, bytes]] = []
        for start in range(0, len(calls), chunk):
            batch = calls[start : start + chunk]
            raw = await self.eth_call(MULTICALL3, encode_aggregate3(batch))
            decoded = decode_aggregate3(raw)
            if len(decoded) != len(batch):
                raise RpcError(f"{self.name} multicall length mismatch")
            rows.extend(decoded)
        return rows


def _short(exc: Exception | None) -> str:
    if exc is None:
        return "unknown error"
    text = str(exc).splitlines()[0].strip()
    return text[:180] or exc.__class__.__name__


def topic_address(address: str) -> str:
    return Web3.to_checksum_address(address.lower())
