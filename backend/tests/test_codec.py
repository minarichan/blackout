from app.adapters.codec import decode_symbol, encode_aggregate3, encode_call, selector
from eth_abi import decode

from app.adapters.compound_v3 import quote


def test_aggregate3_selector_and_roundtrip():
    assert selector("aggregate3((address,bool,bytes)[])").hex() == "82ad56cb"
    inner = encode_call("getReservesList()")
    target = "0x" + "11" * 20
    payload = encode_aggregate3([(target, inner)])
    decoded = decode(["(address,bool,bytes)[]"], payload[4:])
    assert decoded[0][0][1] is True
    assert decoded[0][0][2] == inner


def test_bytes32_symbol():
    assert decode_symbol(b"MKR".ljust(32, b"\x00")) == "MKR"


def test_compound_quote():
    amount, price, value = quote(10**18, 3200 * 10**8, 10**18)
    assert amount == 1
    assert price == 3200
    assert value == 3200
