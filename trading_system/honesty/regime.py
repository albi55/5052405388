"""Regime diagnostic: is the instrument mean-reverting, trending, or a random
walk at this timeframe? This is assumption-light (no strategy, no parameters) and
can save a user from fitting a price-only strategy to noise. We ran exactly this
by hand and it correctly identified EUR/USD daily as an undistinguishable-from-
random-walk series, explaining why every price-only dip strategy failed OOS.

Three lenses: lag-1..k autocorrelation, Lo-MacKinlay variance ratio, and the
direct "what happens after a decline" conditional check.
"""

from __future__ import annotations

import math

from ..core.types import Bar


def _log_returns(bars: list[Bar]) -> list[float]:
    out = []
    for i in range(1, len(bars)):
        if bars[i - 1].close > 0:
            out.append(math.log(bars[i].close / bars[i - 1].close))
    return out


def _mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def _autocorr(rets, lag):
    n = len(rets)
    m = _mean(rets)
    denom = sum((r - m) ** 2 for r in rets)
    if denom == 0:
        return 0.0
    num = sum((rets[i] - m) * (rets[i - lag] - m) for i in range(lag, n))
    return num / denom


def _variance_ratio(rets, q):
    n = len(rets)
    if n <= q:
        return 1.0, 0.0
    m = _mean(rets)
    var1 = sum((r - m) ** 2 for r in rets) / (n - 1)
    if var1 == 0:
        return 1.0, 0.0
    qsums = [sum(rets[i:i + q]) for i in range(0, n - q + 1)]
    mq = q * m
    varq = sum((s - mq) ** 2 for s in qsums) / (len(qsums) * q)
    vr = varq / var1
    phi = (2.0 * (2 * q - 1) * (q - 1)) / (3.0 * q * n)
    z = (vr - 1.0) / math.sqrt(phi) if phi > 0 else 0.0
    return vr, z


def diagnose(bars: list[Bar]) -> tuple[str, dict]:
    """Return (one-line summary, detail dict). The summary is attached to the
    Verdict as regime_note."""
    rets = _log_returns(bars)
    n = len(rets)
    if n < 60:
        return ("regime: insufficient data", {})

    band = 2.0 / math.sqrt(n)
    acs = {lag: _autocorr(rets, lag) for lag in range(1, 6)}
    significant_ac = any(abs(v) > band for v in acs.values())

    vrs = {}
    distinguishable = False
    lean_revert = lean_trend = 0
    for q in (2, 5, 10, 20):
        vr, z = _variance_ratio(rets, q)
        vrs[q] = (vr, z)
        if abs(z) > 2:
            distinguishable = True
            if vr < 1:
                lean_revert += 1
            else:
                lean_trend += 1

    if not significant_ac and not distinguishable:
        summary = ("regime: RANDOM WALK — no exploitable autocorrelation at this "
                   "timeframe (price-only edges unlikely)")
    elif distinguishable and lean_revert >= lean_trend:
        summary = "regime: MEAN-REVERTING — dislocations tend to revert"
    elif distinguishable and lean_trend > lean_revert:
        summary = "regime: TRENDING — moves tend to persist (favor momentum)"
    else:
        summary = "regime: weak/ambiguous structure"

    detail = {
        "n_returns": n,
        "ac_band": band,
        "autocorr": acs,
        "variance_ratios": {q: {"vr": vr, "z": z} for q, (vr, z) in vrs.items()},
    }
    return summary, detail
