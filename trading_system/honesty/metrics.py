"""Risk metrics computed from a trade list. Drawdown and risk are FIRST-CLASS:
no function here returns a bare total return without the drawdown beside it.
"""

from __future__ import annotations

from ..core.types import Trade, RiskMetrics


# Compounded equity curve from a fixed base so drawdown reflects real path
# dependence. The base is a notional scale only; returns are fractional.
_BASE_EQUITY = 10_000.0


def compute_metrics(trades: list[Trade]) -> RiskMetrics:
    n = len(trades)
    if n == 0:
        return RiskMetrics(0.0, 0.0, 0.0, 0, 0, 0.0, 0.0, 0)

    # Equity curve (compounded, so drawdown reflects real path dependence).
    equity = _BASE_EQUITY
    curve = [equity]
    for t in trades:
        equity *= (1.0 + t.ret)
        curve.append(equity)
    total_return = curve[-1] / _BASE_EQUITY - 1.0

    # Max drawdown and longest time underwater.
    peak = curve[0]
    max_dd = 0.0
    underwater = 0
    longest_underwater = 0
    for v in curve:
        if v >= peak:
            peak = v
            underwater = 0
        else:
            underwater += 1
            longest_underwater = max(longest_underwater, underwater)
        dd = (v - peak) / peak
        max_dd = min(max_dd, dd)

    # Worst consecutive losing streak (by trade count).
    streak = 0
    worst_streak = 0
    for t in trades:
        if t.ret <= 0:
            streak += 1
            worst_streak = max(worst_streak, streak)
        else:
            streak = 0

    wins = sum(1 for t in trades if t.is_win)
    win_rate = wins / n
    avg_trade = sum(t.ret for t in trades) / n
    rdd = (total_return / abs(max_dd)) if max_dd < 0 else float("inf")

    return RiskMetrics(
        total_return=total_return,
        max_drawdown=max_dd,
        return_dd_ratio=rdd,
        worst_losing_streak=worst_streak,
        longest_underwater_bars=longest_underwater,
        win_rate=win_rate,
        avg_trade=avg_trade,
        n_trades=n,
    )
