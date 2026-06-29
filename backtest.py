"""
Mean-reversion backtest on daily EUR/USD (read-only, historical analysis).

Rule under test:
  ENTRY (long): close is >= ENTRY_DISCOUNT below its N-day SMA
  EXIT:
    - take profit: price returns to the N-day SMA, OR
    - stop loss:   price falls a further STOP_FURTHER below the entry price

This script places NO real orders. It only pulls historical candles via
mt5.copy_rates_from_pos() and simulates the trades in memory.

This version runs a MATRIX of variations and prints the same stats for each:
  entry discount {1%, 2%}  x  SMA period {10, 20}

Honest-accounting choices (these matter — read them):
  * Signals are computed on a day's CLOSE, but you cannot trade at a close you
    haven't seen yet. So entries/exits fill on the NEXT day's OPEN. This avoids
    look-ahead bias, which is the #1 way backtests lie.
  * Costs: we charge a spread per side on entry AND exit. We take the LIVE spread
    from symbol_info but floor it at a realistic minimum (SPREAD_FLOOR), because
    the live feed reports 0 when the market is closed. A strategy that only works
    at zero cost doesn't work.
  * Intrabar fills for SL/TP are approximate: within a single daily candle we
    cannot know whether the high or low came first. We use a conservative
    convention (check stop before target) so results are not flattered.
  * One position at a time, fixed notional, no compounding, no leverage modeling.
    This isolates whether the RULE has edge, separate from money management.
"""

import sys
from datetime import datetime, timezone

import MetaTrader5 as mt5

# ---------------------------------------------------------------------------
# Parameters
# ---------------------------------------------------------------------------
SYMBOL          = "EURUSD"
TIMEFRAME       = mt5.TIMEFRAME_D1
LOOKBACK_DAYS   = 2600         # ~10 years of trading days (markets ~252/yr)
STOP_FURTHER    = 0.03         # stop = 3% below entry price
SLIPPAGE_PRICE  = 0.00000      # extra adverse fill per side; raise to stress-test
START_EQUITY    = 10_000.0     # notional traded per position (no compounding)

# Realistic floor for EUR/USD spread, in PRICE units (1 pip = 0.0001).
# The live feed reports 0 when markets are closed, which would model zero cost.
SPREAD_FLOOR    = 0.0001

# Variations to test: (entry discount below SMA, SMA period)
# Sweep the entry discount on the 20-day SMA (the better period from prior runs);
# keep one 10-day row to confirm it stays worse at 10-year scale.
VARIATIONS = [
    (0.005, 20),
    (0.010, 20),
    (0.015, 20),
    (0.020, 20),
    (0.010, 10),
]


def fetch_bars():
    """Connect to MT5, pull candles + spread, then disconnect. Returns
    (bars, cost_per_side, span_text). Exits the process on hard failure."""
    if not mt5.initialize():
        print("Failed to connect to MT5:", mt5.last_error())
        sys.exit(1)

    try:
        info = mt5.symbol_info(SYMBOL)
        if info is None or not info.visible:
            # Symbol may exist but not be in Market Watch; try to select it.
            if not mt5.symbol_select(SYMBOL, True):
                print(f"Symbol {SYMBOL} not available:", mt5.last_error())
                sys.exit(1)
            info = mt5.symbol_info(SYMBOL)

        live_spread = (info.spread * info.point) if info else 0.0
        # Floor the live spread so closed-market 0.0 doesn't model zero cost.
        spread_price = max(live_spread, SPREAD_FLOOR)
        cost_per_side = spread_price + SLIPPAGE_PRICE

        rates = mt5.copy_rates_from_pos(SYMBOL, TIMEFRAME, 0, LOOKBACK_DAYS)
        if rates is None or len(rates) == 0:
            print("No rate data returned:", mt5.last_error())
            sys.exit(1)
    finally:
        mt5.shutdown()

    bars = [
        {
            "time":  datetime.fromtimestamp(int(r["time"]), tz=timezone.utc),
            "open":  float(r["open"]),
            "high":  float(r["high"]),
            "low":   float(r["low"]),
            "close": float(r["close"]),
        }
        for r in rates
    ]

    span = f"{bars[0]['time'].date()} -> {bars[-1]['time'].date()}"
    print(f"Pulled {len(bars)} daily {SYMBOL} candles: {span}")
    print(f"Live spread: {live_spread:.5f} | floor: {SPREAD_FLOOR:.5f} | "
          f"modeled cost/side: {cost_per_side:.5f} price "
          f"(spread {spread_price:.5f} + slippage {SLIPPAGE_PRICE:.5f})\n")
    return bars, cost_per_side


def rolling_sma(bars, period):
    """SMA of close aligned so sma[i] uses closes [i-period+1 .. i]."""
    n = len(bars)
    sma = [None] * n
    running = 0.0
    for i in range(n):
        running += bars[i]["close"]
        if i >= period:
            running -= bars[i - period]["close"]
        if i >= period - 1:
            sma[i] = running / period
    return sma


