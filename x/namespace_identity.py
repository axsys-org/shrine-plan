"""Canonical Shrine x-aura identity parsing for local launchers."""
import re


def parse_node_identity(spelling):
    if not re.fullmatch(r"0x(?:[0-9a-f]{2})+", spelling):
        raise ValueError("node must use canonical Shrine hex: 0x followed by lowercase whole bytes")
    payload = bytes.fromhex(spelling[2:])
    number = int.from_bytes(payload, "little")
    if not number:
        raise ValueError("node public-key hash must be nonzero")
    canonical = "0x" + number.to_bytes((number.bit_length() + 7) // 8, "little").hex()
    if spelling != canonical:
        raise ValueError("node must use canonical Shrine hex without trailing zero bytes")
    return number, canonical
