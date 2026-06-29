"""MetaTrader5 data source — READ ONLY.

This module calls only copy_rates_* and symbol_info. It never calls order_send
or anything that mutates account state. That is a deliberate constraint of
Component 1: research touches market data, never the account.
"""

from __future__ import annotations

from datetime import datetime, timezone

from ..core.types import Bar
from ..core.instruments import get as get_instrument
from .source_base import DataSource


# MT5 timeframe name -> constant, resolved lazily so importing this module does
# not require the package to be installed (tests/CI can run without MT5).
_TIMEFRAME_NAMES = {
    "M1": "TIMEFRAME_M1", "M5": "TIMEFRAME_M5", "M15": "TIMEFRAME_M15",
    "M30": "TIMEFRAME_M30", "H1": "TIMEFRAME_H1", "H4": "TIMEFRAME_H4",
    "D1": "TIMEFRAME_D1", "W1": "TIMEFRAME_W1",
}


class MT5Source(DataSource):
    def __init__(self):
        import MetaTrader5 as mt5  # imported here so the module loads without it
        self._mt5 = mt5
        if not mt5.initialize():
            raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")

    def close(self):
        self._mt5.shutdown()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def _tf_const(self, timeframe: str):
        name = _TIMEFRAME_NAMES.get(timeframe.upper())
        if name is None:
            raise ValueError(f"unsupported timeframe: {timeframe}")
        return getattr(self._mt5, name)

    def _ensure_symbol(self, symbol: str):
        info = self._mt5.symbol_info(symbol)
        if info is None or not info.visible:
            if not self._mt5.symbol_select(symbol, True):
                raise RuntimeError(
                    f"symbol {symbol} unavailable: {self._mt5.last_error()}")
            info = self._mt5.symbol_info(symbol)
        return info

    def get_bars(self, symbol: str, timeframe: str, count: int) -> list[Bar]:
        self._ensure_symbol(symbol)
        rates = self._mt5.copy_rates_from_pos(
            symbol, self._tf_const(timeframe), 0, count)
        if rates is None or len(rates) == 0:
            raise RuntimeError(
                f"no rates for {symbol} {timeframe}: {self._mt5.last_error()}")
        return [
            Bar(
                time=datetime.fromtimestamp(int(r["time"]), tz=timezone.utc),
                open=float(r["open"]), high=float(r["high"]),
                low=float(r["low"]), close=float(r["close"]),
                volume=float(r["tick_volume"]),
            )
            for r in rates
        ]

    def get_live_spread_price(self, symbol: str) -> float | None:
        info = self._ensure_symbol(symbol)
        inst = get_instrument(symbol)
        if info is None:
            return None
        # info.spread is in points; convert to price.
        return float(info.spread) * inst.point
