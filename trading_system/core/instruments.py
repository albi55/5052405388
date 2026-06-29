"""Instrument metadata. Kept minimal for v1; expand as the universe grows."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Instrument:
    symbol: str
    point: float          # smallest price increment
    digits: int


_KNOWN = {
    "EURUSD": Instrument("EURUSD", 0.00001, 5),
    "GBPUSD": Instrument("GBPUSD", 0.00001, 5),
    "USDJPY": Instrument("USDJPY", 0.001, 3),
    "AUDUSD": Instrument("AUDUSD", 0.00001, 5),
}


def get(symbol: str) -> Instrument:
    s = symbol.upper()
    if s in _KNOWN:
        return _KNOWN[s]
    # Reasonable default for an unknown 5-digit FX-like instrument.
    return Instrument(s, 0.00001, 5)
