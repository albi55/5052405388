"""Shared test helpers: synthetic bar generators so tests run with no MT5."""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

from ..core.types import Bar


def make_bars(closes, start="2020-01-01"):
    """Build daily Bars from a list of closes. OHLC derived simply but validly
    (high/low bracket open/close)."""
    t0 = datetime.fromisoformat(start).replace(tzinfo=timezone.utc)
    bars = []
    prev = closes[0]
    for i, c in enumerate(closes):
        o = prev
        hi = max(o, c) * 1.001
        lo = min(o, c) * 0.999
        bars.append(Bar(time=t0 + timedelta(days=i), open=o, high=hi, low=lo, close=c))
        prev = c
    return bars


def sine_closes(n=600, base=1.10, amp=0.03, period=40):
    """Oscillating series — genuinely mean-reverting, so a dip strategy SHOULD
    show an in-sample edge here (useful to test the pipeline end to end)."""
    return [base + amp * math.sin(2 * math.pi * i / period) for i in range(n)]


def trending_closes(n=600, base=1.10, drift=0.0005):
    return [base * (1 + drift) ** i for i in range(n)]