def simulate(bars, entry_discount, sma_period, cost_per_side):
    """Run the rule once. Returns a dict of stats + the trade list."""
    n = len(bars)
    sma = rolling_sma(bars, sma_period)

    in_pos = False
    entry_price = stop_price = 0.0
    entry_time = None
    trades = []
    equity = START_EQUITY
    equity_curve = [START_EQUITY]

    for i in range(n - 1):              # i+1 must exist to fill on next open
        if sma[i] is None:
            continue
        nxt = bars[i + 1]

        if not in_pos:
            below = sma[i] * (1.0 - entry_discount)
            if bars[i]["close"] <= below:
                entry_price = nxt["open"] + cost_per_side
                stop_price = nxt["open"] * (1.0 - STOP_FURTHER)
                entry_time = nxt["time"]
                in_pos = True
        else:
            target = sma[i]             # TP when price returns to the SMA
            exit_price = reason = None
            # Conservative: assume stop tested before target within a candle.
            if nxt["low"] <= stop_price:
                exit_price = stop_price - cost_per_side
                reason = "stop"
            elif nxt["high"] >= target:
                exit_price = target - cost_per_side
                reason = "target"

            if exit_price is not None:
                ret = (exit_price - entry_price) / entry_price
                equity *= (1.0 + ret)
                trades.append({
                    "entry_time": entry_time, "exit_time": nxt["time"],
                    "entry": entry_price, "exit": exit_price,
                    "ret": ret, "reason": reason,
                })
                equity_curve.append(equity)
                in_pos = False

    # Stats
    n_trades = len(trades)
    if n_trades == 0:
        return {"n_trades": 0, "total_return": 0.0, "win_rate": 0.0,
                "max_dd": 0.0, "stops": 0, "targets": 0, "avg_ret": 0.0,
                "final_equity": START_EQUITY, "trades": []}

    wins = sum(1 for t in trades if t["ret"] > 0)
    total_return = (equity / START_EQUITY) - 1.0
    peak = equity_curve[0]
    max_dd = 0.0
    for v in equity_curve:
        peak = max(peak, v)
        max_dd = min(max_dd, (v - peak) / peak)

    return {
        "n_trades": n_trades,
        "total_return": total_return,
        "win_rate": wins / n_trades,
        "max_dd": max_dd,
        "stops": sum(1 for t in trades if t["reason"] == "stop"),
        "targets": sum(1 for t in trades if t["reason"] == "target"),
        "avg_ret": sum(t["ret"] for t in trades) / n_trades,
        "final_equity": equity,
        "trades": trades,
    }


def main():
    bars, cost_per_side = fetch_bars()

    print("=" * 78)
    print("RESULTS BY VARIATION  (long-only mean reversion, next-open fills)")
    print("=" * 78)
    header = (f"{'entry':>6}  {'SMA':>4}  {'trades':>6}  {'tot.ret':>8}  "
              f"{'win%':>6}  {'avg/tr':>7}  {'maxDD':>7}  {'tgt/stp':>8}")
    print(header)
    print("-" * 78)

    results = []
    for entry_discount, sma_period in VARIATIONS:
        s = simulate(bars, entry_discount, sma_period, cost_per_side)
        results.append(((entry_discount, sma_period), s))
        print(f"{entry_discount*100:>4.1f}%  {sma_period:>4}  {s['n_trades']:>6}  "
              f"{s['total_return']*100:>7.2f}%  {s['win_rate']*100:>5.1f}%  "
              f"{s['avg_ret']*100:>6.2f}%  {s['max_dd']*100:>6.2f}%  "
              f"{s['targets']:>3}/{s['stops']:<3}")

    print("-" * 78)
    print("entry = close this far below SMA to buy | tgt = exits at SMA | "
          "stp = -3% stop hit")

    # Per-variation trade logs, for the eyeball test.
    for (entry_discount, sma_period), s in results:
        print(f"\n--- entry {entry_discount*100:.1f}% below {sma_period}-day SMA "
              f"({s['n_trades']} trades) ---")
        if not s["trades"]:
            print("  (no trades)")
            continue
        print(f"  {'entry':>10}  {'exit':>10}  {'in':>8} {'out':>8}  {'ret%':>7}  reason")
        for t in s["trades"]:
            print(f"  {t['entry_time'].date()!s:>10}  {t['exit_time'].date()!s:>10}  "
                  f"{t['entry']:>8.5f} {t['exit']:>8.5f}  {t['ret']*100:>7.2f}  {t['reason']}")

    print("\nCaveats: daily-bar intrabar fills approximate (stop assumed before")
    print("target within a candle); next-open fills avoid look-ahead; cost = spread")
    print("per side, floored at the realistic minimum. Small samples = noisy win rate.")


if __name__ == "__main__":
    main()
