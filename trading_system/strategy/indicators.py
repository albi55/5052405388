"""Vectorized indicators. Each returns a numpy array aligned to the input, with
NaN during the warm-up period. Aligned means indicator[i] uses ONLY data up to
and including bar i — never future data. This no-lookahead alignment is asserted
in tests/test_no_lookahead.py.
"""

from __future__ import annotations

import numpy as np


def sma(close: np.ndarray, period: int) -> np.ndarray:
    out = np.full_like(close, np.nan, dtype=float)
    if period <= 0 or len(close) < period:
        return out
    csum = np.cumsum(np.insert(close, 0, 0.0))
    out[period - 1:] = (csum[period:] - csum[:-period]) / period
    return out


def rolling_std(close: np.ndarray, period: int) -> np.ndarray:
    out = np.full_like(close, np.nan, dtype=float)
    if period <= 1 or len(close) < period:
        return out
    for i in range(period - 1, len(close)):
        out[i] = close[i - period + 1:i + 1].std(ddof=1)
    return out


def zscore(close: np.ndarray, period: int) -> np.ndarray:
    """(close - rolling_mean) / rolling_std. Negative = below the mean."""
    m = sma(close, period)
    s = rolling_std(close, period)
    with np.errstate(invalid="ignore", divide="ignore"):
        return (close - m) / s


def rsi(close: np.ndarray, period: int = 14) -> np.ndarray:
    out = np.full_like(close, np.nan, dtype=float)
    if len(close) <= period:
        return out
    delta = np.diff(close)
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    avg_gain = gain[:period].mean()
    avg_loss = loss[:period].mean()
    for i in range(period, len(close)):
        if i > period:
            avg_gain = (avg_gain * (period - 1) + gain[i - 1]) / period
            avg_loss = (avg_loss * (period - 1) + loss[i - 1]) / period
        rs = avg_gain / avg_loss if avg_loss > 0 else np.inf
        out[i] = 100.0 - 100.0 / (1.0 + rs)
    return out


def atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    """Wilder ATR. atr[i] uses true range up to and including i."""
    n = len(close)
    out = np.full(n, np.nan, dtype=float)
    if n <= period:
        return out
    tr = np.empty(n)
    tr[0] = high[0] - low[0]
    for i in range(1, n):
        pc = close[i - 1]
        tr[i] = max(high[i] - low[i], abs(high[i] - pc), abs(low[i] - pc))
    seed = tr[1:period + 1].mean()
    out[period] = seed
    for i in range(period + 1, n):
        out[i] = (out[i - 1] * (period - 1) + tr[i]) / period
    return out


def rolling_high(high: np.ndarray, period: int) -> np.ndarray:
    """Highest high over the prior `period` bars, EXCLUDING the current bar, so a
    breakout compares today's close to a level formed strictly in the past."""
    out = np.full_like(high, np.nan, dtype=float)
    for i in range(period, len(high)):
        out[i] = high[i - period:i].max()
    return out


def rolling_low(low: np.ndarray, period: int) -> np.ndarray:
    out = np.full_like(low, np.nan, dtype=float)
    for i in range(period, len(low)):
        out[i] = low[i - period:i].min()
    return out
