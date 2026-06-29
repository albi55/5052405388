"""Local cache of fetched bars, with force-refresh.

Cached as compact JSON keyed by (symbol, timeframe, count). Keeps repeated
research runs fast and lets you work offline once data is pulled. Caching is
intentionally simple for v1; parquet/db can replace this behind the same API.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from ..config.settings import DATA_CACHE_DIR
from ..core.types import Bar
from .source_base import DataSource
from .validation import validate_bars


def _key(symbol: str, timeframe: str, count: int) -> str:
    return f"{symbol.upper()}_{timeframe.upper()}_{count}.json"


def _path(symbol: str, timeframe: str, count: int):
    return DATA_CACHE_DIR / _key(symbol, timeframe, count)


def _serialize(bars: list[Bar]) -> str:
    return json.dumps([
        {"t": b.time.isoformat(), "o": b.open, "h": b.high,
         "l": b.low, "c": b.close, "v": b.volume}
        for b in bars
    ])


def _deserialize(text: str) -> list[Bar]:
    raw = json.loads(text)
    return [
        Bar(time=datetime.fromisoformat(r["t"]), open=r["o"], high=r["h"],
            low=r["l"], close=r["c"], volume=r["v"])
        for r in raw
    ]


def load_bars(
    source: DataSource,
    symbol: str,
    timeframe: str,
    count: int,
    force_refresh: bool = False,
    warn=print,
) -> tuple[list[Bar], list[str]]:
    """Return (bars, warnings). Uses cache unless force_refresh. Always runs
    validation and surfaces warnings via `warn` so anomalies are never silent."""
    p = _path(symbol, timeframe, count)
    if p.exists() and not force_refresh:
        bars = _deserialize(p.read_text())
    else:
        bars = source.get_bars(symbol, timeframe, count)
        p.write_text(_serialize(bars))

    warnings = validate_bars(bars, timeframe)
    for w in warnings:
        warn(f"[data warning] {symbol} {timeframe}: {w}")
    return bars, warnings
