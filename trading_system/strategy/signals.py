"""Entry signals — price and non-price — behind a common interface.

A signal turns bar arrays + params into a boolean entry array `enter[i]`, meaning
"the entry condition is TRUE as of bar i's close". The backtest engine then fills
on bar i+1's open (no look-ahead). Non-price signals (rate_differential) take an
optional external series through the same interface, so carry-style strategies
slot in without touching the engine.
"""

from __future__ import annotations

import numpy as np

from . import indicators as ind


def entry_signal(spec_entry, bars_arr: dict, direction: int,
                 external: np.ndarray | None = None) -> np.ndarray:
    """Dispatch on spec_entry.type. Returns a boolean np.ndarray aligned to bars.
    bars_arr provides 'open','high','low','close' as numpy arrays."""
    t = spec_entry.type
    p = spec_entry.params
    close = bars_arr["close"]
    n = len(close)
    enter = np.zeros(n, dtype=bool)

    if t == "sma_discount":
        period = int(p.get("period", 20))
        discount = float(p.get("discount", 0.01))
        m = ind.sma(close, period)
        thresh = m * (1.0 - discount) if direction >= 0 else m * (1.0 + discount)
        valid = np.isfinite(m)
        if direction >= 0:
            enter = valid & (close <= thresh)
        else:
            enter = valid & (close >= thresh)

    elif t == "zscore":
        period = int(p.get("period", 20))
        k = float(p.get("k", 2.0))
        z = ind.zscore(close, period)
        valid = np.isfinite(z)
        # long when far BELOW mean (z <= -k); short when far above (z >= +k)
        enter = valid & (z <= -k) if direction >= 0 else valid & (z >= k)

    elif t == "rsi":
        period = int(p.get("period", 14))
        level = float(p.get("level", 30.0))
        r = ind.rsi(close, period)
        valid = np.isfinite(r)
        enter = valid & (r <= level) if direction >= 0 else valid & (r >= (100.0 - level))

    elif t == "breakout":
        period = int(p.get("period", 20))
        if direction >= 0:
            hi = ind.rolling_high(bars_arr["high"], period)
            enter = np.isfinite(hi) & (close > hi)
        else:
            lo = ind.rolling_low(bars_arr["low"], period)
            enter = np.isfinite(lo) & (close < lo)

    elif t == "rate_differential":
        # Non-price signal: enter long when carry (external series) exceeds a
        # threshold. Source is pluggable; if no series supplied, no entries.
        level = float(p.get("level", 0.0))
        if external is not None and len(external) == n:
            valid = np.isfinite(external)
            enter = valid & (external >= level) if direction >= 0 else valid & (external <= -level)

    else:
        raise ValueError(f"unknown entry signal type: {t}")

    return enter
