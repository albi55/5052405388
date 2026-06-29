"""Rate-differential (carry) PROXY source.

⚠️ THIS IS NOT REAL CARRY DATA. A genuine carry signal needs the actual interest-
rate differential between the two currencies (e.g. from a central-bank / rates
feed). We do not have that feed wired yet. Until we do, this module synthesizes a
slow-moving proxy series from price itself so the CARRY MACHINERY is testable
end-to-end — but any result computed on it is NOT tradeable evidence and the loop
labels it as such.

When you wire a real rates feed, implement get_rate_differential() to return the
true differential aligned to the bars, and the loop's carry results become real.
"""

from __future__ import annotations

import numpy as np

from ..core.types import Bar


PROXY_WARNING = ("CARRY PROXY DATA — synthetic, NOT real rate differentials; "
                 "result is machinery-validation only, NOT tradeable evidence")


def get_rate_differential(bars: list[Bar]) -> np.ndarray:
    """Return a per-bar carry-like series aligned to bars. PROXY ONLY.

    We use a long, slow z-score of price as a stand-in for a slow macro signal.
    This deliberately has SOME structure so the pipeline exercises the carry path,
    but it is not economically meaningful. Do not trade on it."""
    close = np.array([b.close for b in bars], dtype=float)
    n = len(close)
    out = np.full(n, np.nan, dtype=float)
    window = 100
    if n <= window:
        return out
    for i in range(window, n):
        seg = close[i - window:i]
        s = seg.std()
        out[i] = (close[i] - seg.mean()) / s if s > 0 else 0.0
    return out
