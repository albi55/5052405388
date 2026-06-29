"""Abstract data source. MT5 is the first implementation; rate-differential and
other macro sources slot in behind this same interface later. Keeping the engine
dependent on DataSource (not MetaTrader5 directly) is what makes the data layer
swappable and testable without a live terminal.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..core.types import Bar


class DataSource(ABC):
    """A read-only source of historical bars. Implementations MUST NOT place
    orders or mutate any account state."""

    @abstractmethod
    def get_bars(self, symbol: str, timeframe: str, count: int) -> list[Bar]:
        """Return up to `count` most-recent bars, oldest-first."""
        raise NotImplementedError

    @abstractmethod
    def get_live_spread_price(self, symbol: str) -> float | None:
        """Current spread in PRICE units, or None if unavailable. May be 0.0 when
        the market is closed — the cost layer floors it, so that's safe."""
        raise NotImplementedError
