from __future__ import annotations

from eth_abi import decode, encode
from eth_utils import function_signature_to_4byte_selector
from web3 import Web3


class DecodeError(Exception):
    pass


def checksum(address: str) -> str:
    return Web3.to_checksum_address(address.lower())


def selector(signature: str) -> bytes:
    return function_signature_to_4byte_selector(signature)


def encode_call(signature: str, types: list[str] | None = None, args: list | None = None) -> bytes:
    payload = selector(signature)
    if types:
        payload += encode(types, args or [])
    return payload


def decode_types(types: list[str], data: bytes):
    if not data:
        raise DecodeError("empty return data")
    try:
        return decode(types, data)
    except Exception as exc:  # eth_abi raises several decode errors
        raise DecodeError(str(exc)) from exc


def decode_address(data: bytes) -> str:
    return checksum(decode_types(["address"], data)[0])


def decode_symbol(data: bytes) -> str:
    if not data:
        return "UNKNOWN"
    if len(data) == 32:
        raw = data.rstrip(b"\x00")
        text = raw.decode("utf-8", errors="ignore").strip()
        return text or "UNKNOWN"
    try:
        text = decode(["string"], data)[0].strip()
        return text or "UNKNOWN"
    except Exception:
        raw = data.rstrip(b"\x00")
        text = raw.decode("utf-8", errors="ignore").strip("\x00").strip()
        return text or "UNKNOWN"


def encode_aggregate3(calls: list[tuple[str, bytes]]) -> bytes:
    payload = [(checksum(target), True, data) for target, data in calls]
    return encode_call("aggregate3((address,bool,bytes)[])", ["(address,bool,bytes)[]"], [payload])


def decode_aggregate3(data: bytes) -> list[tuple[bool, bytes]]:
    rows = decode_types(["(bool,bytes)[]"], data)[0]
    return [(bool(ok), bytes(raw)) for ok, raw in rows]
