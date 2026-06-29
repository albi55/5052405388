"""Data validation. A backtest on dirty data is a more sophisticated lie, so we
validate on load and WARN loudly rather than silently producing wrong results.

Checks: monotonic timestamps, duplicate bars, OHLC sanity (high>=low, close in
range), zero/negative prices, suspicious gaps (much larger than the modal bar
spacing — weekends excepted for FX), and outlier returns (likely bad ticks).
Returns warnings; the caller decides whether to proceed.
"""

from __future__ import annotations

from collections import Counter

from ..core.types import Bar


def validate_bars(bars: list[Bar], timeframe: str) -> list[str]:
    warnings: list[str] = []
    if not bars:
        return ["no bars to validate"]

    # 1. ordering and duplicates
    times = [b.time for b in bars]
    if times != sorted(times):
        warnings.append("bars are not in ascending time order")
    dupes = [t for t, c in Counter(times).items() if c > 1]
    if dupes:
        warnings.append(f"{len(dupes)} duplicate timestamp(s) detected")

    # 2. OHLC sanity
    bad_ohlc = 0
    nonpos = 0
    for b in bars:
        if b.high < b.low or not (b.low <= b.open <= b.high) or not (b.low <= b.close <= b.high):
            bad_ohlc += 1
        if min(b.open, b.high, b.low, b.close) <= 0:
            nonpos += 1
    if bad_ohlc:
        warnings.append(f"{bad_ohlc} bar(s) with inconsistent OHLC (high<low or close/open out of range)")
    if nonpos:
        warnings.append(f"{nonpos} bar(s) with non-positive prices")

    # 3. gaps: compare consecutive spacings to the modal spacing.
    if len(bars) >= 3:
        deltas = [(times[i] - times[i - 1]).total_seconds() for i in range(1, len(times))]
        modal = Counter(deltas).most_common(1)[0][0]
        if modal > 0:
            # Allow up to ~3x modal (weekend on daily FX is ~3 calendar days).
            big_gaps = sum(1 for d in deltas if d > modal * 3.5)
            if big_gaps:
                warnings.append(f"{big_gaps} unusually large time gap(s) (possible missing data/holidays)")

    # 4. outlier returns — candidate bad ticks.
    closes = [b.close for b in bars]
    rets = [abs(closes[i] / closes[i - 1] - 1.0) for i in range(1, len(closes)) if closes[i - 1] > 0]
    if rets:
        rets_sorted = sorted(rets)
        # median absolute return; flag anything > 25x median (very rough, FX daily
        # moves are tiny, so a 25x jump is almost certainly a bad tick).
        med = rets_sorted[len(rets_sorted) // 2] or 1e-9
        outliers = sum(1 for r in rets if r > med * 25)
        if outliers:
            warnings.append(f"{outliers} outlier return(s) >25x median (possible bad ticks)")

    return warnings
